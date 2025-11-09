#!/usr/bin/env python3
"""Quick test script to verify Supabase connection"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_supabase():
    print("🔍 Testing Supabase Connection...\n")
    
    # Check if variables are set
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Missing Supabase credentials in .env file")
        return False
    
    print(f"✅ SUPABASE_URL: {supabase_url[:30]}...")
    print(f"✅ SUPABASE_ANON_KEY: {supabase_key[:30]}...\n")
    
    # Try to connect
    try:
        from supabase import create_client
        client = create_client(supabase_url, supabase_key)
        
        # Test query to chat_flow table
        print("📡 Testing connection to chat_flow table...")
        result = client.table('chat_flow').select('step_number').limit(1).execute()
        
        if result.data:
            print(f"✅ SUCCESS! Connected to Supabase and found {len(result.data)} row(s)")
            print(f"   Sample step_number: {result.data[0].get('step_number', 'N/A')}")
            
            # Test step 110 specifically
            print("\n📡 Testing step 110...")
            step110 = client.table('chat_flow').select('*').eq('step_number', 110).execute()
            if step110.data:
                print(f"✅ Step 110 found: {step110.data[0].get('question_text', '')[:50]}...")
            else:
                print("⚠️  Step 110 not found in database")
            
            return True
        else:
            print("⚠️  Connected but no data found")
            return False
            
    except ImportError:
        print("❌ supabase-py not installed. Run: pip install supabase")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_supabase()
    sys.exit(0 if success else 1)
