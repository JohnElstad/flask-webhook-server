import logging
import requests
import os
import threading
import queue
import time
from datetime import datetime
from typing import Optional

class SupabaseLogHandler(logging.Handler):
    """
    Custom logging handler that sends logs to Supabase asynchronously
    """
    
    def __init__(self, supabase_url: str, supabase_key: str, table_name: str = 'server_logs', 
                 batch_size: int = 10, flush_interval: float = 5.0):
        super().__init__()
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.table_name = table_name
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        
        self.headers = {
            'apikey': supabase_key,
            'Authorization': f'Bearer {supabase_key}',
            'Content-Type': 'application/json'
        }
        
        # Queue for batching logs
        self.log_queue = queue.Queue()
        self.last_flush = time.time()
        
        # Start background worker thread
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        
    def emit(self, record):
        """
        Add log record to queue (non-blocking)
        """
        try:
            # Prepare log data
            log_data = {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'level': record.levelname,
                'logger_name': record.name,
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line_number': record.lineno,
                'process_id': record.process,
                'thread_id': record.thread,
                'thread_name': record.threadName
            }
            
            # Add exception info if present
            if record.exc_info:
                log_data['exception_type'] = record.exc_info[0].__name__ if record.exc_info[0] else 'Unknown'
                log_data['exception_message'] = str(record.exc_info[1]) if record.exc_info[1] else 'Unknown'
                log_data['traceback'] = self.formatException(record.exc_info)
            
            # Add extra fields if present
            if hasattr(record, 'contact_id'):
                log_data['contact_id'] = record.contact_id
            if hasattr(record, 'webhook_type'):
                log_data['webhook_type'] = record.webhook_type
            if hasattr(record, 'operation'):
                log_data['operation'] = record.operation
            
            # Add to queue (non-blocking)
            try:
                self.log_queue.put_nowait(log_data)
            except queue.Full:
                # Queue is full, log to console as fallback
                print(f"Log queue full, dropping log: {record.getMessage()}")
                
        except Exception as e:
            # Fallback to console if anything fails
            print(f"Error preparing log for Supabase: {str(e)}")
            print(f"Log message: {record.getMessage()}")
    
    def _worker(self):
        """
        Background worker thread that processes logs in batches
        """
        batch = []
        
        while True:
            try:
                # Wait for logs with timeout
                try:
                    log_data = self.log_queue.get(timeout=1.0)
                    batch.append(log_data)
                except queue.Empty:
                    pass
                
                current_time = time.time()
                should_flush = (
                    len(batch) >= self.batch_size or 
                    (batch and current_time - self.last_flush >= self.flush_interval)
                )
                
                if should_flush and batch:
                    self._send_batch(batch)
                    batch = []
                    self.last_flush = current_time
                    
            except Exception as e:
                print(f"Error in log worker thread: {str(e)}")
                time.sleep(1)  # Prevent tight loop on errors
    
    def _send_batch(self, batch):
        """
        Send a batch of logs to Supabase
        """
        try:
            # Send batch to Supabase
            url = f"{self.supabase_url}/rest/v1/{self.table_name}"
            
            # Use a longer timeout for batch operations
            response = requests.post(
                url, 
                json=batch, 
                headers=self.headers, 
                timeout=10
            )
            
            if response.status_code not in [200, 201]:
                print(f"Failed to send log batch to Supabase: {response.status_code} - {response.text}")
                # Could implement retry logic here
                
        except Exception as e:
            print(f"Error sending log batch to Supabase: {str(e)}")
    
    def flush(self):
        """
        Force flush any remaining logs
        """
        try:
            # Get all remaining logs from queue
            remaining_logs = []
            while not self.log_queue.empty():
                try:
                    remaining_logs.append(self.log_queue.get_nowait())
                except queue.Empty:
                    break
            
            if remaining_logs:
                self._send_batch(remaining_logs)
                
        except Exception as e:
            print(f"Error flushing logs: {str(e)}")

def setup_supabase_logging(
    supabase_url: Optional[str] = None,
    supabase_key: Optional[str] = None,
    table_name: str = 'server_logs',
    log_level: int = logging.INFO,
    include_console: bool = True,
    batch_size: int = 10,
    flush_interval: float = 5.0
):
    """
    Set up logging to both Supabase and optionally console
    
    Args:
        supabase_url: Supabase URL (defaults to environment variable)
        supabase_key: Supabase key (defaults to environment variable)
        table_name: Name of the logs table in Supabase
        log_level: Minimum log level to capture
        include_console: Whether to also log to console
        batch_size: Number of logs to batch before sending to Supabase
        flush_interval: Maximum time (seconds) to wait before flushing logs
    """
    
    # Get credentials from environment if not provided
    if not supabase_url:
        supabase_url = os.getenv('SUPABASE_URL')
    if not supabase_key:
        supabase_key = os.getenv('SUPABASE_ANON_KEY')
    
    if not supabase_url or not supabase_key:
        print("Warning: Supabase credentials not configured. Logging to console only.")
        if include_console:
            logging.basicConfig(level=log_level)
        return
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Add Supabase handler
    supabase_handler = SupabaseLogHandler(
        supabase_url, 
        supabase_key, 
        table_name,
        batch_size=batch_size,
        flush_interval=flush_interval
    )
    supabase_handler.setLevel(log_level)
    supabase_handler.setFormatter(formatter)
    root_logger.addHandler(supabase_handler)
    
    # Add console handler if requested
    if include_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    print(f"Logging configured: Supabase table '{table_name}' + {'Console' if include_console else 'Supabase only'}")

def log_with_context(level: int, message: str, **kwargs):
    """
    Log a message with additional context that will be stored in Supabase
    
    Args:
        level: Log level (e.g., logging.INFO, logging.ERROR)
        message: Log message
        **kwargs: Additional context fields (e.g., contact_id, operation, webhook_type)
    """
    logger = logging.getLogger()
    
    # Create a custom log record with extra fields
    record = logger.makeRecord(
        name=logger.name,
        level=level,
        fn=kwargs.get('function', ''),
        lno=kwargs.get('line', 0),
        msg=message,
        args=(),
        exc_info=kwargs.get('exc_info'),
        func=kwargs.get('function', ''),
        extra=kwargs
    )
    
    logger.handle(record)

# Convenience functions for common log levels with context
def info_with_context(message: str, **kwargs):
    """Log INFO level message with context"""
    log_with_context(logging.INFO, message, **kwargs)

def error_with_context(message: str, **kwargs):
    """Log ERROR level message with context"""
    log_with_context(logging.ERROR, message, **kwargs)

def warning_with_context(message: str, **kwargs):
    """Log WARNING level message with context"""
    log_with_context(logging.WARNING, message, **kwargs)

def debug_with_context(message: str, **kwargs):
    """Log DEBUG level message with context"""
    log_with_context(logging.DEBUG, message, **kwargs)

def shutdown_logging():
    """
    Gracefully shut down the logging system and flush any remaining logs
    """
    try:
        root_logger = logging.getLogger()
        
        # Find and flush Supabase handlers
        for handler in root_logger.handlers:
            if isinstance(handler, SupabaseLogHandler):
                handler.flush()
                
        print("Logging system shut down gracefully")
        
    except Exception as e:
        print(f"Error shutting down logging: {str(e)}")
