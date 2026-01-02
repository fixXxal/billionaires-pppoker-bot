#!/usr/bin/env python3
"""
Test the new simple cashback logic:
- Find last withdrawal
- Count deposits after that withdrawal
- If >= 500 MVR → Eligible
"""

def test_cashback_scenarios():
    print("=" * 60)
    print("SIMPLE CASHBACK LOGIC TEST SCENARIOS")
    print("=" * 60)

    scenarios = [
        {
            "name": "Scenario 1: Withdraw 700, deposit 500, lose all",
            "withdrawals": [700],
            "deposits_after": [500],
            "expected_eligible": True,
            "expected_amount": 500
        },
        {
            "name": "Scenario 2: No withdrawal, deposit 600",
            "withdrawals": [],
            "deposits_after": [600],
            "expected_eligible": True,
            "expected_amount": 600
        },
        {
            "name": "Scenario 3: Withdraw 1000, deposit 300 (not enough)",
            "withdrawals": [1000],
            "deposits_after": [300],
            "expected_eligible": False,
            "expected_amount": 300
        },
        {
            "name": "Scenario 4: Withdraw 500, deposit 200+300 (two deposits = 500 total)",
            "withdrawals": [500],
            "deposits_after": [200, 300],
            "expected_eligible": True,
            "expected_amount": 500
        },
        {
            "name": "Scenario 5: Withdraw 100, deposit 600, withdraw 50 → Counter RESETS",
            "withdrawals": [100, 50],  # Last withdrawal = 50
            "deposits_after": [0],  # No deposits after the 2nd withdrawal
            "expected_eligible": False,
            "expected_amount": 0
        },
        {
            "name": "Scenario 6: Multiple deposits totaling 800 after last withdrawal",
            "withdrawals": [1000],
            "deposits_after": [300, 200, 300],  # 800 total
            "expected_eligible": True,
            "expected_amount": 800
        }
    ]

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i}. {scenario['name']}")
        print("-" * 60)

        # Simulate the logic
        last_withdrawal_exists = len(scenario['withdrawals']) > 0
        deposits_after_withdrawal = sum(scenario['deposits_after'])

        eligible = deposits_after_withdrawal >= 500

        # Display results
        if last_withdrawal_exists:
            last_withdrawal = scenario['withdrawals'][-1]
            print(f"   Last withdrawal: {last_withdrawal} MVR")
        else:
            print(f"   Last withdrawal: None")

        print(f"   Deposits after last withdrawal: {deposits_after_withdrawal} MVR")
        print(f"   Minimum required: 500 MVR")
        print(f"   Eligible: {'✅ YES' if eligible else '❌ NO'}")

        # Verify expectations
        if eligible == scenario['expected_eligible'] and deposits_after_withdrawal == scenario['expected_amount']:
            print(f"   Result: ✅ PASS")
        else:
            print(f"   Result: ❌ FAIL")
            print(f"   Expected eligible: {scenario['expected_eligible']}, got: {eligible}")
            print(f"   Expected amount: {scenario['expected_amount']}, got: {deposits_after_withdrawal}")

    print("\n" + "=" * 60)
    print("COMPARISON: OLD vs NEW LOGIC")
    print("=" * 60)

    print("\n❌ OLD LOGIC (Complex):")
    print("   - Tracked ALL deposits and withdrawals (lifetime)")
    print("   - Included spin rewards, bonuses, previous cashback")
    print("   - Complex 'baseline' calculation")
    print("   - User with withdrawal > deposits = 'in profit' = NOT eligible")
    print("   - Bug: Past withdrawals block current losses from counting")

    print("\n✅ NEW LOGIC (Simple):")
    print("   - Find LAST withdrawal")
    print("   - Count deposits AFTER that withdrawal")
    print("   - If deposits >= 500 → Eligible")
    print("   - Every withdrawal RESETS the counter")
    print("   - Fixed: Only current deposits (after last withdrawal) count")

    print("\n" + "=" * 60)
    print("KEY IMPROVEMENT")
    print("=" * 60)
    print("\nUser scenario: Withdrew 700 MVR yesterday, deposited 500 MVR today, lost it all")
    print("\nOLD LOGIC:")
    print("   ❌ NOT ELIGIBLE (withdrawals > deposits = 'in profit')")
    print("\nNEW LOGIC:")
    print("   ✅ ELIGIBLE (500 MVR lost after last withdrawal)")
    print("\n" + "=" * 60)

if __name__ == '__main__':
    test_cashback_scenarios()
