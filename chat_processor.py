import logging
from datetime import datetime, timedelta
from typing import Dict, List
import requests
import os
import threading
import time
from openai_handler import openai_handler
from system_prompts import get_system_prompt

# Configure logging
logger = logging.getLogger(__name__)

# Get Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')

# GHL API configuration
GHL_API_KEY = os.getenv('GHL_API_KEY')
GHL_API_URL = 'https://services.leadconnectorhq.com/conversations/messages'
GHL_API_VERSION = '2021-04-15'

# Message batching configuration
MESSAGE_BATCH_WAIT_TIME = int(os.getenv('MESSAGE_BATCH_WAIT_TIME', 5))  # seconds
MESSAGE_BATCH_CHECK_INTERVAL = 5  # seconds - how often to check for batch completion

class ChatProcessor:
    """
    Handles AI responses to SMS messages using message batching for better context
    """
    
    def __init__(self):
        self.active_batches = {}  # contact_id -> batch_info
        self.batch_locks = {}  # contact_id -> threading.Lock
        self.batch_threads = {}  # contact_id -> threading.Thread
        
        # Concurrency control
        self.max_concurrent_batches = int(os.getenv('MAX_CONCURRENT_BATCHES', 50))
        self.cleanup_interval = int(os.getenv('CLEANUP_INTERVAL', 300))  # 5 minutes
        
        # Start cleanup timer (disabled to prevent blocking)
        # self._start_cleanup_timer()
        
        logger.info(f"ChatProcessor initialized with max {self.max_concurrent_batches} concurrent batches, cleanup disabled to prevent blocking")
    
    def _start_cleanup_timer(self):
        """Start a background timer to periodically clean up inactive batches."""
        def cleanup_task():
            while True:
                try:
                    logger.info(f"Running cleanup task. Current active batches: {len(self.active_batches)}")
                    self._cleanup_completed_threads()
                    logger.info(f"Cleanup task completed. Waiting for {self.cleanup_interval} seconds.")
                    time.sleep(self.cleanup_interval)
                except Exception as e:
                    logger.error(f"Error in cleanup task: {str(e)}")
                    # Shorter sleep on error to prevent long blocking
                    time.sleep(30)
                except KeyboardInterrupt:
                    logger.info("Cleanup task interrupted, stopping...")
                    break

        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True, name="CleanupTask")
        cleanup_thread.start()
        logger.info(f"Cleanup timer started. Will run every {self.cleanup_interval} seconds.")
    
    def manual_cleanup(self):
        """Manually run cleanup to remove completed threads and old batches"""
        try:
            logger.info("Running manual cleanup...")
            self._cleanup_completed_threads()
            logger.info("Manual cleanup completed")
        except Exception as e:
            logger.error(f"Error in manual cleanup: {str(e)}")
    
    def force_cleanup_stuck_locks(self):
        """Force cleanup of stuck locks that might be causing deadlocks"""
        try:
            logger.info("Force cleaning up stuck locks...")
            stuck_contacts = []
            
            # Check for stuck locks
            for contact_id, lock in self.batch_locks.items():
                try:
                    # Try to acquire lock with very short timeout
                    if lock.acquire(timeout=0.1):
                        lock.release()
                    else:
                        stuck_contacts.append(contact_id)
                except:
                    stuck_contacts.append(contact_id)
            
            # Force cleanup stuck contacts
            for contact_id in stuck_contacts:
                try:
                    logger.warning(f"Force cleaning stuck contact: {contact_id}")
                    if contact_id in self.active_batches:
                        del self.active_batches[contact_id]
                    if contact_id in self.batch_threads:
                        del self.batch_threads[contact_id]
                    if contact_id in self.batch_locks:
                        del self.batch_locks[contact_id]
                except:
                    pass
            
            logger.info(f"Force cleanup completed, removed {len(stuck_contacts)} stuck contacts")
            return len(stuck_contacts)
        except Exception as e:
            logger.error(f"Error in force cleanup: {str(e)}")
            return 0
    
    def force_cleanup_all_threads(self):
        """Force cleanup all threads and batches - nuclear option"""
        try:
            logger.warning("FORCE CLEANUP: Removing all threads and batches")
            
            # Clear all batches
            batch_count = len(self.active_batches)
            self.active_batches.clear()
            
            # Clear all threads
            thread_count = len(self.batch_threads)
            self.batch_threads.clear()
            
            # Clear all locks
            lock_count = len(self.batch_locks)
            self.batch_locks.clear()
            
            logger.warning(f"FORCE CLEANUP completed: {batch_count} batches, {thread_count} threads, {lock_count} locks removed")
            return batch_count + thread_count + lock_count
        except Exception as e:
            logger.error(f"Error in force cleanup all: {str(e)}")
            return 0
    
    def _cleanup_completed_threads(self):
        """Remove completed threads and old batches"""
        try:
            # Remove completed threads
            completed_contacts = [
                contact_id for contact_id, thread in self.batch_threads.items()
                if not thread.is_alive()
            ]
            for contact_id in completed_contacts:
                if contact_id in self.batch_threads:
                    del self.batch_threads[contact_id]
                logger.debug(f"Removed completed thread for contact {contact_id}")
            
            # Remove old batches (older than 1 hour)
            current_time = datetime.utcnow()
            old_batches = [
                contact_id for contact_id, batch in self.active_batches.items()
                if (current_time - batch['start_time']).total_seconds() > 3600
            ]
            for contact_id in old_batches:
                if contact_id in self.active_batches:
                    del self.active_batches[contact_id]
                if contact_id in self.batch_locks:
                    del self.batch_locks[contact_id]
                logger.debug(f"Removed old batch for contact {contact_id}")
            
            # Log cleanup results
            if completed_contacts or old_batches:
                logger.info(f"Cleanup completed: removed {len(completed_contacts)} completed threads, {len(old_batches)} old batches")
                
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
        
    def send_message_to_ghl(self, contact_id: str, message: str) -> bool:
        """
        Send message to GHL using their API
        """
        try:
            thread_id = threading.current_thread().ident
            logger.info(f"[GHL_SEND] Thread {thread_id} starting GHL send for contact {contact_id}")
            
            if not GHL_API_KEY:
                logger.error(f"[GHL_SEND] Thread {thread_id} GHL API key not configured")
                return False
            
            # Prepare the GHL API request
            logger.info(f"[GHL_SEND] Thread {thread_id} preparing GHL API request for contact {contact_id}")
            ghl_data = {
                "type": "SMS",
                "contactId": contact_id,
                "message": message
            }
            
            headers = {
                'Accept': 'application/json',
                'Authorization': f'Bearer {GHL_API_KEY}',
                'Content-Type': 'application/json',
                'Version': GHL_API_VERSION
            }
            
            # Send message to GHL with shorter timeout to prevent hanging
            logger.info(f"[GHL_SEND] Thread {thread_id} attempting to send message to GHL for contact {contact_id}")
            response = requests.post(GHL_API_URL, json=ghl_data, headers=headers, timeout=5)
            logger.info(f"[GHL_SEND] Thread {thread_id} GHL API call completed for contact {contact_id}")
            
            if response.status_code in [200, 201]:
                logger.info(f"[GHL_SEND] Thread {thread_id} message sent to GHL successfully for contact {contact_id}")
                return True
            else:
                logger.error(f"[GHL_SEND] Thread {thread_id} failed to send message to GHL: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            thread_id = threading.current_thread().ident
            logger.error(f"[GHL_SEND] Thread {thread_id} GHL API timeout for contact {contact_id} - request took longer than 5 seconds")
            return False
        except requests.exceptions.ConnectionError:
            thread_id = threading.current_thread().ident
            logger.error(f"[GHL_SEND] Thread {thread_id} GHL API connection error for contact {contact_id} - network issue")
            return False
        except Exception as e:
            thread_id = threading.current_thread().ident
            logger.error(f"[GHL_SEND] Thread {thread_id} error sending message to GHL for contact {contact_id}: {str(e)}")
            return False

    def get_batch_wait_time(self) -> int:
        """Get the current batch wait time in seconds"""
        return MESSAGE_BATCH_WAIT_TIME
    
    def set_batch_wait_time(self, seconds: int):
        """Set the batch wait time in seconds"""
        global MESSAGE_BATCH_WAIT_TIME
        MESSAGE_BATCH_WAIT_TIME = seconds
        logger.info(f"Message batch wait time updated to {seconds} seconds")
    
    def start_message_batch(self, contact_id: str, message_body: str, sourceforai: str = None):
        """
        Start or extend a message batch for a contact
        """
        try:
            # Check if we're at capacity
            if len(self.active_batches) >= self.max_concurrent_batches:
                logger.warning(f"Maximum concurrent batches reached ({self.max_concurrent_batches}), rejecting new batch for {contact_id}")
                return False
            
            # Ensure we have a lock for this contact
            if contact_id not in self.batch_locks:
                self.batch_locks[contact_id] = threading.Lock()
            
            with self.batch_locks[contact_id]:
                current_time = datetime.utcnow()
                
                if contact_id in self.active_batches:
                    # Extend existing batch - add message but DON'T restart timer
                    batch_info = self.active_batches[contact_id]
                    batch_info['last_message_time'] = current_time
                    batch_info['message_count'] += 1
                    batch_info['messages'].append(message_body)
                    
                    # Calculate time remaining
                    time_elapsed = (current_time - batch_info['start_time']).total_seconds()
                    time_remaining = max(0, MESSAGE_BATCH_WAIT_TIME - time_elapsed)
                    
                    logger.info(f"Extended batch for {contact_id}: {batch_info['message_count']} messages ({time_remaining:.1f}s remaining)")
                else:
                    # Start new batch
                    batch_info = {
                        'start_time': current_time,
                        'last_message_time': current_time,
                        'message_count': 1,
                        'messages': [message_body],
                        'batch_id': f"batch_{contact_id}_{int(current_time.timestamp())}",
                        'timer_started': True,
                        'sourceforai': sourceforai
                    }
                    self.active_batches[contact_id] = batch_info
                    logger.info(f"Started new batch for {contact_id}: '{message_body[:30]}...' ({MESSAGE_BATCH_WAIT_TIME}s timer)")
                    
                    # Start batch timer in background
                    self._start_batch_timer(contact_id, batch_info)
                
            return True
                
        except Exception as e:
            logger.error(f"Error starting message batch for contact {contact_id}: {str(e)}")
            return False
    
    def _start_batch_timer(self, contact_id: str, batch_info: Dict):
        """
        Start a timer to process the batch after the wait period
        """
        try:
            # Don't start multiple timers for the same contact
            if contact_id in self.batch_threads:
                logger.warning(f"Timer already running for {contact_id}, skipping duplicate")
                return
            
            def batch_timer():
                try:
                    # Wait for the full batch wait time
                    time.sleep(MESSAGE_BATCH_WAIT_TIME)
                    
                    logger.info(f"Batch timer expired for {contact_id}, processing batch")
                    
                    # Process the batch with timeout protection
                    try:
                        start_time = time.time()
                        self._process_message_batch(contact_id, batch_info)
                        processing_time = time.time() - start_time
                        logger.info(f"Batch processed for {contact_id} in {processing_time:.2f}s")
                            
                    except Exception as process_error:
                        logger.error(f"Batch processing error for {contact_id}: {str(process_error)}")
                        # Force cleanup on processing error
                        try:
                            if contact_id in self.active_batches:
                                del self.active_batches[contact_id]
                        except Exception:
                            pass
                    
                except Exception as e:
                    logger.error(f"Batch timer error for {contact_id}: {str(e)}")
                finally:
                    # Clean up thread reference
                    try:
                        if contact_id in self.batch_threads:
                            del self.batch_threads[contact_id]
                    except Exception:
                        pass
            
            # Start timer thread
            timer_thread = threading.Thread(target=batch_timer, daemon=True, name=f"BatchTimer-{contact_id}")
            timer_thread.start()
            self.batch_threads[contact_id] = timer_thread
            
        except Exception as e:
            logger.error(f"Error starting batch timer for contact {contact_id}: {str(e)}")
    
    def _process_message_batch(self, contact_id: str, batch_info: Dict):
        """
        Process a complete message batch
        """
        try:
            # Combine all messages in the batch
            combined_message = " ".join(batch_info['messages'])
            logger.info(f"Processing batch for {contact_id}: '{combined_message[:50]}...' ({batch_info['message_count']} messages)")
            
            # Get chat history for context and format for OpenAI
            messages = self.get_chat_history(contact_id, limit=20)
            previous_messages = messages if messages else []
            sourceforai = batch_info.get('sourceforai')
            openai_messages = self.format_messages_for_openai(previous_messages, combined_message, sourceforai)
            
            # Process with OpenAI
            if openai_handler.is_configured():
                try:
                    
                    # Generate AI response
                    response_result = openai_handler.generate_chat_response(openai_messages)
                    
                    if response_result.get('response'):
                        ai_response = response_result['response']
                        logger.info(f"AI response for {contact_id}: {ai_response[:50]}...")
                        
                        # Store the AI response in Supabase
                        try:
                            self.store_ai_response(contact_id, ai_response, response_result)
                            logger.info(f"AI response stored and sent for {contact_id}")
                        except Exception as e:
                            logger.error(f"Failed to store AI response for {contact_id}: {str(e)}")
                    else:
                        logger.error(f"Failed to generate AI response for {contact_id}")
                        
                except Exception as e:
                    logger.error(f"OpenAI processing failed for contact {contact_id}: {str(e)}")
            else:
                logger.warning("OpenAI not configured, skipping AI processing")
            
            
            # Clean up the processed batch (non-blocking)
            thread_id = threading.current_thread().ident
            logger.info(f"[PROCESS_CLEANUP] Thread {thread_id} starting cleanup for contact {contact_id}")
            try:
                # Try to acquire lock with timeout to prevent deadlock
                if contact_id in self.batch_locks:
                    logger.info(f"[PROCESS_CLEANUP] Thread {thread_id} attempting to acquire lock for contact {contact_id}")
                    lock_acquired = self.batch_locks[contact_id].acquire(timeout=1.0)
                    if lock_acquired:
                        logger.info(f"[PROCESS_CLEANUP] Thread {thread_id} lock acquired for contact {contact_id}")
                        try:
                            if contact_id in self.active_batches:
                                del self.active_batches[contact_id]
                                logger.info(f"[PROCESS_CLEANUP] Thread {thread_id} batch processed and cleaned up for contact {contact_id}")
                        finally:
                            self.batch_locks[contact_id].release()
                            logger.info(f"[PROCESS_CLEANUP] Thread {thread_id} lock released for contact {contact_id}")
                    else:
                        # Lock timeout - force cleanup without lock
                        logger.warning(f"[PROCESS_CLEANUP] Thread {thread_id} lock timeout for contact {contact_id}, forcing cleanup")
                        if contact_id in self.active_batches:
                            del self.active_batches[contact_id]
                            logger.info(f"[PROCESS_CLEANUP] Thread {thread_id} batch force cleaned up for contact {contact_id}")
                else:
                    # No lock exists, just clean up
                    logger.info(f"[PROCESS_CLEANUP] Thread {thread_id} no lock exists for contact {contact_id}, cleaning up directly")
                    if contact_id in self.active_batches:
                        del self.active_batches[contact_id]
                        logger.info(f"[PROCESS_CLEANUP] Thread {thread_id} batch cleaned up for contact {contact_id} (no lock)")
            except Exception as cleanup_error:
                logger.error(f"[PROCESS_CLEANUP] Thread {thread_id} error during batch cleanup for contact {contact_id}: {str(cleanup_error)}")
                # Force cleanup even on error
                try:
                    if contact_id in self.active_batches:
                        del self.active_batches[contact_id]
                        logger.info(f"[PROCESS_CLEANUP] Thread {thread_id} emergency batch cleanup for contact {contact_id}")
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error processing message batch for contact {contact_id}: {str(e)}")
            # Ensure cleanup happens even on error (non-blocking)
            try:
                if contact_id in self.active_batches:
                    del self.active_batches[contact_id]
                    logger.info(f"Emergency cleanup of failed batch for contact {contact_id}")
                # Also clean up the lock if it exists
                if contact_id in self.batch_locks:
                    try:
                        self.batch_locks[contact_id].release()
                    except:
                        pass
                    del self.batch_locks[contact_id]
            except Exception as emergency_cleanup_error:
                logger.error(f"Emergency cleanup failed for contact {contact_id}: {str(emergency_cleanup_error)}")
                # Force cleanup even if there's an error
                try:
                    if contact_id in self.active_batches:
                        del self.active_batches[contact_id]
                    if contact_id in self.batch_locks:
                        del self.batch_locks[contact_id]
                except:
                    pass
    
    def get_active_batches(self) -> Dict:
        """Get information about active message batches"""
        try:
            batch_info = {}
            current_time = datetime.utcnow()
            
            for contact_id, batch in self.active_batches.items():
                # Calculate time remaining based on when the timer started
                # The timer starts when the first message arrives, so we calculate from start_time
                time_elapsed = (current_time - batch['start_time']).total_seconds()
                time_remaining = max(0, MESSAGE_BATCH_WAIT_TIME - time_elapsed)
                
                batch_info[contact_id] = {
                    'batch_id': batch['batch_id'],
                    'start_time': batch['start_time'].isoformat(),
                    'last_message_time': batch['last_message_time'].isoformat(),
                    'message_count': batch['message_count'],
                    'messages': batch['messages'],
                    'time_elapsed': round(time_elapsed, 1),
                    'time_remaining': round(time_remaining, 1),
                    'timer_active': contact_id in self.batch_threads
                }
            return batch_info
        except Exception as e:
            logger.error(f"Error getting active batches: {str(e)}")
            return {}
    
    def force_process_batch(self, contact_id: str):
        """Force process a batch immediately without waiting"""
        try:
            with self.batch_locks[contact_id]:
                if contact_id in self.active_batches:
                    batch_info = self.active_batches[contact_id]
                    logger.info(f"Force processing batch for contact {contact_id}")
                    self._process_message_batch(contact_id, batch_info)
                    return True
                else:
                    logger.warning(f"No active batch found for contact {contact_id}")
                    return False
        except Exception as e:
            logger.error(f"Error force processing batch for contact {contact_id}: {str(e)}")
            return False
    
    def get_chat_history(self, contact_id: str, limit: int = 20) -> List[Dict]:
        """
        Retrieve chat history from Supabase for a specific contact
        """
        try:
            if not SUPABASE_URL or not SUPABASE_ANON_KEY:
                logger.error("Supabase credentials not configured")
                return []
            
            # Get messages from Supabase
            messages_url = f"{SUPABASE_URL}/rest/v1/messages"
            headers = {
                'apikey': SUPABASE_ANON_KEY,
                'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
                'Content-Type': 'application/json'
            }
            
            params = {
                'contact_id': f'eq.{contact_id}',
                'order': 'created_at.asc',  # Chronological order for conversation flow
                'limit': limit
            }
            
            # Add timeout to prevent hanging
            response = requests.get(messages_url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                messages = response.json()
                logger.info(f"Retrieved {len(messages)} messages for contact {contact_id}")
                return messages
            else:
                logger.error(f"Failed to retrieve chat history: {response.status_code} - {response.text}")
                return []
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout retrieving chat history for contact {contact_id}")
            return []
        except Exception as e:
            logger.error(f"Error retrieving chat history: {str(e)}")
            return []
    
    def format_messages_for_openai(self, messages: List[Dict], new_message: str, sourceforai: str = None) -> List[Dict]:
        """
        Convert Supabase message history to OpenAI chat completions format
        Returns: [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, ...]
        """
        openai_messages = []
        
        # Add system message based on sourceforai field
        system_prompt = get_system_prompt(sourceforai)
        logger.info(f"Using system prompt for sourceforai: {sourceforai or 'default'}")
        
        system_message = {
            "role": "system",
            "content": system_prompt
        }

        openai_messages.append(system_message)
        
        # Convert Supabase messages to OpenAI format
        for message in messages:
            message_type = message.get('message_type', '')
            message_body = message.get('message_body', '')
            
            if message_body:
                if message_type == 'AI_RESPONSE':
                    # AI responses become 'assistant' role
                    openai_messages.append({
                        "role": "assistant",
                        "content": message_body
                    })
                elif message_type == 'SMS' or message_type is None:
                    # SMS messages become 'user' role
                    openai_messages.append({
                        "role": "user",
                        "content": message_body
                    })
                # Skip other message types
        
        # Add the new incoming message as 'user' role only if it's not already in the history
        # Check if the last message in history is the same as the new message
        if not messages or messages[-1].get('message_body', '') != new_message:
            openai_messages.append({
                "role": "user",
                "content": new_message
            })
        
        logger.info(f"Formatted {len(openai_messages)} messages for OpenAI (including system message)")
        return openai_messages
    
    def store_ai_response(self, contact_id: str, ai_response: str, response_metadata: Dict):
        """
        Store AI response in Supabase
        """
        try:
            if not SUPABASE_URL or not SUPABASE_ANON_KEY:
                logger.error("Supabase credentials not configured")
                return False
            
            # Prepare data for Supabase
            supabase_data = {
                'contact_id': contact_id,
                'message_body': ai_response,
                'message_type': 'AI_RESPONSE',
                'created_at': datetime.utcnow().isoformat() + 'Z',  # Use UTC time with Z suffix
                'metadata': {
                    'model': response_metadata.get('model', ''),
                    'tokens_used': response_metadata.get('tokens_used', 0),
                    'response_type': 'ai_generated'
                }
            }
            
            # Insert into messages table
            messages_url = f"{SUPABASE_URL}/rest/v1/messages"
            headers = {
                'apikey': SUPABASE_ANON_KEY,
                'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(messages_url, json=supabase_data, headers=headers, timeout=5)
            
            if response.status_code in [200, 201]:
                logger.info(f"AI response for contact {contact_id} stored in Supabase successfully")
                
                # Now send the AI response to GoHighLevel
                try:
                    thread_id = threading.current_thread().ident
                    logger.info(f"[STORE_GHL] Thread {thread_id} sending AI response to GoHighLevel for contact {contact_id}")
                    ghl_sent = self.send_message_to_ghl(contact_id, ai_response)
                    if ghl_sent:
                        logger.info(f"[STORE_GHL] Thread {thread_id} AI response sent to GoHighLevel successfully for contact {contact_id}")
                    else:
                        logger.error(f"[STORE_GHL] Thread {thread_id} failed to send AI response to GoHighLevel for contact {contact_id}")
                except Exception as e:
                    logger.error(f"[STORE_GHL] Thread {thread_id} error sending AI response to GoHighLevel for contact {contact_id}: {str(e)}")
                
                return True
            else:
                logger.error(f"Failed to store AI response in Supabase: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error storing AI response: {str(e)}")
            return False
    
    def cleanup_all_batches(self):
        """Clean up all active batches and timers - useful for debugging"""
        try:
            logger.info("Cleaning up all active batches and timers")
            with threading.Lock():  # Use a temporary lock for cleanup
                # Clear all batches
                self.active_batches.clear()
                
                # Clear all timer references
                self.batch_threads.clear()
                
                # Clear all locks
                self.batch_locks.clear()
                
            logger.info("All batches and timers cleaned up successfully")
            return True
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
            return False
    
    def get_timer_status(self) -> Dict:
        """Get detailed status of all timers for debugging"""
        try:
            timer_status = {}
            for contact_id, timer_thread in self.batch_threads.items():
                timer_status[contact_id] = {
                    'is_alive': timer_thread.is_alive(),
                    'name': timer_thread.name,
                    'daemon': timer_thread.daemon,
                    'ident': timer_thread.ident
                }
            return timer_status
        except Exception as e:
            logger.error(f"Error getting timer status: {str(e)}")
            return {}
    
    def get_batch_status(self) -> Dict:
        """Get detailed status of all active batches for debugging"""
        try:
            batch_status = {}
            for contact_id, batch_info in self.active_batches.items():
                batch_status[contact_id] = {
                    'start_time': str(batch_info.get('start_time', 'unknown')),
                    'message_count': batch_info.get('message_count', 0),
                    'timer_started': batch_info.get('timer_started', False),
                    'has_lock': contact_id in self.batch_locks
                }
            return batch_status
        except Exception as e:
            logger.error(f"Error getting batch status: {str(e)}")
            return {}

# Create a global instance
chat_processor = ChatProcessor()
