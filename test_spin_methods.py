"""
Quick test script to verify spin methods work
"""
import os
os.environ['DJANGO_API_URL'] = 'https://billionaires-pppoker-bot-production-5ae9.up.railway.app/api'

from django_api import DjangoAPI

# Test the methods exist
api = DjangoAPI()

print("✅ Testing Django API methods...")
print(f"   - get_spin_user: {hasattr(api, 'get_spin_user')}")
print(f"   - create_spin_user: {hasattr(api, 'create_spin_user')}")
print(f"   - update_spin_user: {hasattr(api, 'update_spin_user')}")

# Test actual call (using a test user ID that won't exist)
print("\n🧪 Testing get_spin_user with non-existent user...")
try:
    result = api.get_spin_user(telegram_id=999999999)
    print(f"   Result: {result}")
    if result is None:
        print("   ✅ Returns None for non-existent user (correct behavior)")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n✅ All tests complete!")
