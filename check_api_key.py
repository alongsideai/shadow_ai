#!/usr/bin/env python3
"""Quick script to check if OpenAI API key is configured correctly."""

import os
import sys

def check_api_key():
    """Check if OpenAI API key is set and valid."""
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ OPENAI_API_KEY environment variable is NOT set")
        print("\nTo set it:")
        print("  export OPENAI_API_KEY='sk-your-key-here'")
        print("\nOr create a .env file with:")
        print("  OPENAI_API_KEY=sk-your-key-here")
        return False
    
    if not api_key.startswith("sk-"):
        print("⚠️  WARNING: API key doesn't start with 'sk-'")
        print(f"   Key starts with: {api_key[:10]}...")
        return False
    
    print(f"✅ OPENAI_API_KEY is set")
    print(f"   Key starts with: {api_key[:7]}...")
    print(f"   Key length: {len(api_key)} characters")
    
    # Try to initialize the service to verify it works
    try:
        from shadowai.value_enrichment_service import create_enrichment_service
        service = create_enrichment_service()
        print("✅ Enrichment service initialized successfully")
        return True
    except ValueError as e:
        print(f"❌ Failed to initialize service: {e}")
        return False
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("   Install with: pip install openai")
        return False
    except Exception as e:
        print(f"⚠️  Service initialization error: {e}")
        return False

if __name__ == "__main__":
    success = check_api_key()
    sys.exit(0 if success else 1)

