"""
Script to populate exchange rates in the database
Run this script once to set up initial exchange rates
"""

import os
import django
import sys
from decimal import Decimal

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'billionaires_backend.settings')
sys.path.append('/mnt/c/billionaires')
django.setup()

from api.models import ExchangeRate

def populate_exchange_rates():
    """
    Populate exchange rates table with common currency conversions

    Base currency: MVR (Maldivian Rufiyaa)
    All rates are approximate and should be updated regularly
    """

    # Common exchange rates (as of typical values - UPDATE THESE)
    rates = [
        # USD to other currencies
        ('USD', 'MVR', Decimal('15.42')),  # 1 USD = 15.42 MVR (pegged rate)
        ('MVR', 'USD', Decimal('0.0649')), # 1 MVR = 0.0649 USD

        # USDT (Tether - typically 1:1 with USD)
        ('USDT', 'MVR', Decimal('15.42')),
        ('MVR', 'USDT', Decimal('0.0649')),
        ('USDT', 'USD', Decimal('1.00')),
        ('USD', 'USDT', Decimal('1.00')),

        # BTC (Bitcoin - HIGHLY VARIABLE, update frequently)
        ('BTC', 'USD', Decimal('96000.00')),  # Example: 1 BTC = $96,000
        ('USD', 'BTC', Decimal('0.00001042')),
        ('BTC', 'MVR', Decimal('1480320.00')),  # 96000 * 15.42
        ('MVR', 'BTC', Decimal('0.000000676')),

        # Same currency (identity)
        ('USD', 'USD', Decimal('1.00')),
        ('MVR', 'MVR', Decimal('1.00')),
        ('USDT', 'USDT', Decimal('1.00')),
        ('BTC', 'BTC', Decimal('1.00')),
    ]

    print("Populating exchange rates...")
    print("-" * 60)

    created_count = 0
    updated_count = 0

    for currency_from, currency_to, rate in rates:
        try:
            # Try to get existing rate
            exchange_rate, created = ExchangeRate.objects.get_or_create(
                currency_from=currency_from,
                currency_to=currency_to,
                defaults={
                    'rate': rate,
                    'is_active': True,
                    'synced_to_sheets': False
                }
            )

            if created:
                created_count += 1
                print(f"✓ Created: {currency_from}/{currency_to} = {rate}")
            else:
                # Update existing rate
                if exchange_rate.rate != rate:
                    old_rate = exchange_rate.rate
                    exchange_rate.rate = rate
                    exchange_rate.is_active = True
                    exchange_rate.save()
                    updated_count += 1
                    print(f"↻ Updated: {currency_from}/{currency_to} = {rate} (was {old_rate})")
                else:
                    print(f"→ Exists:  {currency_from}/{currency_to} = {rate}")

        except Exception as e:
            print(f"✗ Error with {currency_from}/{currency_to}: {str(e)}")

    print("-" * 60)
    print(f"Summary:")
    print(f"  Created: {created_count} rates")
    print(f"  Updated: {updated_count} rates")
    print(f"  Total in DB: {ExchangeRate.objects.count()} rates")
    print()
    print("IMPORTANT NOTES:")
    print("  1. BTC rate is highly volatile - update it regularly!")
    print("  2. USD/MVR rate is pegged at ~15.42")
    print("  3. USDT is treated as 1:1 with USD")
    print("  4. You can update rates using the Django admin panel")
    print()
    print("To view all rates:")
    print("  python manage.py shell")
    print("  from api.models import ExchangeRate")
    print("  for rate in ExchangeRate.objects.all():")
    print("      print(rate)")

if __name__ == '__main__':
    try:
        populate_exchange_rates()
        print("\n✓ Exchange rates populated successfully!")
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
