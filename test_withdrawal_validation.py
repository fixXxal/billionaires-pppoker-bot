#!/usr/bin/env python3
"""
Test withdrawal validation scenarios
Minimum withdrawal: 200 MVR
"""

def test_withdrawal_scenarios():
    print("=" * 60)
    print("WITHDRAWAL VALIDATION TEST SCENARIOS")
    print("Minimum Withdrawal: 200 MVR")
    print("=" * 60)

    scenarios = [
        {
            "name": "User deposits 500 MVR, withdraws 100 MVR",
            "balance": 500,
            "withdrawal_amount": 100,
            "should_pass": False,
            "reason": "Below minimum (200 MVR)"
        },
        {
            "name": "User deposits 500 MVR, withdraws 200 MVR",
            "balance": 500,
            "withdrawal_amount": 200,
            "should_pass": True,
            "reason": "Exactly minimum (200 MVR)"
        },
        {
            "name": "User deposits 500 MVR, withdraws 300 MVR",
            "balance": 500,
            "withdrawal_amount": 300,
            "should_pass": True,
            "reason": "Above minimum"
        },
        {
            "name": "User deposits 1000 MVR, withdraws 500 MVR",
            "balance": 1000,
            "withdrawal_amount": 500,
            "should_pass": True,
            "reason": "Above minimum"
        },
        {
            "name": "User deposits 150 MVR, withdraws 150 MVR",
            "balance": 150,
            "withdrawal_amount": 150,
            "should_pass": False,
            "reason": "Below minimum (200 MVR)"
        },
        {
            "name": "User deposits 250 MVR, withdraws 250 MVR",
            "balance": 250,
            "withdrawal_amount": 250,
            "should_pass": True,
            "reason": "Above minimum"
        }
    ]

    MIN_WITHDRAWAL = 200

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i}. {scenario['name']}")
        print("-" * 60)

        balance = scenario['balance']
        withdrawal = scenario['withdrawal_amount']

        # Check minimum withdrawal
        passes_minimum = withdrawal >= MIN_WITHDRAWAL

        # Check balance
        has_balance = balance >= withdrawal

        # Overall result
        can_withdraw = passes_minimum and has_balance

        print(f"   Balance: {balance} MVR")
        print(f"   Withdrawal request: {withdrawal} MVR")
        print(f"   Minimum required: {MIN_WITHDRAWAL} MVR")
        print(f"   ")
        print(f"   Checks:")
        print(f"   └─ Minimum amount: {'✅ PASS' if passes_minimum else '❌ FAIL'}")
        print(f"   └─ Sufficient balance: {'✅ PASS' if has_balance else '❌ FAIL'}")
        print(f"   ")
        print(f"   Result: {'✅ ALLOWED' if can_withdraw else '❌ BLOCKED'}")
        print(f"   Reason: {scenario['reason']}")

        # Verify expectations
        if can_withdraw == scenario['should_pass']:
            print(f"   Test: ✅ CORRECT")
        else:
            print(f"   Test: ❌ WRONG (Expected: {scenario['should_pass']}, Got: {can_withdraw})")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"\n✅ Minimum Withdrawal: {MIN_WITHDRAWAL} MVR")
    print("\nValidation Rules:")
    print("1. Withdrawal amount >= 200 MVR")
    print("2. User balance >= Withdrawal amount")
    print("\nExample Messages:")
    print("\n❌ If withdrawal < 200 MVR:")
    print("   'Minimum Withdrawal: 200 MVR'")
    print("   'Your amount: 100.00 MVR'")
    print("   'Please enter at least 200 MVR'")
    print("\n❌ If balance insufficient:")
    print("   'Insufficient balance'")
    print("   'Balance: 150 MVR, Requested: 200 MVR'")
    print("\n✅ If all checks pass:")
    print("   'Withdrawal request submitted successfully!'")
    print("\n" + "=" * 60)

if __name__ == '__main__':
    test_withdrawal_scenarios()
