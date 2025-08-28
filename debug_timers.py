#!/usr/bin/env python3
"""
Debug script for stuck timers in the message batching system
"""

import requests
import time
import json

# Configuration
BASE_URL = "http://127.0.0.1:5000"

def check_server_health():
    """Check if the server is responding"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Server is responding")
            return True
        else:
            print(f"❌ Server returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to server: {str(e)}")
        return False

def check_batch_status():
    """Check current batch status"""
    try:
        response = requests.get(f"{BASE_URL}/queue-status", timeout=5)
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
            return status
        else:
            print(f"❌ Failed to get batch status: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error checking batch status: {str(e)}")
        return None

def check_timer_status():
    """Check detailed timer thread status"""
    try:
        response = requests.get(f"{BASE_URL}/timer-status", timeout=5)
        if response.status_code == 200:
            status = response.json()
            print(f"\n⏰ Timer Status:")
            if status.get('timer_status'):
                for contact_id, timer_info in status['timer_status'].items():
                    print(f"   Contact {contact_id}:")
                    print(f"     Is alive: {timer_info.get('is_alive', 'Unknown')}")
                    print(f"     Thread name: {timer_info.get('name', 'Unknown')}")
                    print(f"     Daemon: {timer_info.get('daemon', 'Unknown')}")
            else:
                print("   No active timers found")
            return status
        else:
            print(f"❌ Failed to get timer status: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error checking timer status: {str(e)}")
        return None

def cleanup_batches():
    """Clean up all stuck batches and timers"""
    try:
        print("\n🧹 Cleaning up all batches and timers...")
        response = requests.post(f"{BASE_URL}/cleanup-batches", timeout=10)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Cleanup successful: {result.get('message', 'No message')}")
            return True
        else:
            print(f"❌ Cleanup failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error during cleanup: {str(e)}")
        return False

def test_webhook():
    """Test if webhook endpoint is working"""
    try:
        print("\n📝 Testing webhook endpoint...")
        webhook_data = {
            'contact_id': 'debug_test_123',
            'first_name': 'Debug',
            'last_name': 'Test',
            'phone': '+1234567890',
            'message': {
                'body': 'Debug test message',
                'message_type': 'SMS'
            },
            'type': 'contact.reply'
        }
        
        response = requests.post(f"{BASE_URL}/webhook", json=webhook_data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Webhook test successful: {result.get('message', 'No message')}")
            return True
        else:
            print(f"❌ Webhook test failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing webhook: {str(e)}")
        return False

def main():
    print("🔍 Timer Debugging Tool")
    print("=" * 40)
    
    # Check server health
    if not check_server_health():
        print("\n❌ Server is not responding. Please start the Flask server first.")
        return
    
    # Check current status
    batch_status = check_batch_status()
    timer_status = check_timer_status()
    
    # Test webhook functionality
    webhook_working = test_webhook()
    
    # Provide recommendations
    print(f"\n📋 Recommendations:")
    
    if batch_status and batch_status.get('active_batches', 0) > 0:
        print("   - You have active batches. This is normal if messages were recently sent.")
    
    if timer_status and timer_status.get('timer_status'):
        print("   - You have active timers. This is normal if batches are waiting to process.")
    
    if not webhook_working:
        print("   - Webhook endpoint is not working properly.")
    
    # Ask if user wants to clean up
    print(f"\n🧹 If you're experiencing stuck timers or want to reset everything:")
    choice = input("   Do you want to clean up all batches and timers? (y/n): ").strip().lower()
    
    if choice == 'y':
        cleanup_batches()
        
        # Check status again
        print(f"\n📊 Status after cleanup:")
        check_batch_status()
        check_timer_status()
    
    print(f"\n✅ Debugging complete!")

if __name__ == "__main__":
    main()
