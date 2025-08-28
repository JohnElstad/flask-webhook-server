from flask import Blueprint, request, jsonify
import json
import logging
import os
import threading
import time
from datetime import datetime
import requests
from openai_handler import openai_handler
from chat_processor import chat_processor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get API credentials from environment variables
GHL_API_KEY = os.getenv('GHL_API_KEY')
GHL_LOCATION_ID = os.getenv('GHL_LOCATION_ID')
GHL_BASE_URL = os.getenv('GHL_BASE_URL', 'https://rest.gohighlevel.com/v1')

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')

# Create webhook blueprint
webhook_bp = Blueprint('webhook', __name__)

# Simple duplicate prevention - track contacts currently being processed
contacts_being_processed = set()
processing_lock = threading.Lock()

# Track background threads to prevent accumulation
background_threads = {}  # contact_id -> thread_info
thread_tracking_lock = threading.Lock()

def is_contact_being_processed(contact_id):
    """Check if a contact is currently being processed"""
    with processing_lock:
        return contact_id in contacts_being_processed

def mark_contact_processing(contact_id):
    """Mark a contact as being processed"""
    try:
        with processing_lock:
            contacts_being_processed.add(contact_id)
    except Exception as e:
        logger.error(f"Error marking contact {contact_id} as processing: {str(e)}")

def unmark_contact_processing(contact_id):
    """Mark a contact as no longer being processed"""
    try:
        with processing_lock:
            contacts_being_processed.discard(contact_id)
    except Exception as e:
        logger.error(f"Error unmarking contact {contact_id} as processing: {str(e)}")
    
    # Also clean up thread tracking
    try:
        with thread_tracking_lock:
            if contact_id in background_threads:
                del background_threads[contact_id]
    except Exception as e:
        logger.error(f"Error cleaning up thread tracking for contact {contact_id}: {str(e)}")

def cleanup_dead_threads():
    """Clean up any dead threads that might be causing issues"""
    try:
        import threading
        
        # Clean up tracked background threads
        with thread_tracking_lock:
            dead_contacts = []
            for contact_id, thread_info in background_threads.items():
                if not thread_info['thread'].is_alive():
                    dead_contacts.append(contact_id)
            
            for contact_id in dead_contacts:
                del background_threads[contact_id]
                logger.info(f"Cleaned up dead background thread for contact {contact_id}")
        
        # Get all threads
        all_threads = threading.enumerate()
        dead_threads = []
        
        for thread in all_threads:
            if not thread.is_alive() and thread != threading.main_thread():
                dead_threads.append(thread.name)
        
        if dead_threads:
            logger.info(f"Found {len(dead_threads)} dead threads: {dead_threads}")
            
        return len(dead_threads)
        
    except Exception as e:
        logger.error(f"Error cleaning up dead threads: {str(e)}")
        return 0

