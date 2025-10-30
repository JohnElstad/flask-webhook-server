"""
API endpoints for managing bot configurations
"""
from flask import Blueprint, request, jsonify
import logging
from bot_config_manager import bot_config_manager

# Configure logging
logger = logging.getLogger(__name__)

# Create bot config API blueprint
bot_config_api_bp = Blueprint('bot_config_api', __name__)

@bot_config_api_bp.route('/api/bots', methods=['GET'])
def list_bot_configs():
    """
    List all bot configurations, optionally filtered by subaccount
    Query params: ?subaccount_id=xyz
    """
    try:
        subaccount_id = request.args.get('subaccount_id')
        configs = bot_config_manager.list_bot_configs(subaccount_id)
        
        return jsonify({
            'status': 'success',
            'bot_configs': configs,
            'count': len(configs)
        }), 200
    except Exception as e:
        logger.error(f"Error listing bot configs: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to list bot configs: {str(e)}'
        }), 500

@bot_config_api_bp.route('/api/bots', methods=['POST'])
def add_bot_config():
    """
    Add a new bot configuration
    
    Expected JSON body:
    {
        "subaccount_id": "Texas Health Fitness Center",
        "source_name": "fitness_lead",
        "bot_name": "Fitness Lead Bot",
        "system_prompt": "You are a fitness lead conversion specialist...",
        "first_message": "Hey {name}! Ready to start your fitness journey?"
    }
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['subaccount_id', 'source_name', 'bot_name', 'system_prompt', 'first_message']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'status': 'error',
                    'message': f'Missing required field: {field}'
                }), 400
        
        # Add the bot configuration
        success = bot_config_manager.add_bot_config(
            subaccount_id=data['subaccount_id'],
            source_name=data['source_name'],
            bot_name=data['bot_name'],
            system_prompt=data['system_prompt'],
            first_message=data['first_message']
        )
        
        if success:
            return jsonify({
                'status': 'success',
                'message': f'Bot config {data["subaccount_id"]}:{data["source_name"]} added successfully'
            }), 201
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to add bot configuration'
            }), 500
            
    except Exception as e:
        logger.error(f"Error adding bot config: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to add bot config: {str(e)}'
        }), 500

@bot_config_api_bp.route('/api/bots/<subaccount_id>/<source_name>', methods=['GET'])
def get_bot_config(subaccount_id, source_name):
    """
    Get a specific bot configuration
    """
    try:
        config = bot_config_manager.get_bot_config(subaccount_id, source_name)
        
        if config:
            return jsonify({
                'status': 'success',
                'subaccount_id': subaccount_id,
                'source_name': source_name,
                'config': config
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': f'Bot config {subaccount_id}:{source_name} not found'
            }), 404
            
    except Exception as e:
        logger.error(f"Error getting bot config {subaccount_id}:{source_name}: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to get bot config: {str(e)}'
        }), 500

@bot_config_api_bp.route('/api/bots/<subaccount_id>/<source_name>', methods=['PUT'])
def update_bot_config(subaccount_id, source_name):
    """
    Update a bot configuration
    
    Expected JSON body (partial updates allowed):
    {
        "bot_name": "Updated Bot Name",
        "system_prompt": "Updated system prompt...",
        "first_message": "Updated first message..."
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No update data provided'
            }), 400
        
        # Filter allowed update fields
        allowed_fields = ['bot_name', 'system_prompt', 'first_message', 'is_active']
        updates = {k: v for k, v in data.items() if k in allowed_fields}
        
        if not updates:
            return jsonify({
                'status': 'error',
                'message': 'No valid update fields provided'
            }), 400
        
        success = bot_config_manager.update_bot_config(subaccount_id, source_name, **updates)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': f'Bot config {subaccount_id}:{source_name} updated successfully'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to update bot configuration'
            }), 500
            
    except Exception as e:
        logger.error(f"Error updating bot config {subaccount_id}:{source_name}: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to update bot config: {str(e)}'
        }), 500

@bot_config_api_bp.route('/api/bots/test/<subaccount_id>/<source_name>', methods=['POST'])
def test_bot_config(subaccount_id, source_name):
    """
    Test a bot configuration by generating sample responses
    """
    try:
        data = request.get_json() or {}
        contact_name = data.get('contact_name', 'John')
        
        # Get system prompt and first message
        system_prompt = bot_config_manager.get_system_prompt(subaccount_id, source_name)
        first_message = bot_config_manager.get_first_message(subaccount_id, source_name, contact_name)
        
        return jsonify({
            'status': 'success',
            'subaccount_id': subaccount_id,
            'source_name': source_name,
            'test_results': {
                'system_prompt': system_prompt,
                'first_message': first_message,
                'contact_name_used': contact_name
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error testing bot config {subaccount_id}:{source_name}: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to test bot config: {str(e)}'
        }), 500
