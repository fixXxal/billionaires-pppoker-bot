#!/usr/bin/env python3
"""
Backfill PPPoker IDs to user profiles from their deposits
Run this once to update all existing users with their most recent PPPoker ID
"""

import os
import sys
import django
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_backend.settings')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'django_backend'))
django.setup()

from api.models import User, Deposit

def backfill_pppoker_ids():
    """Update user PPPoker IDs from their most recent deposit"""

    print("🔄 Starting PPPoker ID backfill...")

    # Get all users
    users = User.objects.all()
    total_users = users.count()
    updated_count = 0
    skipped_count = 0

    print(f"📊 Found {total_users} users to process\n")

    for user in users:
        # Get user's most recent deposit with a PPPoker ID
        recent_deposit = Deposit.objects.filter(
            user=user,
            pppoker_id__isnull=False
        ).exclude(
            pppoker_id=''
        ).order_by('-created_at').first()

        if recent_deposit and recent_deposit.pppoker_id:
            pppoker_id = recent_deposit.pppoker_id

            # Update user's PPPoker ID if different or empty
            if user.pppoker_id != pppoker_id:
                old_id = user.pppoker_id or "(empty)"
                user.pppoker_id = pppoker_id
                user.save()
                updated_count += 1
                print(f"✅ Updated user {user.telegram_id} (@{user.username}): {old_id} → {pppoker_id}")
            else:
                skipped_count += 1
                print(f"⏭️  Skipped user {user.telegram_id} (already has ID: {pppoker_id})")
        else:
            skipped_count += 1
            print(f"⏭️  Skipped user {user.telegram_id} (no deposits with PPPoker ID)")

    print(f"\n✨ Backfill complete!")
    print(f"📈 Updated: {updated_count} users")
    print(f"⏭️  Skipped: {skipped_count} users")
    print(f"📊 Total: {total_users} users")

if __name__ == '__main__':
    backfill_pppoker_ids()