def store_contact_in_supabase(contact_data):
    """
    Store contact information in Supabase
    """
    try:
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            logger.error("Supabase credentials not configured")
            return False
        
        # Extract contact information
        contact_id = contact_data.get('contact_id')
        first_name = contact_data.get('first_name', '')
        last_name = contact_data.get('last_name', '')
        phone = contact_data.get('phone', '')
        email = contact_data.get('email', '')
        company_name = contact_data.get('company_name', '')
        
        # Prepare data for Supabase
        supabase_data = {
            'contact_id': contact_id,
            'first_name': first_name,
            'last_name': last_name,
            'phone': phone,
            'email': email,
            'company_name': company_name,
            'created_at': datetime.utcnow().isoformat() + 'Z',  # Use UTC time with Z suffix
            'updated_at': datetime.utcnow().isoformat() + 'Z'   # Use UTC time with Z suffix
        }
        
        # Insert into contacts table
        contacts_url = f"{SUPABASE_URL}/rest/v1/contacts"
        headers = {
            'apikey': SUPABASE_ANON_KEY,
            'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
            'Content-Type': 'application/json',
            'Prefer': 'resolution=merge-duplicates'  # This handles duplicates gracefully
        }
        
        # Add 5-second timeout to prevent hanging - reduced from 10s
        response = requests.post(contacts_url, json=supabase_data, headers=headers, timeout=5)
        
        if response.status_code in [200, 201]:
            logger.info(f"Contact {contact_id} stored/updated in Supabase successfully")
            return True
        elif response.status_code == 409:
            logger.info(f"Contact {contact_id} already exists in Supabase (duplicate handled)")
            return True
        else:
            logger.error(f"Failed to store contact in Supabase: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error(f"Timeout storing contact {contact_id} in Supabase")
        return False
    except Exception as e:
        logger.error(f"Error storing contact in Supabase: {str(e)}")
        return False

def store_message_in_supabase(contact_id, message_data):
    """
    Store SMS message in Supabase
    """
    try:
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            logger.error("Supabase credentials not configured")
            return False
        
        # Extract message information
        message_body = message_data.get('body', '')
        
        # Log the message for debugging
        logger.info(f"Processing SMS message: {message_body[:50]}...")
        
        # Prepare data for Supabase
        current_time = datetime.utcnow().isoformat() + 'Z'
        logger.info(f"Storing message with timestamp: {current_time}")
        
        supabase_data = {
            'contact_id': contact_id,
            'message_body': message_body,
            'message_type': 'SMS',  # Always SMS
            'created_at': current_time  # Use UTC time with Z suffix
        }
        
        # Insert into messages table
        messages_url = f"{SUPABASE_URL}/rest/v1/messages"
        headers = {
            'apikey': SUPABASE_ANON_KEY,
            'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
            'Content-Type': 'application/json'
        }
        
        # Add 5-second timeout to prevent hanging - reduced from 10s
        response = requests.post(messages_url, json=supabase_data, headers=headers, timeout=5)
        
        if response.status_code in [200, 201]:
            logger.info(f"SMS message for contact {contact_id} stored in Supabase successfully")
            return True
        else:
            logger.error(f"Failed to store SMS message in Supabase: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error(f"Timeout storing SMS message for contact {contact_id} in Supabase")
        return False
    except Exception as e:
        logger.error(f"Error storing SMS message in Supabase: {str(e)}")
        return False

def store_openai_analysis_in_supabase(contact_id, message_body, analysis_result):
    """
    Store OpenAI analysis results in Supabase
    """
    try:
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            logger.error("Supabase credentials not configured")
            return False
        
        # Prepare analysis data for Supabase
        supabase_data = {
            'contact_id': contact_id,
            'message_body': message_body,
            'sentiment': analysis_result.get('sentiment', {}).get('sentiment', 'unknown'),
            'sentiment_confidence': analysis_result.get('sentiment', {}).get('confidence', 0.0),
            'intent': analysis_result.get('intent', {}).get('intent', 'unknown'),
            'ai_response': analysis_result.get('ai_response', {}).get('response', ''),
            'tokens_used': analysis_result.get('ai_response', {}).get('tokens_used', 0),
            'processed': analysis_result.get('processed', False),
            'created_at': datetime.utcnow().isoformat() + 'Z'  # Use UTC time with Z suffix
        }
        
        # Insert into openai_analysis table
        analysis_url = f"{SUPABASE_URL}/rest/v1/openai_analysis"
        headers = {
            'apikey': SUPABASE_ANON_KEY,
            'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
            'Content-Type': 'application/json'
        }
        
        # Add 5-second timeout to prevent hanging
        response = requests.post(analysis_url, json=supabase_data, headers=headers, timeout=5)
        
        if response.status_code in [200, 201]:
            logger.info(f"OpenAI analysis for contact {contact_id} stored in Supabase successfully")
            return True
        else:
            logger.error(f"Failed to store OpenAI analysis in Supabase: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error storing OpenAI analysis in Supabase: {str(e)}")
        return False

def process_webhook_background(data):
    """
    Process webhook data in background thread with comprehensive error protection
    """
    contact_id = "unknown"
    try:
        # Extract contact_id first for logging
        contact_id = data.get('contact_id', 'unknown')
        message_data = data.get('message', {})
        
        logger.info(f"=== BACKGROUND PROCESSING STARTED ===")
        logger.info(f"Contact ID: {contact_id}")
        logger.info(f"Data type: {type(data)}")
        logger.info(f"Data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        
        if contact_id and contact_id != 'unknown':
            logger.info(f"Background processing webhook for contact ID: {contact_id}")
            
            # Mark contact as being processed (minimal lock time)
            try:
                mark_contact_processing(contact_id)
            except Exception as e:
                logger.error(f"Failed to mark contact processing for {contact_id}: {str(e)}")
            
            # Store contact information in Supabase with comprehensive error handling
            try:
                logger.info(f"Attempting to store contact for {contact_id}")
                contact_stored = store_contact_in_supabase(data)
                logger.info(f"Contact storage completed for {contact_id}: {contact_stored}")
            except Exception as e:
                logger.error(f"Contact storage failed for {contact_id}: {str(e)}")
                logger.error(f"Error type: {type(e).__name__}")
                import traceback
                logger.error(f"Contact storage traceback: {traceback.format_exc()}")
                contact_stored = False
            
            # Store message in Supabase with comprehensive error handling
            message_stored = False
            if message_data:
                try:
                    logger.info(f"Attempting to store message for {contact_id}")
                    message_stored = store_message_in_supabase(contact_id, message_data)
                    logger.info(f"Message storage completed for {contact_id}: {message_stored}")
                except Exception as e:
                    logger.error(f"Message storage failed for {contact_id}: {str(e)}")
                    logger.error(f"Error type: {type(e).__name__}")
                    import traceback
                    logger.error(f"Message storage traceback: {traceback.format_exc()}")
                    message_stored = False
                
                # Handle new SMS with message batching
                message_body = message_data.get('body', '')
                if message_body:
                    try:
                        logger.info(f"New SMS received for contact {contact_id}: {message_body[:50]}...")
                        
                        # Start or extend message batch for AI processing
                        chat_processor.start_message_batch(contact_id, message_body)
                        
                        logger.info(f"Message added to batch for contact {contact_id}")
                    except Exception as e:
                        logger.error(f"Message batching failed for {contact_id}: {str(e)}")
                        logger.error(f"Error type: {type(e).__name__}")
                        import traceback
                        logger.error(f"Message batching traceback: {traceback.format_exc()}")
                else:
                    logger.info("No message body found in webhook")
            else:
                message_stored = True  # No message to store
                logger.info("No message data found in webhook")
            
            # Process the webhook data based on type
            webhook_type = data.get('type', 'unknown')
            
            if webhook_type == 'contact.reply':
                # Handle contact reply webhook in background
                logger.info(f"Background processing contact reply for contact {contact_id}")
            elif webhook_type == 'contact.created':
                # Handle contact creation webhook in background
                logger.info(f"Background processing contact creation for contact {contact_id}")
            else:
                # Handle unknown webhook types (like your custom workflow)
                logger.info(f"Background processing custom webhook type: {webhook_type}")
            
            logger.info(f"Background processing completed for contact {contact_id}")
            
        else:
            logger.warning(f"No valid contact_id found in webhook data: {contact_id}")
            
    except Exception as e:
        logger.error(f"=== CRITICAL BACKGROUND PROCESSING ERROR ===")
        logger.error(f"Contact ID: {contact_id}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        import traceback
        logger.error(f"Full background processing traceback: {traceback.format_exc()}")
        # Don't let background errors crash the main thread
    finally:
        logger.info(f"=== BACKGROUND PROCESSING ENDED ===")
        logger.info(f"Contact ID: {contact_id}")
        # Unmark contact as being processed
        unmark_contact_processing(contact_id)

@webhook_bp.route('/webhook', methods=['POST'])
def webhook():
    """
    Handle incoming webhook requests from GHL - return immediately
    """
    # Add comprehensive error handling to prevent crashes
    try:
        # Log the incoming webhook immediately
        logger.info(f"=== WEBHOOK RECEIVED ===")
        logger.info(f"Timestamp: {datetime.now()}")
        logger.info(f"Method: {request.method}")
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Content-Length: {request.content_length}")
        logger.info(f"Headers: {dict(request.headers)}")
        
        # Get the webhook data with comprehensive error handling
        data = {}
        try:
            if request.is_json:
                logger.info("Attempting to parse JSON webhook data...")
                data = request.get_json()
                logger.info(f"JSON webhook data parsed successfully: {type(data)}")
            else:
                logger.info("Attempting to parse form webhook data...")
                data = request.form.to_dict()
                logger.info(f"Form webhook data parsed successfully: {type(data)}")
                
            logger.info(f"Webhook data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            
        except Exception as e:
            logger.error(f"Critical error parsing webhook data: {str(e)}")
            logger.error(f"Request data: {request.get_data()}")
            # Return error response immediately to prevent hanging
            return jsonify({
                'status': 'error',
                'message': f'Failed to parse webhook data: {str(e)}',
                'error_type': 'parsing_error'
            }), 400
        
        # Extract contact_id for immediate response
        contact_id = data.get('contact_id', 'unknown')
        logger.info(f"Contact ID extracted: {contact_id}")
        
        # Validate essential data
        if not contact_id or contact_id == 'unknown':
            logger.warning("No contact_id found in webhook data")
            contact_id = f"unknown_{int(time.time())}"
        
        # Check if contact is already being processed (non-blocking)
        try:
            contact_already_processing = False
            with processing_lock:
                contact_already_processing = contact_id in contacts_being_processed
            
            if contact_already_processing:
                logger.info(f"Contact {contact_id} is already being processed, skipping duplicate webhook")
                # Still return success to prevent webhook failures
                response_data = {
                    'status': 'success',
                    'message': 'Webhook received but contact already being processed',
                    'contact_id': contact_id,
                    'processing': {
                        'type': 'already_processing',
                        'message': 'Contact is already being processed, message will be handled by existing process'
                    },
                    'timestamp': datetime.now().isoformat()
                }
                return jsonify(response_data), 200
        except Exception as e:
            logger.error(f"Error checking contact processing status for {contact_id}: {str(e)}")
            # Continue with processing - don't fail the webhook
        
        # Start background processing with comprehensive error protection
        def process_in_background():
            try:
                logger.info(f"Starting background processing for contact {contact_id}")
                process_webhook_background(data)
                logger.info(f"Background processing completed for contact {contact_id}")
            except Exception as e:
                logger.error(f"Background processing error for contact {contact_id}: {str(e)}")
                logger.error(f"Error type: {type(e).__name__}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Start background thread WITHOUT waiting for any locks
        try:
            logger.info(f"Creating background thread for contact {contact_id}")
            thread = threading.Thread(target=process_in_background, name=f"Webhook-{contact_id}")
            thread.daemon = True
            
            # Start thread immediately without any lock operations
            thread.start()
            
            # Track the thread AFTER starting it (no lock contention)
            try:
                with thread_tracking_lock:
                    background_threads[contact_id] = {
                        'thread': thread,
                        'start_time': time.time(),
                        'name': thread.name
                    }
            except Exception as tracking_error:
                logger.error(f"Thread tracking failed for contact {contact_id}: {str(tracking_error)}")
                # Don't fail the webhook for tracking errors
            
            logger.info(f"Background thread started successfully for contact {contact_id}")
        except Exception as e:
            logger.error(f"Failed to start background thread for contact {contact_id}: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Continue without background processing - don't fail the webhook
        
        # CRITICAL: Ensure immediate response by adding minimal delay to prevent race conditions
        import time
        time.sleep(0.001)  # 1ms delay to ensure background thread is fully started
        
        # Return immediate response - this is critical for GHL
        response_data = {
            'status': 'success',
            'message': 'Webhook received and message added to batch',
            'contact_id': contact_id,
            'processing': {
                'type': 'batched',
                'message': f'Message added to batch, will process in {chat_processor.get_batch_wait_time()} seconds if no more messages',
                'batch_wait_time': chat_processor.get_batch_wait_time()
            },
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"Preparing response for contact {contact_id}")
        response = jsonify(response_data)
        logger.info(f"Response prepared successfully for contact {contact_id}")
        
        logger.info(f"Returning immediate response for contact {contact_id}")
        return response, 200
        
    except Exception as e:
        logger.error(f"=== CRITICAL WEBHOOK ERROR ===")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        
        # Always return a response, never let the endpoint hang or crash
        try:
            return jsonify({
                'status': 'error',
                'message': f'Server error: {str(e)}',
                'error_type': 'critical_error',
                'timestamp': datetime.now().isoformat()
            }), 500
        except Exception as response_error:
            logger.error(f"Even error response failed: {str(response_error)}")
            # Last resort - return plain text
            return f"Server Error: {str(e)}", 500

@webhook_bp.route('/queue-status', methods=['GET'])
def queue_status():
    """Check the status of message batching"""
    try:
        active_batches = chat_processor.get_active_batches()
        return jsonify({
            'status': 'success',
            'active_batches': len(active_batches),
            'batch_details': active_batches,
            'batch_wait_time': chat_processor.get_batch_wait_time(),
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Error getting batch status: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@webhook_bp.route('/batch-debug', methods=['GET'])
def batch_debug():
    """Get detailed debugging information about batches and timers"""
    try:
        timer_status = chat_processor.get_timer_status()
        batch_status = chat_processor.get_batch_status()
        
        return jsonify({
            'status': 'success',
            'timers': {
                'count': len(timer_status),
                'details': timer_status
            },
            'batches': {
                'count': len(batch_status),
                'details': batch_status
            },
            'batch_wait_time': chat_processor.get_batch_wait_time(),
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Error getting batch debug info: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500



@webhook_bp.route('/server-status', methods=['GET'])
def server_status():
    """Check if the server is responsive and healthy"""
    try:
        import threading
        
        # Get thread info WITHOUT cleaning up (to prevent thread creation)
        thread_info = {}
        for thread in threading.enumerate():
            thread_info[thread.name] = {
                'ident': thread.ident,
                'daemon': thread.daemon,
                'alive': thread.is_alive()
            }
        
        # Get contact processing info
        with processing_lock:
            contacts_processing = list(contacts_being_processed)
        
        # Get tracked background threads info
        with thread_tracking_lock:
            tracked_threads = {}
            for contact_id, thread_info in background_threads.items():
                tracked_threads[contact_id] = {
                    'name': thread_info['name'],
                    'alive': thread_info['thread'].is_alive(),
                    'age_seconds': round(time.time() - thread_info['start_time'], 1)
                }
        
        test_time = datetime.now().isoformat()
        return jsonify({
            'status': 'healthy',
            'server_time': test_time,
            'message': 'Server is responsive',
            'threads': {
                'total_count': threading.active_count(),
                'main_thread_alive': threading.main_thread().is_alive(),
                'details': thread_info
            },
            'contacts_processing': {
                'count': len(contacts_processing),
                'list': contacts_processing
            },
            'tracked_background_threads': {
                'count': len(tracked_threads),
                'details': tracked_threads
            }
        }), 200
    except Exception as e:
        logger.error(f"Server status check failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@webhook_bp.route('/emergency-cleanup', methods=['POST'])
def emergency_cleanup():
    """Emergency cleanup to unstick the server"""
    try:
        import threading
        
        # Clear all contacts being processed
        with processing_lock:
            contacts_processing = list(contacts_being_processed)
            contacts_being_processed.clear()
        
        # Force cleanup of chat processor
        try:
            chat_processor.cleanup_all_batches()
        except Exception as e:
            logger.error(f"Chat processor cleanup failed: {str(e)}")
        
        return jsonify({
            'status': 'success',
            'message': 'Emergency cleanup completed',
            'cleared_contacts': contacts_processing,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Emergency cleanup failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Emergency cleanup failed: {str(e)}'
        }), 500

def handle_contact_reply(data):
    """
    Handle contact reply webhook from GHL
    """
    try:
        # Extract relevant information from the webhook data
        contact_id = data.get('contact', {}).get('id')
        message = data.get('message', {})
        
        logger.info(f"Processing contact reply for contact ID: {contact_id}")
        
        # Example: Use GHL API to get more contact details
        if GHL_API_KEY and contact_id:
            logger.info(f"Using GHL API key: {GHL_API_KEY[:10]}...")
            # You can make API calls to GHL here using the API key
        
        # Example: Store data in Supabase
        if SUPABASE_URL and SUPABASE_ANON_KEY:
            logger.info(f"Using Supabase URL: {SUPABASE_URL}")
            # You can store webhook data in Supabase here
        
        # Add your business logic here
        # For example:
        # - Update contact status
        # - Send notifications
        # - Process the reply
        
        return jsonify({
            'status': 'success',
            'message': 'Contact reply processed successfully',
            'contact_id': contact_id,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error handling contact reply: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to process contact reply: {str(e)}'
        }), 500

def handle_contact_created(data):
    """
    Handle contact creation webhook from GHL
    """
    try:
        contact_id = data.get('contact', {}).get('id')
        contact_info = data.get('contact', {})
        
        logger.info(f"Processing new contact creation: {contact_id}")
        
        # Example: Use GHL API to get more contact details
        if GHL_API_KEY and contact_id:
            logger.info(f"Using GHL API key: {GHL_API_KEY[:10]}...")
            # You can make API calls to GHL here
        
        # Example: Store new contact in Supabase
        if SUPABASE_URL and SUPABASE_ANON_KEY:
            logger.info(f"Using Supabase URL: {SUPABASE_URL}")
            # You can store new contact data in Supabase here
        
        # Add your business logic here
        # For example:
        # - Welcome email
        # - Initial setup
        # - Database logging
        
        return jsonify({
            'status': 'success',
            'message': 'Contact creation processed successfully',
            'contact_id': contact_id,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error handling contact creation: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to process contact creation: {str(e)}'
        }), 500



# Configuration endpoint to check API setup
@webhook_bp.route('/config', methods=['GET'])
def check_config():
    """
    Check if API keys are properly configured
    """
    config_status = {
        'ghl_api_key': '✅ Configured' if GHL_API_KEY else '❌ Missing',
        'ghl_location_id': '✅ Configured' if GHL_LOCATION_ID else '❌ Missing',
        'supabase_url': '✅ Configured' if SUPABASE_URL else '❌ Missing',
        'supabase_key': '✅ Configured' if SUPABASE_ANON_KEY else '❌ Missing',
        'openai_api_key': '✅ Configured' if openai_handler.is_configured() else '❌ Missing',
        'openai_model': openai_handler.model if openai_handler.is_configured() else 'Not configured',
        'batch_wait_time': f'{chat_processor.get_batch_wait_time()} seconds'
    }
    
    return jsonify({
        'status': 'success',
        'message': 'Configuration check',
        'config': config_status,
        'timestamp': datetime.now().isoformat()
    })



# Batch management endpoints






@webhook_bp.route('/cleanup-batches', methods=['POST'])
def cleanup_batches():
    """
    Clean up all active batches and timers - useful for debugging stuck timers
    """
    try:
        success = chat_processor.cleanup_all_batches()
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'All batches and timers cleaned up successfully',
                'timestamp': datetime.now().isoformat()
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to cleanup batches',
                'timestamp': datetime.now().isoformat()
            }), 500
            
    except Exception as e:
        logger.error(f"Error cleaning up batches: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Cleanup failed: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500

@webhook_bp.route('/timer-status', methods=['GET'])
def timer_status():
    """
    Get detailed status of all timer threads for debugging
    """
    try:
        timer_status = chat_processor.get_timer_status()
        return jsonify({
            'status': 'success',
            'timer_status': timer_status,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting timer status: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to get timer status: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500

@webhook_bp.route('/debug-threads', methods=['GET'])
def debug_threads():
    """Debug endpoint to identify thread leak sources"""
    try:
        import threading
        import traceback
        
        # Get all threads with stack traces
        thread_debug = {}
        for thread in threading.enumerate():
            # Get thread info
            thread_info = {
                'ident': thread.ident,
                'daemon': thread.daemon,
                'alive': thread.is_alive(),
                'name': thread.name
            }
            
            # Try to get stack trace for non-main threads
            if thread != threading.main_thread():
                try:
                    # This might not work in all Python versions, but worth trying
                    if hasattr(thread, '_target'):
                        thread_info['target'] = str(thread._target)
                    if hasattr(thread, '_args'):
                        thread_info['args'] = str(thread._args)
                except Exception as e:
                    thread_info['target_error'] = str(e)
            
            thread_debug[thread.name] = thread_info
        
        # Get chat processor thread info
        chat_processor_info = {}
        try:
            if hasattr(chat_processor, 'batch_threads'):
                chat_processor_info['batch_threads'] = len(chat_processor.batch_threads)
                chat_processor_info['batch_thread_names'] = list(chat_processor.batch_threads.keys())
            if hasattr(chat_processor, '_cleanup_thread_started'):
                chat_processor_info['cleanup_started'] = chat_processor._cleanup_thread_started
        except Exception as e:
            chat_processor_info['error'] = str(e)
        
        return jsonify({
            'status': 'success',
            'thread_count': threading.active_count(),
            'threads': thread_debug,
            'chat_processor': chat_processor_info,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Debug threads failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
