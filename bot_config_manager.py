"""
Bot Configuration Manager for handling dynamic bot configurations
"""
import os
import logging
import requests
from typing import Dict, Optional, Tuple
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')

class BotConfigManager:
    """
    Manages bot configurations stored in database
    """
    
    def __init__(self):
        self.config_cache = {}  # Cache for bot configurations
        self.cache_ttl = 300  # 5 minutes cache TTL
        self.last_cache_update = {}
        
    def get_bot_config(self, subaccount_id: str, source_name: str = 'default') -> Optional[Dict[str, str]]:
        """
        Get bot configuration for a specific subaccount and source
        Returns dict with system_prompt, first_message, bot_name
        """
        cache_key = f"{subaccount_id}:{source_name}"
        
        # Check cache first
        if self._is_cache_valid(cache_key):
            return self.config_cache.get(cache_key)
            
        # Fetch from database
        config = self._fetch_bot_config_from_db(subaccount_id, source_name)
        
        if config:
            # Update cache
            self.config_cache[cache_key] = config
            self.last_cache_update[cache_key] = datetime.now()
            
        return config
    
    def get_system_prompt(self, subaccount_id: str, source_name: str = 'default') -> str:
        """Get system prompt for a specific bot configuration"""
        config = self.get_bot_config(subaccount_id, source_name)
        if config:
            return config['system_prompt']
        
        # Fallback to default
        if source_name != 'default':
            return self.get_system_prompt(subaccount_id, 'default')
        
        # Ultimate fallback
        return "You are a helpful customer service assistant."
    
    def get_first_message(self, subaccount_id: str, source_name: str = 'default', contact_name: str = '', contact_data: dict = None) -> str:
        """Get first message for a specific bot configuration"""
        logger.info(f"DEBUG BOT CONFIG: Looking for first_message with subaccount_id='{subaccount_id}', source_name='{source_name}'")
        
        config = self.get_bot_config(subaccount_id, source_name)
        logger.info(f"DEBUG BOT CONFIG: get_bot_config returned: {config}")
        
        if config:
            # Replace placeholders with actual contact data
            message = config['first_message']
            
            # Handle {name} format
            if contact_name:
                message = message.replace('{name}', contact_name)
            else:
                message = message.replace('{name}', 'there')
            
            # Handle {{contact.first_name}} and other GHL webhook formats
            if contact_data:
                first_name = contact_data.get('first_name', contact_name or 'there')
                last_name = contact_data.get('last_name', '')
                full_name = contact_data.get('full_name', contact_name or 'there')
                
                # Replace GHL webhook template variables
                message = message.replace('{{contact.first_name}}', first_name)
                message = message.replace('{{contact.last_name}}', last_name)
                message = message.replace('{{contact.full_name}}', full_name)
                message = message.replace('{{contact.name}}', first_name)
            else:
                # Fallback if no contact_data provided
                message = message.replace('{{contact.first_name}}', contact_name or 'there')
                message = message.replace('{{contact.last_name}}', '')
                message = message.replace('{{contact.full_name}}', contact_name or 'there')
                message = message.replace('{{contact.name}}', contact_name or 'there')
            
            logger.info(f"DEBUG BOT CONFIG: Found config, returning message: '{message[:50]}...'")
            return message
        
        # Fallback to default
        if source_name != 'default':
            logger.info(f"DEBUG BOT CONFIG: No config found for source '{source_name}', trying 'default'")
            return self.get_first_message(subaccount_id, 'default', contact_name, contact_data)
        
        # Ultimate fallback
        logger.info(f"DEBUG BOT CONFIG: No config found, using ultimate fallback")
        name_part = f" {contact_name}" if contact_name else ""
        return f"Hello{name_part}! How can I help you today?"
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached config is still valid"""
        if cache_key not in self.config_cache:
            return False
            
        last_update = self.last_cache_update.get(cache_key)
        if not last_update:
            return False
            
        return (datetime.now() - last_update).total_seconds() < self.cache_ttl
    
    def _fetch_bot_config_from_db(self, subaccount_id: str, source_name: str) -> Optional[Dict[str, str]]:
        """Fetch bot configuration from Supabase"""
        try:
            if not SUPABASE_URL or not SUPABASE_ANON_KEY:
                logger.error("Supabase credentials not configured")
                return None
                
            url = f"{SUPABASE_URL}/rest/v1/bot_configurations"
            headers = {
                'apikey': SUPABASE_ANON_KEY,
                'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
                'Content-Type': 'application/json'
            }
            
            # Try exact match first
            params = {
                'subaccount_id': f'eq.{subaccount_id}',
                'source_name': f'eq.{source_name}',
                'is_active': 'eq.true',
                'select': 'bot_name,system_prompt,first_message,source_name'
            }
            
            logger.info(f"DEBUG BOT CONFIG: Querying database with URL: {url}")
            logger.info(f"DEBUG BOT CONFIG: Query params: {params}")
            
            response = requests.get(url, headers=headers, params=params, timeout=5)
            logger.info(f"DEBUG BOT CONFIG: Database response status: {response.status_code}")
            logger.info(f"DEBUG BOT CONFIG: Database response: {response.text[:200]}...")
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    config = data[0]
                    return {
                        'bot_name': config['bot_name'],
                        'system_prompt': config['system_prompt'],
                        'first_message': config['first_message'],
                        'source_name': config['source_name']
                    }
                else:
                    # Try fallback to default source for this subaccount
                    if source_name != 'default':
                        return self._fetch_bot_config_from_db(subaccount_id, 'default')
                    
                    # Try fallback to default subaccount
                    if subaccount_id != 'default':
                        return self._fetch_bot_config_from_db('default', source_name)
                    
                    logger.warning(f"No bot configuration found for subaccount: {subaccount_id}, source: {source_name}")
                    return None
            else:
                logger.error(f"Failed to fetch bot config: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching bot config for {subaccount_id}:{source_name}: {str(e)}")
            return None
    
    def add_bot_config(self, subaccount_id: str, source_name: str, bot_name: str, 
                      system_prompt: str, first_message: str) -> bool:
        """Add a new bot configuration"""
        try:
            if not SUPABASE_URL or not SUPABASE_ANON_KEY:
                logger.error("Supabase credentials not configured")
                return False
                
            url = f"{SUPABASE_URL}/rest/v1/bot_configurations"
            headers = {
                'apikey': SUPABASE_ANON_KEY,
                'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'subaccount_id': subaccount_id,
                'source_name': source_name,
                'bot_name': bot_name,
                'system_prompt': system_prompt,
                'first_message': first_message,
                'is_active': True
            }
            
            response = requests.post(url, json=data, headers=headers, timeout=5)
            
            if response.status_code in [200, 201]:
                logger.info(f"Successfully added bot config: {subaccount_id}:{source_name}")
                # Clear cache to force refresh
                cache_key = f"{subaccount_id}:{source_name}"
                if cache_key in self.config_cache:
                    del self.config_cache[cache_key]
                return True
            else:
                logger.error(f"Failed to add bot config: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error adding bot config: {str(e)}")
            return False
    
    def update_bot_config(self, subaccount_id: str, source_name: str, **updates) -> bool:
        """Update an existing bot configuration"""
        try:
            if not SUPABASE_URL or not SUPABASE_ANON_KEY:
                logger.error("Supabase credentials not configured")
                return False
                
            url = f"{SUPABASE_URL}/rest/v1/bot_configurations"
            headers = {
                'apikey': SUPABASE_ANON_KEY,
                'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
                'Content-Type': 'application/json'
            }
            
            # Add updated_at timestamp
            updates['updated_at'] = datetime.utcnow().isoformat() + 'Z'
            
            params = {
                'subaccount_id': f'eq.{subaccount_id}',
                'source_name': f'eq.{source_name}'
            }
            
            response = requests.patch(url, json=updates, headers=headers, params=params, timeout=5)
            
            if response.status_code in [200, 204]:
                logger.info(f"Successfully updated bot config: {subaccount_id}:{source_name}")
                # Clear cache to force refresh
                cache_key = f"{subaccount_id}:{source_name}"
                if cache_key in self.config_cache:
                    del self.config_cache[cache_key]
                return True
            else:
                logger.error(f"Failed to update bot config: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating bot config: {str(e)}")
            return False
    
    def list_bot_configs(self, subaccount_id: str = None) -> list:
        """List bot configurations, optionally filtered by subaccount"""
        try:
            if not SUPABASE_URL or not SUPABASE_ANON_KEY:
                logger.error("Supabase credentials not configured")
                return []
                
            url = f"{SUPABASE_URL}/rest/v1/bot_configurations"
            headers = {
                'apikey': SUPABASE_ANON_KEY,
                'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
                'Content-Type': 'application/json'
            }
            
            params = {
                'is_active': 'eq.true',
                'select': 'subaccount_id,source_name,bot_name,created_at,updated_at'
            }
            
            if subaccount_id:
                params['subaccount_id'] = f'eq.{subaccount_id}'
            
            response = requests.get(url, headers=headers, params=params, timeout=5)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to list bot configs: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error listing bot configs: {str(e)}")
            return []

# Global instance
bot_config_manager = BotConfigManager()
