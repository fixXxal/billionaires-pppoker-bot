"""
One-time script to fix existing pending spin timestamps.
Converts timestamps from Indian/Maldives timezone (UTC+5) to UTC.
"""
import os
import sys
import django
from datetime import timedelta

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'billionaires_backend.settings')
django.setup()

from api.models import SpinHistory
from django.utils import timezone
import pytz

def fix_pending_spins():
    """Convert pending spin timestamps from Maldives time to UTC"""

    # Get all pending spins (not notified)
    pending_spins = SpinHistory.objects.filter(notified_at__isnull=True)

    print(f"Found {pending_spins.count()} pending spins to fix")

    maldives_tz = pytz.timezone('Indian/Maldives')
    fixed_count = 0

    for spin in pending_spins:
        # The timestamp is currently stored as if it's UTC, but it was actually created in Maldives time
        # So we need to subtract 5 hours to get the real UTC time
        old_created_at = spin.created_at

        # Subtract 5 hours (Maldives is UTC+5)
        new_created_at = old_created_at - timedelta(hours=5)

        # Update the record
        spin.created_at = new_created_at
        spin.save(update_fields=['created_at'])

        fixed_count += 1

        if fixed_count <= 5:  # Show first 5 for verification
            print(f"  Spin ID {spin.id}: {old_created_at} → {new_created_at} (subtracted 5 hours)")

    print(f"\n✅ Fixed {fixed_count} pending spins")
    print(f"All timestamps have been converted from Maldives time to UTC")

if __name__ == '__main__':
    fix_pending_spins()
