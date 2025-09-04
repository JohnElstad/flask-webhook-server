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



# Root endpoint
@app.route('/', methods=['GET'])
def root():
    return jsonify({
        'message': 'Webhook Server with OpenAI Integration',
        'features': {
            'message_batching': f'Messages are batched and processed after {os.getenv("MESSAGE_BATCH_WAIT_TIME", 30)} seconds of inactivity',
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
    # Get port from environment or default to 5000
    port = int(os.environ.get('PORT', 5000))
    
    # For production, use 0.0.0.0 to bind to all interfaces
    # For development, use 127.0.0.1 for local only
    host = os.environ.get('HOST', '127.0.0.1')
    
    print(f"Starting webhook server on {host}:{port}")
    print(f"Webhook endpoint: http://{host}:{port}/webhook")
    print(f"Health check: http://{host}:{port}/health")
    print(f"Ping test: http://{host}:{port}/ping")
    print(f"Message batching enabled - messages processed after {os.getenv('MESSAGE_BATCH_WAIT_TIME', 30)} seconds of inactivity")
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
