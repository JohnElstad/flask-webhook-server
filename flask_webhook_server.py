# Load environment variables FIRST, before any other imports
import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify
from flask_cors import CORS
from webhook_handlers import webhook_bp
from datetime import datetime

# Create Flask app
app = Flask(__name__)

# Enable CORS for webhook testing
CORS(app)

# Register blueprints
app.register_blueprint(webhook_bp)

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    try:
        import threading
        import os
        
        return jsonify({
            'status': 'healthy', 
            'message': 'Webhook server is running',
            'timestamp': datetime.now().isoformat(),
            'environment_loaded': bool(os.getenv('OPENAI_API_KEY')),
            'threads': {
                'active_count': threading.active_count(),
                'main_thread_alive': threading.main_thread().is_alive()
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

# Test OpenAI endpoint
@app.route('/test-openai', methods=['POST'])
def test_openai():
    try:
        from openai_handler import openai_handler
        
        if not openai_handler.is_configured():
            return jsonify({
                'status': 'error',
                'message': 'OpenAI not configured'
            }), 400
        
        # Test with a simple message
        test_message = "Hey, do you fix roofs?"
        response = openai_handler.generate_response(test_message)
        
        return jsonify({
            'status': 'success',
            'test_message': test_message,
            'ai_response': response.get('response'),
            'model': response.get('model'),
            'tokens_used': response.get('tokens_used'),
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'OpenAI test failed: {str(e)}'
        }), 500

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

# Test webhook endpoint to verify functionality
@app.route('/test-webhook', methods=['POST'])
def test_webhook():
    try:
        # Simulate a GHL webhook
        test_data = {
            'contact_id': 'test_contact_123',
            'first_name': 'John',
            'last_name': 'Test',
            'phone': '+1234567890',
            'message': {
                'body': 'Hello, this is a test message',
                'message_type': 'SMS'
            },
            'type': 'contact.reply'
        }
        
        return jsonify({
            'status': 'success',
            'message': 'Test webhook endpoint working',
            'test_data': test_data,
            'note': 'Use /webhook endpoint for actual processing',
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Test webhook setup failed: {str(e)}'
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
            'test_openai': '/test-openai (POST) - Test OpenAI functionality',
            'generate_response': '/generate-response (POST) - Generate AI response',
            'test_webhook': '/test-webhook (POST) - Test webhook functionality',
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
    
    app.run(host=host, port=port, debug=True)
