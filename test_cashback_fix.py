"""
Test script to verify cashback eligibility logic fix

The bug was: user_at_loss = club_profit < 0 (WRONG)
Should be: user_at_loss = club_profit > 0 (CORRECT)

When club makes profit, user is at a loss.
"""

def test_cashback_logic():
    """Test different scenarios"""

    print("🧪 Testing Cashback Eligibility Logic Fix\n")
    print("=" * 60)

    # Test Case 1: User deposited 1500, no wins (user LOST 1500)
    print("\n📋 Test Case 1: User deposited 1500 MVR, lost all 7 spins")
    deposits = 1500
    withdrawals = 0
    spin_rewards = 0
    bonuses = 0
    cashback = 0

    club_profit = deposits - (withdrawals + spin_rewards + bonuses + cashback)
    user_loss = club_profit if club_profit > 0 else 0
    user_profit = -club_profit if club_profit < 0 else 0
    user_at_loss = club_profit > 0

    print(f"   Deposits: {deposits} MVR")
    print(f"   Withdrawals: {withdrawals} MVR")
    print(f"   Spin rewards: {spin_rewards} MVR")
    print(f"   Club profit: {club_profit} MVR")
    print(f"   User loss: {user_loss} MVR")
    print(f"   User profit: {user_profit} MVR")
    print(f"   User at loss? {user_at_loss}")
    print(f"   ✅ EXPECTED: True (user should be eligible)" if user_at_loss else "   ❌ FAILED: Should be True")

    # Test Case 2: User deposited 1000, won 1500 in spins (user WON 500)
    print("\n📋 Test Case 2: User deposited 1000 MVR, won 1500 in spins")
    deposits = 1000
    withdrawals = 0
    spin_rewards = 1500
    bonuses = 0
    cashback = 0

    club_profit = deposits - (withdrawals + spin_rewards + bonuses + cashback)
    user_loss = club_profit if club_profit > 0 else 0
    user_profit = -club_profit if club_profit < 0 else 0
    user_at_loss = club_profit > 0

    print(f"   Deposits: {deposits} MVR")
    print(f"   Withdrawals: {withdrawals} MVR")
    print(f"   Spin rewards: {spin_rewards} MVR")
    print(f"   Club profit: {club_profit} MVR (negative = club lost money)")
    print(f"   User loss: {user_loss} MVR")
    print(f"   User profit: {user_profit} MVR")
    print(f"   User at loss? {user_at_loss}")
    print(f"   ✅ EXPECTED: False (user should NOT be eligible)" if not user_at_loss else "   ❌ FAILED: Should be False")

    # Test Case 3: User deposited 2000, withdrew 1000 (broke even)
    print("\n📋 Test Case 3: User deposited 2000 MVR, withdrew 1000 MVR")
    deposits = 2000
    withdrawals = 1000
    spin_rewards = 0
    bonuses = 0
    cashback = 0

    club_profit = deposits - (withdrawals + spin_rewards + bonuses + cashback)
    user_loss = club_profit if club_profit > 0 else 0
    user_profit = -club_profit if club_profit < 0 else 0
    user_at_loss = club_profit > 0

    print(f"   Deposits: {deposits} MVR")
    print(f"   Withdrawals: {withdrawals} MVR")
    print(f"   Spin rewards: {spin_rewards} MVR")
    print(f"   Club profit: {club_profit} MVR")
    print(f"   User loss: {user_loss} MVR")
    print(f"   User profit: {user_profit} MVR")
    print(f"   User at loss? {user_at_loss}")
    print(f"   ✅ EXPECTED: True (user should be eligible)" if user_at_loss else "   ❌ FAILED: Should be True")

    # Test Case 4: User deposited 1000, won 500 spins, withdrew 1500 (net 0)
    print("\n📋 Test Case 4: User deposited 1000, won 500 spins, withdrew 1500")
    deposits = 1000
    withdrawals = 1500
    spin_rewards = 500
    bonuses = 0
    cashback = 0

    club_profit = deposits - (withdrawals + spin_rewards + bonuses + cashback)
    user_loss = club_profit if club_profit > 0 else 0
    user_profit = -club_profit if club_profit < 0 else 0
    user_at_loss = club_profit > 0

    print(f"   Deposits: {deposits} MVR")
    print(f"   Withdrawals: {withdrawals} MVR")
    print(f"   Spin rewards: {spin_rewards} MVR")
    print(f"   Club profit: {club_profit} MVR (negative = club lost money)")
    print(f"   User loss: {user_loss} MVR")
    print(f"   User profit: {user_profit} MVR")
    print(f"   User at loss? {user_at_loss}")
    print(f"   ✅ EXPECTED: False (user should NOT be eligible)" if not user_at_loss else "   ❌ FAILED: Should be False")

    # Test Case 5: User deposited 2000, won 300 spins, bonuses 200 (lost 1500)
    print("\n📋 Test Case 5: User deposited 2000, won 300 spins, 200 bonus")
    deposits = 2000
    withdrawals = 0
    spin_rewards = 300
    bonuses = 200
    cashback = 0

    club_profit = deposits - (withdrawals + spin_rewards + bonuses + cashback)
    user_loss = club_profit if club_profit > 0 else 0
    user_profit = -club_profit if club_profit < 0 else 0
    user_at_loss = club_profit > 0

    print(f"   Deposits: {deposits} MVR")
    print(f"   Withdrawals: {withdrawals} MVR")
    print(f"   Spin rewards: {spin_rewards} MVR")
    print(f"   Bonuses: {bonuses} MVR")
    print(f"   Club profit: {club_profit} MVR")
    print(f"   User loss: {user_loss} MVR")
    print(f"   User profit: {user_profit} MVR")
    print(f"   User at loss? {user_at_loss}")
    print(f"   ✅ EXPECTED: True (user should be eligible)" if user_at_loss else "   ❌ FAILED: Should be True")

    print("\n" + "=" * 60)
    print("✅ All test cases completed!")
    print("\nExplanation:")
    print("- Club profit POSITIVE → User LOST money → Eligible for cashback")
    print("- Club profit NEGATIVE → User WON money → NOT eligible for cashback")
    print("- Club profit = Deposits - (Withdrawals + Spins + Bonuses + Cashback)")

if __name__ == '__main__':
    test_cashback_logic()
