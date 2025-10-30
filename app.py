#!/usr/bin/env python3
"""
Simple app.py entry point for Render deployment
This imports the Flask app from flask_webhook_server.py
"""
from flask_webhook_server import app

if __name__ == "__main__":
    import os
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    app.run(host=host, port=port, debug=False)
