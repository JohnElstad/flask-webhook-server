#!/usr/bin/env python3
"""
Test script for the message batching system
This script simulates multiple messages being sent to test the batching behavior
"""

import requests
import time
import json
from datetime import datetime

# Configuration
WEBHOOK_URL = "http://127.0.0.1:5000/webhook"
TEST_CONTACT_ID = "test_contact_batch_123"

def send_test_message(message_body):
    """Send a test message to the webhook"""
    webhook_data = {
        'contact_id': TEST_CONTACT_ID,
        'first_name': 'Test',
        'last_name': 'User',
        'phone': '+1234567890',
        'message': {
            'body': message_body,
            'message_type': 'SMS'
        },
        'type': 'contact.reply'
    }
    
    try:
        response = requests.post(WEBHOOK_URL, json=webhook_data, timeout=10)
        print(f"✅ Message sent: '{message_body}' - Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"   Response: {result.get('message', 'No message')}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Failed to send message: {str(e)}")
        return False

def check_batch_status():
    """Check the current batch status"""
    try:
        response = requests.get(f"http://127.0.0.1:5000/queue-status", timeout=10)
        if response.status_code == 200:
            status = response.json()
            print(f"\n📊 Batch Status:")
            print(f"   Active batches: {status.get('active_batches', 0)}")
            print(f"   Batch wait time: {status.get('batch_wait_time', 'Unknown')}s")
            
            if status.get('batch_details'):
                for contact_id, batch_info in status['batch_details'].items():
                    print(f"   Contact {contact_id}:")
                    print(f"     Messages: {batch_info.get('message_count', 0)}")
                    print(f"     Time remaining: {batch_info.get('time_remaining', 'Unknown')}s")
                    print(f"     Timer active: {batch_info.get('timer_active', 'Unknown')}")
                    if batch_info.get('messages'):
                        print(f"     Messages: {', '.join(batch_info['messages'])}")
        else:
            print(f"❌ Failed to get batch status: {response.status_code}")
    except Exception as e:
        print(f"❌ Error checking batch status: {str(e)}")

def test_batching_system():
    """Test the batching system with multiple messages"""
    print("🚀 Testing Message Batching System")
    print("=" * 50)
    
    # Send first message
    print(f"\n📝 Sending first message at {datetime.now().strftime('%H:%M:%S')}")
    send_test_message("Hi there!")
    
    # Check initial status
    time.sleep(2)
    check_batch_status()
    
    # Send second message after 5 seconds
    print(f"\n⏰ Waiting 5 seconds...")
    time.sleep(5)
    
    print(f"\n📝 Sending second message at {datetime.now().strftime('%H:%M:%S')}")
    send_test_message("I have a question")
    
    # Check status again
    time.sleep(2)
    check_batch_status()
    
    # Send third message after another 5 seconds
    print(f"\n⏰ Waiting 5 more seconds...")
    time.sleep(5)
    
    print(f"\n📝 Sending third message at {datetime.now().strftime('%H:%M:%S')}")
    send_test_message("About gym membership")
    
    # Check final status
    time.sleep(2)
    check_batch_status()
    
    print(f"\n⏰ Now waiting for batch timer to expire (should be ~20 seconds remaining)...")
    print("   The batch should process automatically after the timer expires.")
    print("   Check your server logs to see when the batch is processed.")
    
    # Monitor the batch status every 5 seconds
    for i in range(10):  # Monitor for up to 50 seconds
        time.sleep(5)
        check_batch_status()
        
        # Check if batch was processed
        try:
            response = requests.get(f"http://127.0.0.1:5000/batch-status/{TEST_CONTACT_ID}", timeout=10)
            if response.status_code == 200:
                status = response.json()
                if not status.get('batch_info'):
                    print(f"\n🎉 Batch was processed! No active batch found for {TEST_CONTACT_ID}")
                    break
        except:
            pass

def test_force_process():
    """Test forcing a batch to process immediately"""
    print(f"\n🔨 Testing Force Process")
    print("=" * 30)
    
    # Send a message
    send_test_message("Force process test message")
    
    # Wait a moment
    time.sleep(2)
    
    # Force process the batch
    try:
        response = requests.post(f"http://127.0.0.1:5000/force-process-batch/{TEST_CONTACT_ID}", timeout=10)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Force process successful: {result.get('message', 'No message')}")
        else:
            print(f"❌ Force process failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error force processing: {str(e)}")

if __name__ == "__main__":
    print("Choose a test:")
    print("1. Test normal batching (send 3 messages, wait for timer)")
    print("2. Test force processing (send message, force process immediately)")
    print("3. Check current batch status")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == "1":
        test_batching_system()
    elif choice == "2":
        test_force_process()
    elif choice == "3":
        check_batch_status()
    else:
        print("Invalid choice. Running normal batching test...")
        test_batching_system()
