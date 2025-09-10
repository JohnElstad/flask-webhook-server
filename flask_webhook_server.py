# Load environment variables FIRST, before any other imports
import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify
from flask_cors import CORS
from webhook_handlers import webhook_bp
from datetime import datetime
import logging
from supabase_logger import setup_supabase_logging, shutdown_logging

# Create Flask app
app = Flask(__name__)

# Enable CORS for webhook testing
CORS(app)

# Set up Supabase logging with async batching
setup_supabase_logging(
    table_name='server_logs',
    log_level=logging.INFO,
    include_console=True,
    batch_size=20,  # Send logs in batches of 20
    flush_interval=10.0  # Flush every 10 seconds
)

# Register blueprints
app.register_blueprint(webhook_bp)

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    try:
        import threading
        import psutil
        import os
        
        # Get process info
        process = psutil.Process(os.getpid())
        
        return jsonify({
            'status': 'healthy', 
            'message': 'Webhook server is running',
            'timestamp': datetime.now().isoformat(),
            'environment_loaded': bool(os.getenv('OPENAI_API_KEY')),
            'threads': {
                'active_count': threading.active_count(),
                'main_thread_alive': threading.main_thread().is_alive()
            },
            'process': {
                'memory_mb': round(process.memory_info().rss / 1024 / 1024, 2),
                'cpu_percent': process.cpu_percent(),
                'create_time': datetime.fromtimestamp(process.create_time()).isoformat()
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Health check failed: {str(e)}'
        }), 500

# Simple ping endpoint for basic connectivity testing
@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({'pong': datetime.now().isoformat()})



# Emergency reset endpoint to clear all timers
@app.route('/reset-timers', methods=['POST'])
def reset_timers():
    try:
        return jsonify({
            'status': 'success',
            'message': 'Timer system removed - no timers to reset',
            'note': 'System now processes messages immediately',
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Request failed: {str(e)}'
        }), 500

# Debug endpoint to check for stuck locks
@app.route('/debug/locks', methods=['GET'])
def debug_locks():
    try:
        from chat_processor import chat_processor
        
        # Get current status
        active_batches = chat_processor.get_active_batches()
        timer_status = chat_processor.get_timer_status()
        
        return jsonify({
            'status': 'success',
            'active_batches': active_batches,
            'timer_status': timer_status,
            'batch_locks_count': len(chat_processor.batch_locks),
            'batch_threads_count': len(chat_processor.batch_threads),
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Debug failed: {str(e)}'
        }), 500

# Force cleanup stuck locks endpoint
@app.route('/debug/force-cleanup', methods=['POST'])
def force_cleanup():
    try:
        from chat_processor import chat_processor
        
        # Force cleanup stuck locks
        cleaned_count = chat_processor.force_cleanup_stuck_locks()
        
        return jsonify({
            'status': 'success',
            'message': f'Force cleanup completed, removed {cleaned_count} stuck contacts',
            'cleaned_count': cleaned_count,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Force cleanup failed: {str(e)}'
        }), 500

# Nuclear cleanup endpoint - removes ALL threads and batches
@app.route('/debug/nuclear-cleanup', methods=['POST'])
def nuclear_cleanup():
    try:
        from chat_processor import chat_processor
        
        # Nuclear cleanup - removes everything
        cleaned_count = chat_processor.force_cleanup_all_threads()
        
        return jsonify({
            'status': 'success',
            'message': f'Nuclear cleanup completed, removed {cleaned_count} items',
            'cleaned_count': cleaned_count,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Nuclear cleanup failed: {str(e)}'
        }), 500



# Root endpoint
@app.route('/', methods=['GET'])
def root():
    return jsonify({
        'message': 'Webhook Server with OpenAI Integration',
        'features': {
            'message_batching': f'Messages are batched and processed after {os.getenv("MESSAGE_BATCH_WAIT_TIME", 5)} seconds of inactivity',
            'openai_integration': 'AI-powered message analysis and responses',
            'chat_history': 'Automatic chat history retrieval and processing',
            'configurable_wait_time': 'Batch wait time is configurable via environment variable or API'
        },
        'endpoints': {
            'webhook': '/webhook (POST) - Main webhook endpoint',
            'health': '/health (GET) - Health check',
            'ping': '/ping (GET) - Basic connectivity test',
            'config': '/config (GET) - Configuration status',
            'generate_response': '/generate-response (POST) - Generate AI response',
            'batch_config': '/batch-config (GET/POST) - Get or set batch configuration',
            'queue_status': '/queue-status (GET) - Check active message batches',
            'force_process_batch': '/force-process-batch/<contact_id> (POST) - Force process a batch immediately',
            'batch_status': '/batch-status/<contact_id> (GET) - Get detailed batch status for a contact'
        }
    })

if __name__ == '__main__':
    # Disable Windows console quick edit mode to prevent hanging
    if os.name == 'nt':  # Windows only
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # Get console handle
            console_handle = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
            # Get current console mode
            mode = ctypes.c_ulong()
            kernel32.GetConsoleMode(console_handle, ctypes.byref(mode))
            # Disable quick edit mode (0x0040) and insert mode (0x0020)
            new_mode = mode.value & ~(0x0040 | 0x0020)
            kernel32.SetConsoleMode(console_handle, new_mode)
            print("Windows console quick edit mode disabled to prevent hanging")
        except Exception as e:
            print(f"Warning: Could not disable console quick edit mode: {e}")
    
    # Get port from environment or default to 5000
    port = int(os.environ.get('PORT', 5000))
    
    # For production, use 0.0.0.0 to bind to all interfaces
    # For development, use 127.0.0.1 for local only
    host = os.environ.get('HOST', '127.0.0.1')
    
    print(f"Starting webhook server on {host}:{port}")
    print(f"Webhook endpoint: http://{host}:{port}/webhook")
    print(f"Health check: http://{host}:{port}/health")
    print(f"Ping test: http://{host}:{port}/ping")
    print(f"Message batching enabled - messages processed after {os.getenv('MESSAGE_BATCH_WAIT_TIME', 5)} seconds of inactivity")
    print(f"OpenAI integration: {'Enabled' if os.getenv('OPENAI_API_KEY') else 'Disabled'}")
    print(f"Async logging enabled - logs batched every 10 seconds or 20 logs")
    
    try:
        # For production, disable debug mode and use 0.0.0.0
        debug_mode = os.environ.get('FLASK_ENV') == 'development'
        app.run(host='0.0.0.0', port=port, debug=debug_mode)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        shutdown_logging()
        print("Server stopped")
