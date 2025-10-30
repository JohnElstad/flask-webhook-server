#!/usr/bin/env python3
"""
WSGI entry point for production deployment
"""
import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the Flask app
from flask_webhook_server import app

# Make sure the app is available for WSGI servers
application = app

if __name__ == "__main__":
    # For direct execution
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    app.run(host=host, port=port, debug=False)
