"""
Script to cleanup and manage admins in database
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'billionaires_backend.settings')
django.setup()

from api.models import Admin

def cleanup_admins():
    """Remove duplicate admins and keep only the required ones"""

    # These are the ONLY admins we want to keep
    required_admins = [
        7928805328,  # billionaires_370625 (SUPER ADMIN from ADMIN_USER_ID)
        5465086879,  # FixXxaL (regular admin)
    ]

    print("🔍 Cleaning up admin database...\n")

    all_admins = Admin.objects.all()
    print(f"📊 Found {all_admins.count()} total admins\n")

    for admin in all_admins:
        if admin.telegram_id in required_admins:
            # Keep this admin, make sure it's active
            if not admin.is_active:
                admin.is_active = True
                admin.save()
                print(f"✅ Kept and activated: {admin.telegram_id} ({admin.username})")
            else:
                print(f"✓ Keeping: {admin.telegram_id} ({admin.username})")
        else:
            # This admin is not in our required list
            print(f"❌ Removing extra admin: {admin.telegram_id} ({admin.username or 'No username'})")
            admin.delete()

    print(f"\n📊 Final admin count: {Admin.objects.filter(is_active=True).count()}")
    print("\nRemaining admins:")
    for admin in Admin.objects.all():
        print(f"  ✅ ID: {admin.telegram_id}, Username: {admin.username}, Role: {admin.role}, Active: {admin.is_active}")

if __name__ == '__main__':
    response = input("⚠️  This will remove admins NOT in the required list (7928805328, 5465086879). Continue? (yes/no): ")
    if response.lower() == 'yes':
        cleanup_admins()
    else:
        print("Cancelled.")
