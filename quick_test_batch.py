#!/usr/bin/env python3
"""
Quick test for the message batching system
Sets a short wait time and sends multiple messages to test batching
"""

import requests
import time
import json

# Configuration
WEBHOOK_URL = "http://127.0.0.1:5000/webhook"
TEST_CONTACT_ID = "quick_test_456"

def set_batch_wait_time(seconds):
    """Set the batch wait time to a shorter duration for testing"""
    try:
        data = {'batch_wait_time': seconds}
        response = requests.post('http://127.0.0.1:5000/batch-config', json=data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Batch wait time set to {seconds} seconds: {result.get('message')}")
            return True
        else:
            print(f"❌ Failed to set batch wait time: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error setting batch wait time: {str(e)}")
        return False

def send_message(message):
    """Send a test message"""
    webhook_data = {
        'contact_id': TEST_CONTACT_ID,
        'first_name': 'Quick',
        'last_name': 'Test',
        'phone': '+1234567890',
        'message': {
            'body': message,
            'message_type': 'SMS'
        },
        'type': 'contact.reply'
    }
    
    try:
        response = requests.post(WEBHOOK_URL, json=webhook_data, timeout=10)
        print(f"📝 Sent: '{message}' - Status: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Failed to send: {str(e)}")
        return False

def check_status():
    """Check batch status"""
    try:
        response = requests.get('http://127.0.0.1:5000/queue-status', timeout=10)
        if response.status_code == 200:
            status = response.json()
            batches = status.get('batch_details', {})
            if TEST_CONTACT_ID in batches:
                batch = batches[TEST_CONTACT_ID]
                print(f"📊 Batch: {batch['message_count']} messages, {batch['time_remaining']:.1f}s remaining")
            else:
                print("📊 No active batch found")
    except Exception as e:
        print(f"❌ Error checking status: {str(e)}")

def main():
    print("🚀 Quick Batching Test")
    print("=" * 30)
    
    # Set a short wait time for testing (10 seconds)
    print("\n⚙️ Setting batch wait time to 10 seconds...")
    if not set_batch_wait_time(10):
        print("Failed to set batch wait time. Exiting.")
        return
    
    # Send first message
    print(f"\n📝 Sending first message at {time.strftime('%H:%M:%S')}")
    send_message("Hello!")
    time.sleep(1)
    check_status()
    
    # Send second message after 2 seconds
    print(f"\n⏰ Waiting 2 seconds...")
    time.sleep(2)
    
    print(f"\n📝 Sending second message at {time.strftime('%H:%M:%S')}")
    send_message("How are you?")
    time.sleep(1)
    check_status()
    
    # Send third message after another 2 seconds
    print(f"\n⏰ Waiting 2 more seconds...")
    time.sleep(2)
    
    print(f"\n📝 Sending third message at {time.strftime('%H:%M:%S')}")
    send_message("I need help with something")
    time.sleep(1)
    check_status()
    
    print(f"\n⏰ Now waiting for batch timer to expire (~5 seconds remaining)...")
    print("   The batch should process automatically after 10 seconds total.")
    
    # Monitor every 2 seconds
    for i in range(6):
        time.sleep(2)
        check_status()
        
        # Check if batch was processed
        try:
            response = requests.get(f'http://127.0.0.1:5000/batch-status/{TEST_CONTACT_ID}', timeout=10)
            if response.status_code == 200:
                status = response.json()
                if not status.get('batch_info'):
                    print(f"\n🎉 Batch was processed! Check your server logs for OpenAI response.")
                    break
        except:
            pass
    
    print(f"\n✅ Test completed! Check your server logs to see the batch processing.")

if __name__ == "__main__":
    main()
