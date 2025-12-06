"""
Script to verify and add admins to the database
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'billionaires_backend.settings')
django.setup()

from api.models import Admin

def verify_admins():
    """Verify that all required admins exist in database"""

    required_admins = [
        {'telegram_id': 7928805328, 'username': 'billionaires_370625', 'role': 'superadmin'},
        {'telegram_id': 5465086879, 'username': 'FixXxaL', 'role': 'admin'},
    ]

    print("🔍 Checking admins in database...\n")

    for admin_info in required_admins:
        telegram_id = admin_info['telegram_id']
        username = admin_info['username']
        role = admin_info['role']

        admin, created = Admin.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={
                'username': username,
                'role': role,
                'is_active': True
            }
        )

        if created:
            print(f"✅ Created new admin: {telegram_id} ({username}) - Role: {role}")
        else:
            # Update if exists
            if not admin.is_active:
                admin.is_active = True
                admin.save()
                print(f"🔄 Activated admin: {telegram_id} ({username}) - Role: {role}")
            else:
                print(f"✓ Admin already exists: {telegram_id} ({username}) - Role: {role}, Active: {admin.is_active}")

    print(f"\n📊 Total active admins in database: {Admin.objects.filter(is_active=True).count()}")
    print("\nAll admins:")
    for admin in Admin.objects.all():
        print(f"  - ID: {admin.telegram_id}, Username: {admin.username}, Role: {admin.role}, Active: {admin.is_active}")

if __name__ == '__main__':
    verify_admins()
