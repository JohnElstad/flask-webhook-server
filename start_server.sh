#!/bin/bash

echo "Starting Flask Webhook Server..."
echo ""
echo "Make sure you have Python installed and dependencies installed:"
echo "pip install -r requirements.txt"
echo ""
echo "Starting server on http://127.0.0.1:5000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Check if Python is installed
if ! command -v python &> /dev/null; then
    echo "Error: Python is not installed or not in PATH"
    exit 1
fi

# Check if requirements are installed
if [ ! -f "requirements.txt" ]; then
    echo "Error: requirements.txt not found"
    exit 1
fi

# Start the server
python app.py
