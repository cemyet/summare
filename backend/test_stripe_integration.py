#!/usr/bin/env python3
"""
Test script for Stripe integration with step 505
This script tests the dynamic Stripe checkout session creation
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")

def test_step_505_stripe_integration():
    """Test the complete Stripe integration flow for step 505"""
    
    print("🧪 Testing Stripe Integration for Step 505")
    print("=" * 50)
    
    # Test 1: Get step 505 data
    print("\n1️⃣ Testing step 505 data retrieval...")
    try:
        response = requests.get(f"{API_BASE_URL}/api/chat-flow/505")
        if response.status_code == 200:
            step_data = response.json()
            print("✅ Step 505 data retrieved successfully")
            print(f"   Question: {step_data.get('question_text', 'N/A')}")
            print(f"   Options: {len(step_data.get('options', []))}")
            
            # Check if we have the stripe_payment option
            options = step_data.get('options', [])
            stripe_option = None
            for option in options:
                if option.get('option_value') == 'stripe_payment':
                    stripe_option = option
                    break
            
            if stripe_option:
                print("✅ Stripe payment option found")
                print(f"   Action type: {stripe_option.get('action_type')}")
            else:
                print("❌ Stripe payment option not found")
                return False
                
        else:
            print(f"❌ Failed to get step 505: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error getting step 505: {str(e)}")
        return False
    
    # Test 2: Process stripe_payment choice
    print("\n2️⃣ Testing stripe_payment choice processing...")
    try:
        payload = {
            "step_number": 505,
            "option_value": "stripe_payment",
            "context": {}
        }
        
        response = requests.post(
            f"{API_BASE_URL}/api/chat-flow/process-choice",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Stripe payment choice processed successfully")
            
            if result.get('success'):
                action_data = result.get('result', {}).get('action_data', {})
                if action_data.get('url') and 'checkout.stripe.com' in action_data.get('url', ''):
                    print("✅ Dynamic Stripe checkout URL generated")
                    print(f"   URL: {action_data.get('url')}")
                    return True
                else:
                    print("❌ No valid Stripe checkout URL in response")
                    print(f"   Action data: {action_data}")
                    return False
            else:
                print("❌ Choice processing failed")
                return False
        else:
            print(f"❌ Failed to process choice: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error processing choice: {str(e)}")
        return False

def test_direct_stripe_session():
    """Test direct Stripe session creation endpoint"""
    
    print("\n3️⃣ Testing direct Stripe session creation...")
    try:
        response = requests.post(f"{API_BASE_URL}/create-stripe-session")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Direct Stripe session created successfully")
            print(f"   Checkout URL: {result.get('checkout_url')}")
            print(f"   Session ID: {result.get('session_id')}")
            return True
        else:
            print(f"❌ Failed to create Stripe session: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error creating Stripe session: {str(e)}")
        return False

def main():
    """Run all tests"""
    
    print("🚀 Stripe Integration Test Suite")
    print("=" * 50)
    
    # Check if Stripe key is configured
    if not STRIPE_SECRET_KEY:
        print("⚠️  STRIPE_SECRET_KEY not configured - some tests may fail")
    else:
        print("✅ Stripe secret key configured")
    
    # Run tests
    test1_passed = test_step_505_stripe_integration()
    test2_passed = test_direct_stripe_session()
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print(f"   Step 505 Integration: {'✅ PASS' if test1_passed else '❌ FAIL'}")
    print(f"   Direct Session Creation: {'✅ PASS' if test2_passed else '❌ FAIL'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 All tests passed! Stripe integration is working correctly.")
        return True
    else:
        print("\n❌ Some tests failed. Please check the configuration and try again.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
