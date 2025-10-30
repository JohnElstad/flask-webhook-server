"""
Subaccount Manager for handling multiple GHL subaccounts
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

class SubaccountManager:
    """
    Manages multiple GHL subaccounts and their credentials
    """
    
    def __init__(self):
        self.subaccount_cache = {}  # Cache for subaccount credentials
        self.cache_ttl = 300  # 5 minutes cache TTL
        self.last_cache_update = {}
        
    def get_subaccount_from_webhook(self, webhook_data: dict) -> Optional[str]:
        """
        Extract subaccount ID from webhook data
        
        GHL webhooks may contain subaccount info in various fields:
        - locationId
        - location_id  
        - customData.locationId
        - customData.subaccountId
        """
        # Try common location ID fields
        subaccount_id = (webhook_data.get('locationId') or 
                        webhook_data.get('location_id') or
                        webhook_data.get('location'))
        
        if subaccount_id:
            # If location is a dict, try to extract the ID
            if isinstance(subaccount_id, dict):
                subaccount_id = (subaccount_id.get('id') or 
                               subaccount_id.get('locationId') or
                               subaccount_id.get('location_id'))
            
            if subaccount_id:
                return subaccount_id
            
        # Check customData
        custom_data = webhook_data.get('customData', {})
        if isinstance(custom_data, dict):
            subaccount_id = (custom_data.get('locationId') or 
                           custom_data.get('subaccountId') or
                           custom_data.get('location_id'))
            
        # Check contact data
        contact_data = webhook_data.get('contact', {})
        if isinstance(contact_data, dict):
            subaccount_id = (contact_data.get('locationId') or 
                           contact_data.get('location_id'))
            
        # Check message data
        message_data = webhook_data.get('message', {})
        if isinstance(message_data, dict):
            subaccount_id = (message_data.get('locationId') or 
                           message_data.get('location_id'))
            
        # Fallback: check for any field containing 'location'
        if not subaccount_id:
            for key, value in webhook_data.items():
                if 'location' in key.lower() and isinstance(value, str):
                    subaccount_id = value
                    break
                    
        return subaccount_id
    
    def get_subaccount_id(self, ghl_location_id: str) -> str:
        """
        Get the actual subaccount_id from a GHL location ID
        Returns the subaccount_id to use for bot configurations
        """
        logger.info(f"DEBUG SUBACCOUNT: Looking up subaccount_id for ghl_location_id='{ghl_location_id}'")
        credentials = self._fetch_subaccount_from_db(ghl_location_id)
        logger.info(f"DEBUG SUBACCOUNT: Database returned credentials: {credentials}")
        if credentials and credentials.get('subaccount_id'):
            result = credentials['subaccount_id']
            logger.info(f"DEBUG SUBACCOUNT: Returning subaccount_id='{result}'")
            return result
        logger.info(f"DEBUG SUBACCOUNT: No credentials found, returning fallback='{ghl_location_id}'")
        return ghl_location_id  # fallback to the original identifier

    def get_subaccount_credentials(self, identifier: str) -> Optional[Dict[str, str]]:
        """
        Get credentials for a specific subaccount by subaccount_id OR ghl_location_id
        Returns dict with api_key, location_id, base_url
        """
        # Check cache first (use identifier as cache key)
        if self._is_cache_valid(identifier):
            return self.subaccount_cache.get(identifier)
            
        # Fetch from database
        credentials = self._fetch_subaccount_from_db(identifier)
        
        if credentials:
            # Update cache (use identifier as cache key)
            self.subaccount_cache[identifier] = credentials
            self.last_cache_update[identifier] = datetime.now()
            
        return credentials
    
    def _is_cache_valid(self, subaccount_id: str) -> bool:
        """Check if cached credentials are still valid"""
        if subaccount_id not in self.subaccount_cache:
            return False
            
        last_update = self.last_cache_update.get(subaccount_id)
        if not last_update:
            return False
            
        return (datetime.now() - last_update).total_seconds() < self.cache_ttl
    
    def _fetch_subaccount_from_db(self, identifier: str) -> Optional[Dict[str, str]]:
        """Fetch subaccount credentials from Supabase by subaccount_id OR ghl_location_id"""
        try:
            if not SUPABASE_URL or not SUPABASE_ANON_KEY:
                logger.error("Supabase credentials not configured")
                return None
                
            url = f"{SUPABASE_URL}/rest/v1/subaccounts"
            headers = {
                'apikey': SUPABASE_ANON_KEY,
                'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
                'Content-Type': 'application/json'
            }
            
            # Try to find by subaccount_id first, then by ghl_location_id
            params = {
                'or': f'(subaccount_id.eq.{identifier},ghl_location_id.eq.{identifier})',
                'is_active': 'eq.true',
                'select': 'subaccount_id,ghl_api_key,ghl_location_id,ghl_base_url'
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    subaccount = data[0]
                    return {
                        'subaccount_id': subaccount['subaccount_id'],
                        'api_key': subaccount['ghl_api_key'],
                        'location_id': subaccount['ghl_location_id'],
                        'base_url': subaccount.get('ghl_base_url', 'https://services.leadconnectorhq.com')
                    }
                else:
                    logger.warning(f"No active subaccount found for ID: {subaccount_id}")
                    return None
            else:
                logger.error(f"Failed to fetch subaccount {subaccount_id}: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching subaccount {subaccount_id}: {str(e)}")
            return None
    
    def get_default_subaccount(self) -> Optional[Dict[str, str]]:
        """
        Get default subaccount credentials from environment variables
        Used as fallback when subaccount can't be determined from webhook
        """
        api_key = os.getenv('GHL_API_KEY')
        location_id = os.getenv('GHL_LOCATION_ID')
        base_url = os.getenv('GHL_BASE_URL', 'https://services.leadconnectorhq.com')
        
        if api_key and location_id:
            return {
                'api_key': api_key,
                'location_id': location_id,
                'base_url': base_url
            }
        return None
    
    def add_subaccount(self, subaccount_id: str, subaccount_name: str, 
                      api_key: str, location_id: str, base_url: str = None) -> bool:
        """Add a new subaccount to the database"""
        try:
            if not SUPABASE_URL or not SUPABASE_ANON_KEY:
                logger.error("Supabase credentials not configured")
                return False
                
            url = f"{SUPABASE_URL}/rest/v1/subaccounts"
            headers = {
                'apikey': SUPABASE_ANON_KEY,
                'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'subaccount_id': subaccount_id,
                'subaccount_name': subaccount_name,
                'ghl_api_key': api_key,
                'ghl_location_id': location_id,
                'ghl_base_url': base_url or 'https://services.leadconnectorhq.com',
                'is_active': True
            }
            
            response = requests.post(url, json=data, headers=headers, timeout=5)
            
            if response.status_code in [200, 201]:
                logger.info(f"Successfully added subaccount: {subaccount_id}")
                # Clear cache to force refresh
                if subaccount_id in self.subaccount_cache:
                    del self.subaccount_cache[subaccount_id]
                return True
            else:
                logger.error(f"Failed to add subaccount {subaccount_id}: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error adding subaccount {subaccount_id}: {str(e)}")
            return False
    
    def list_subaccounts(self) -> list:
        """List all active subaccounts"""
        try:
            if not SUPABASE_URL or not SUPABASE_ANON_KEY:
                logger.error("Supabase credentials not configured")
                return []
                
            url = f"{SUPABASE_URL}/rest/v1/subaccounts"
            headers = {
                'apikey': SUPABASE_ANON_KEY,
                'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
                'Content-Type': 'application/json'
            }
            
            params = {
                'is_active': 'eq.true',
                'select': 'subaccount_id,subaccount_name,ghl_location_id,created_at'
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=5)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to list subaccounts: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error listing subaccounts: {str(e)}")
            return []

# Global instance
subaccount_manager = SubaccountManager()
