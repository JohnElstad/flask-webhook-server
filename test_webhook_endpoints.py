#!/usr/bin/env python3
"""
Test script for the webhook server
Run this script to test your webhook endpoints locally
"""

import requests
import json
import time

# Configuration
BASE_URL = "http://127.0.0.1:5000"
WEBHOOK_URL = f"{BASE_URL}/webhook"
HEALTH_URL = f"{BASE_URL}/health"
TEST_URL = f"{BASE_URL}/test-webhook"

def test_health_endpoint():
    """Test the health check endpoint"""
    print("🔍 Testing health endpoint...")
    try:
        response = requests.get(HEALTH_URL)
        if response.status_code == 200:
            print("✅ Health check passed")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure it's running!")
        return False
    return True

def test_webhook_endpoint():
    """Test the webhook endpoint with sample data"""
    print("\n🔍 Testing webhook endpoint...")
    
    # Test data for contact reply
    test_data = {
        "type": "contact.reply",
        "contact": {
            "id": "test_contact_123",
            "email": "test@example.com",
            "firstName": "John",
            "lastName": "Doe"
        },
        "message": {
            "content": "This is a test message",
            "direction": "inbound",
            "timestamp": "2024-01-01T12:00:00Z"
        }
    }
    
    try:
        response = requests.post(
            WEBHOOK_URL,
            json=test_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            print("✅ Webhook test passed")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Webhook test failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server")
        return False
    
    return True

def test_contact_created_webhook():
    """Test the webhook endpoint with contact creation data"""
    print("\n🔍 Testing contact creation webhook...")
    
    test_data = {
        "type": "contact.created",
        "contact": {
            "id": "new_contact_456",
            "email": "new@example.com",
            "firstName": "Jane",
            "lastName": "Smith",
            "phone": "+1234567890"
        },
        "location": {
            "id": "loc_123",
            "name": "Test Location"
        }
    }
    
    try:
        response = requests.post(
            WEBHOOK_URL,
            json=test_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            print("✅ Contact creation webhook test passed")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Contact creation webhook test failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server")
        return False
    
    return True

def test_unknown_webhook_type():
    """Test the webhook endpoint with unknown webhook type"""
    print("\n🔍 Testing unknown webhook type...")
    
    test_data = {
        "type": "unknown.event",
        "data": {
            "someField": "someValue"
        }
    }
    
    try:
        response = requests.post(
            WEBHOOK_URL,
            json=test_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            print("✅ Unknown webhook type test passed")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Unknown webhook type test failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server")
        return False
    
    return True

def test_invalid_json():
    """Test the webhook endpoint with invalid JSON"""
    print("\n🔍 Testing invalid JSON handling...")
    
    try:
        response = requests.post(
            WEBHOOK_URL,
            data="invalid json data",
            headers={"Content-Type": "application/json"}
        )
        
        print(f"   Response status: {response.status_code}")
        print(f"   Response: {response.text}")
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server")
        return False
    
    return True

def main():
    """Run all tests"""
    print("🚀 Starting webhook server tests...")
    print(f"   Server URL: {BASE_URL}")
    print(f"   Webhook endpoint: {WEBHOOK_URL}")
    print("=" * 50)
    
    # Test health endpoint first
    if not test_health_endpoint():
        print("\n❌ Server is not running. Please start the Flask app first:")
        print("   cd src")
        print("   python app.py")
        return
    
    # Wait a moment for server to be ready
    time.sleep(1)
    
    # Run all tests
    tests = [
        test_webhook_endpoint,
        test_contact_created_webhook,
        test_unknown_webhook_type,
        test_invalid_json
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your webhook server is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    print("\n💡 Next steps:")
    print("   1. Your webhook server is running locally")
    print("   2. To receive webhooks from external services, use ngrok:")
    print("      ngrok http 5000")
    print("   3. Use the ngrok URL as your webhook endpoint in GHL")

if __name__ == "__main__":
    main()
