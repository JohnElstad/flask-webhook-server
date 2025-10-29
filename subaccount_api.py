"""
API endpoints for managing GHL subaccounts
"""
from flask import Blueprint, request, jsonify
import logging
from subaccount_manager import subaccount_manager

# Configure logging
logger = logging.getLogger(__name__)

# Create subaccount API blueprint
subaccount_api_bp = Blueprint('subaccount_api', __name__)

@subaccount_api_bp.route('/api/subaccounts', methods=['GET'])
def list_subaccounts():
    """
    List all active subaccounts
    """
    try:
        subaccounts = subaccount_manager.list_subaccounts()
        return jsonify({
            'status': 'success',
            'subaccounts': subaccounts,
            'count': len(subaccounts)
        }), 200
    except Exception as e:
        logger.error(f"Error listing subaccounts: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to list subaccounts: {str(e)}'
        }), 500

@subaccount_api_bp.route('/api/subaccounts', methods=['POST'])
def add_subaccount():
    """
    Add a new subaccount
    
    Expected JSON body:
    {
        "subaccount_id": "sub_123",
        "subaccount_name": "My Business Account",
        "ghl_api_key": "your_api_key_here",
        "ghl_location_id": "your_location_id_here",
        "ghl_base_url": "https://rest.gohighlevel.com/v1" (optional)
    }
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['subaccount_id', 'subaccount_name', 'ghl_api_key', 'ghl_location_id']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'status': 'error',
                    'message': f'Missing required field: {field}'
                }), 400
        
        # Add the subaccount
        success = subaccount_manager.add_subaccount(
            subaccount_id=data['subaccount_id'],
            subaccount_name=data['subaccount_name'],
            api_key=data['ghl_api_key'],
            location_id=data['ghl_location_id'],
            base_url=data.get('ghl_base_url')
        )
        
        if success:
            return jsonify({
                'status': 'success',
                'message': f'Subaccount {data["subaccount_id"]} added successfully'
            }), 201
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to add subaccount'
            }), 500
            
    except Exception as e:
        logger.error(f"Error adding subaccount: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to add subaccount: {str(e)}'
        }), 500

@subaccount_api_bp.route('/api/subaccounts/<subaccount_id>', methods=['GET'])
def get_subaccount(subaccount_id):
    """
    Get credentials for a specific subaccount (without exposing API key)
    """
    try:
        credentials = subaccount_manager.get_subaccount_credentials(subaccount_id)
        
        if credentials:
            # Don't expose the full API key for security
            masked_key = credentials['api_key'][:8] + '...' + credentials['api_key'][-4:] if len(credentials['api_key']) > 12 else '***'
            
            return jsonify({
                'status': 'success',
                'subaccount_id': subaccount_id,
                'location_id': credentials['location_id'],
                'base_url': credentials['base_url'],
                'api_key_masked': masked_key
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': f'Subaccount {subaccount_id} not found'
            }), 404
            
    except Exception as e:
        logger.error(f"Error getting subaccount {subaccount_id}: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to get subaccount: {str(e)}'
        }), 500

@subaccount_api_bp.route('/api/subaccounts/test/<subaccount_id>', methods=['POST'])
def test_subaccount_credentials(subaccount_id):
    """
    Test subaccount credentials by making a simple API call to GHL
    """
    try:
        credentials = subaccount_manager.get_subaccount_credentials(subaccount_id)
        
        if not credentials:
            return jsonify({
                'status': 'error',
                'message': f'Subaccount {subaccount_id} not found'
            }), 404
        
        # Test the credentials by making a simple API call
        import requests
        
        test_url = f"{credentials['base_url']}/locations/{credentials['location_id']}"
        headers = {
            'Authorization': f'Bearer {credentials["api_key"]}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(test_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return jsonify({
                'status': 'success',
                'message': f'Subaccount {subaccount_id} credentials are valid',
                'test_response_code': response.status_code
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': f'Subaccount {subaccount_id} credentials test failed',
                'test_response_code': response.status_code,
                'test_response': response.text[:200]
            }), 400
            
    except Exception as e:
        logger.error(f"Error testing subaccount {subaccount_id}: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to test subaccount credentials: {str(e)}'
        }), 500

@subaccount_api_bp.route('/api/webhook/test', methods=['POST'])
def test_webhook_subaccount_detection():
    """
    Test webhook subaccount detection with sample data
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No webhook data provided'
            }), 400
        
        # Extract subaccount ID from webhook data
        subaccount_id = subaccount_manager.get_subaccount_from_webhook(data)
        
        # Get credentials if subaccount found
        credentials = None
        if subaccount_id:
            credentials = subaccount_manager.get_subaccount_credentials(subaccount_id)
        
        # Fallback to default if needed
        if not credentials:
            credentials = subaccount_manager.get_default_subaccount()
        
        return jsonify({
            'status': 'success',
            'detected_subaccount_id': subaccount_id,
            'credentials_found': credentials is not None,
            'using_default': subaccount_id is None,
            'webhook_data_keys': list(data.keys())
        }), 200
        
    except Exception as e:
        logger.error(f"Error testing webhook subaccount detection: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to test webhook detection: {str(e)}'
        }), 500
