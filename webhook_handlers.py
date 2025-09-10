from flask import Blueprint, request, jsonify
import logging
import os
import threading
import time
from datetime import datetime
import requests
from openai_handler import openai_handler
from chat_processor import chat_processor
from system_prompts import get_first_message

# Import the new logging functions
from supabase_logger import (
    info_with_context, 
    error_with_context, 
    warning_with_context,
    debug_with_context
)

# Configure basic logging (will be overridden by main server)
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

# Message deduplication - track recent messages by hash to prevent duplicates
recent_messages = {}  # contact_id -> {message_hash: timestamp}
message_dedup_lock = threading.Lock()
MESSAGE_DEDUP_WINDOW = 300  # 5 minutes in seconds

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
        error_with_context(
            f"Error marking contact {contact_id} as processing: {str(e)}",
            contact_id=contact_id,
            operation="mark_contact_processing"
        )

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

def is_duplicate_message(contact_id, message_body):
    """
    Check if this message is a duplicate based on content hash within time window
    
    Args:
        contact_id (str): The contact ID
        message_body (str): The message content to check
        
    Returns:
        bool: True if this is a duplicate message, False otherwise
    """
    if not message_body or not message_body.strip():
        return False
    
    import hashlib
    import time
    
    try:
        # Create hash of message content (normalized)
        normalized_message = message_body.strip().lower()
        message_hash = hashlib.md5(normalized_message.encode()).hexdigest()
        current_time = time.time()
        
        with message_dedup_lock:
            # Clean up old entries first
            if contact_id in recent_messages:
                # Remove messages older than the deduplication window
                old_hashes = []
                for msg_hash, timestamp in recent_messages[contact_id].items():
                    if current_time - timestamp > MESSAGE_DEDUP_WINDOW:
                        old_hashes.append(msg_hash)
                
                for old_hash in old_hashes:
                    del recent_messages[contact_id][old_hash]
                
                # If no recent messages left, remove the contact entry
                if not recent_messages[contact_id]:
                    del recent_messages[contact_id]
            
            # Check if this message hash exists for this contact
            if contact_id in recent_messages:
                if message_hash in recent_messages[contact_id]:
                    time_since_last = current_time - recent_messages[contact_id][message_hash]
                    logger.warning(f"Duplicate message detected for contact {contact_id}: '{message_body[:50]}...' (last seen {time_since_last:.1f}s ago)")
                    return True
            
            # Add this message to the tracking
            if contact_id not in recent_messages:
                recent_messages[contact_id] = {}
            recent_messages[contact_id][message_hash] = current_time
            
            logger.debug(f"Message recorded for contact {contact_id}: hash {message_hash[:8]}...")
            return False
            
    except Exception as e:
        logger.error(f"Error checking for duplicate message: {str(e)}")
        # On error, don't block the message - let it through
        return False

def clean_old_message_hashes():
    """Clean up old message hashes to prevent memory growth"""
    try:
        import time
        current_time = time.time()
        
        with message_dedup_lock:
            contacts_to_remove = []
            
            for contact_id in list(recent_messages.keys()):
                # Clean old messages for this contact
                old_hashes = []
                for msg_hash, timestamp in recent_messages[contact_id].items():
                    if current_time - timestamp > MESSAGE_DEDUP_WINDOW:
                        old_hashes.append(msg_hash)
                
                for old_hash in old_hashes:
                    del recent_messages[contact_id][old_hash]
                
                # If no messages left, mark contact for removal
                if not recent_messages[contact_id]:
                    contacts_to_remove.append(contact_id)
            
            # Remove contacts with no recent messages
            for contact_id in contacts_to_remove:
                del recent_messages[contact_id]
            
            logger.debug(f"Message hash cleanup complete. Tracking {len(recent_messages)} contacts")
            
    except Exception as e:
        logger.error(f"Error during message hash cleanup: {str(e)}")

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
                info_with_context(
            f"Cleaned up dead background thread for contact {contact_id}",
            contact_id=contact_id,
            operation="cleanup_dead_threads"
        )
        
        # Get all threads
        all_threads = threading.enumerate()
        dead_threads = []
        
        for thread in all_threads:
            if not thread.is_alive() and thread != threading.main_thread():
                dead_threads.append(thread.name)
        
        if dead_threads:
            info_with_context(
            f"Found {len(dead_threads)} dead threads: {dead_threads}",
            operation="cleanup_dead_threads"
        )
            
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

def store_first_message_in_supabase(contact_id, first_message):
    """
    Store the first message from GHL custom field in Supabase (only once per contact)
    """
    try:
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            logger.error("Supabase credentials not configured")
            return False
        
        if not first_message or not first_message.strip():
            logger.warning(f"No first message provided for contact {contact_id}")
            return False
        
        # Check if first message already exists for this contact
        messages_url = f"{SUPABASE_URL}/rest/v1/messages"
        headers = {
            'apikey': SUPABASE_ANON_KEY,
            'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
            'Content-Type': 'application/json'
        }
        
        # Query to check if first message already exists
        params = {
            'contact_id': f'eq.{contact_id}',
            'message_type': f'eq.AI_RESPONSE',
            'select': 'id,message_body'
        }
        
        check_response = requests.get(messages_url, headers=headers, params=params, timeout=5)
        
        if check_response.status_code == 200:
            existing_messages = check_response.json()
            
            # Check if the first message already exists
            for msg in existing_messages:
                if msg.get('message_body', '').strip() == first_message.strip():
                    logger.info(f"First message already exists for contact {contact_id}, skipping storage")
                    return True
            
            logger.info(f"First message not found for contact {contact_id}, storing it now")
        else:
            logger.warning(f"Could not check existing messages for contact {contact_id}: {check_response.status_code}")
        
        # Store the first message
        current_time = datetime.utcnow().isoformat() + 'Z'
        supabase_data = {
            'contact_id': contact_id,
            'message_body': first_message.strip(),
            'message_type': 'AI_RESPONSE',
            'created_at': current_time
        }
        
        response = requests.post(messages_url, json=supabase_data, headers=headers, timeout=5)
        
        if response.status_code in [200, 201]:
            logger.info(f"First message for contact {contact_id} stored in Supabase successfully")
            return True
        else:
            logger.error(f"Failed to store first message in Supabase: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error(f"Timeout storing first message for contact {contact_id} in Supabase")
        return False
    except Exception as e:
        logger.error(f"Error storing first message in Supabase: {str(e)}")
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
        
        if contact_id and contact_id != 'unknown':
            logger.info(f"Processing webhook for contact {contact_id}")
            
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
            
            # Get first message from system prompts based on sourceforai
            sourceforai = data.get('sourceforai')
            if not sourceforai:
                # Check customData for sourceforai
                custom_data = data.get('customData', {})
                if isinstance(custom_data, dict):
                    sourceforai = custom_data.get('sourceforai')
            
            # Extract contact name from webhook data
            contact_name = data.get('first_name', '')
            if not contact_name:
                # Try alternative name fields
                contact_name = data.get('name', '')
                if not contact_name:
                    # Try full_name and extract first name
                    full_name = data.get('full_name', '')
                    if full_name:
                        contact_name = full_name.split()[0] if full_name.split() else ''
            
            # Get the appropriate first message based on sourceforai and contact name
            first_message = get_first_message(sourceforai, contact_name)
            logger.info(f"Using first message for sourceforai '{sourceforai or 'default'}' and contact '{contact_name or 'unknown'}': {first_message[:100]}...")
            
            # Store the first message in Supabase
            try:
                logger.info(f"Attempting to store first message for {contact_id}")
                first_message_stored = store_first_message_in_supabase(contact_id, first_message)
                logger.info(f"First message storage completed for {contact_id}: {first_message_stored}")
            except Exception as e:
                logger.error(f"First message storage failed for {contact_id}: {str(e)}")
                logger.error(f"Error type: {type(e).__name__}")
                import traceback
                logger.error(f"First message storage traceback: {traceback.format_exc()}")
            
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
                        
                        # Check for duplicate messages before processing
                        if is_duplicate_message(contact_id, message_body):
                            logger.warning(f"Skipping duplicate message for contact {contact_id}: {message_body[:50]}...")
                            return  # Skip processing this duplicate message
                        
                        # Periodically clean up old message hashes (every 10th message roughly)
                        import random
                        if random.randint(1, 10) == 1:
                            try:
                                clean_old_message_hashes()
                            except Exception as cleanup_error:
                                logger.error(f"Error during message hash cleanup: {str(cleanup_error)}")
                        
                        # Use sourceforai already extracted above
                        logger.info(f"Using sourceforai: {sourceforai or 'default'} for contact {contact_id}")
                        
                        # Start or extend message batch for AI processing
                        chat_processor.start_message_batch(contact_id, message_body, sourceforai)
                        
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
        # Get the webhook data
        data = {}
        try:
            if request.is_json:
                data = request.get_json()
            else:
                data = request.form.to_dict()
            
            # Extract key fields for logging
            sourceforai = data.get('sourceforai')
            if not sourceforai:
                custom_data = data.get('customData', {})
                if isinstance(custom_data, dict):
                    sourceforai = custom_data.get('sourceforai')
            
            contact_name = data.get('first_name', '') or data.get('name', '') or (data.get('full_name', '').split()[0] if data.get('full_name') else '')
            
            logger.info(f"Webhook received - Source: {sourceforai or 'default'}, Contact: {contact_name or 'unknown'}")
            
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


