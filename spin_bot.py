"""
Telegram Spin Bot Module
Handles spin wheel functionality with counter-based rewards
Integrates with main Billionaires PPPoker Bot
"""

import random
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import hashlib
import time

logger = logging.getLogger(__name__)


class SpinBot:
    """Manages spin wheel functionality and rewards"""

    def __init__(self, sheets_manager, admin_user_id: int, timezone):
        """Initialize spin bot with sheets manager"""
        self.sheets = sheets_manager
        self.admin_user_id = admin_user_id
        self.timezone = timezone

        # Deposit to spins mapping (MVR -> spins)
        self.deposit_tiers = [
            (200, 1),
            (400, 2),
            (600, 3),
            (800, 4),
            (1000, 5),
            (1200, 6),
            (1400, 7),
            (1600, 8),
            (1800, 9),
            (2000, 25),
            (3000, 35),
            (4000, 45),
            (5000, 60),
            (6000, 75),
            (7000, 90),
            (8000, 105),
            (9000, 115),
            (10000, 120),
            (12000, 150),
            (14000, 180),
            (16000, 210),
            (18000, 230),
            (20000, 250),
        ]

        # PERSONAL Counter milestones (each user has own counter)
        # Users get ONE random prize when they complete a milestone
        # Prize appears at RANDOM spin within the milestone block
        self.milestones = [10, 50, 100, 500, 1000]

        # Prize wheel for ANIMATION ONLY (shown during spin, all give 0 chips)
        self.display_wheel = [
            {"name": "🎁 iPhone 17 Pro Max", "type": "display", "chips": 0, "weight": 5},
            {"name": "💻 MacBook Pro", "type": "display", "chips": 0, "weight": 5},
            {"name": "⌚ Apple Watch Ultra", "type": "display", "chips": 0, "weight": 10},
            {"name": "🎧 AirPods Pro", "type": "display", "chips": 0, "weight": 10},
            {"name": "💎 100 Points", "type": "display", "chips": 0, "weight": 15},
            {"name": "💰 50 Points", "type": "display", "chips": 0, "weight": 20},
            {"name": "🪙 25 Points", "type": "display", "chips": 0, "weight": 15},
            {"name": "🎯 10 Points", "type": "display", "chips": 0, "weight": 20},
        ]

        # REAL prize pool (given at milestones)
        # These are the ONLY real rewards users can actually get
        self.prize_pool = [
            {"name": "🏆 500 Chips", "chips": 500, "weight": 1},      # 0.01% (very rare jackpot)
            {"name": "💰 250 Chips", "chips": 250, "weight": 100},    # 1%
            {"name": "💎 100 Chips", "chips": 100, "weight": 200},    # 2%
            {"name": "💵 50 Chips", "chips": 50, "weight": 300},      # 3%
            {"name": "🪙 25 Chips", "chips": 25, "weight": 400},      # 4%
            {"name": "🎯 10 Chips", "chips": 10, "weight": 500},      # 5%
        ]

        # Anti-cheat tracking
        self.recent_spins = {}  # user_id: [(timestamp, hash), ...]

    def calculate_spins_from_deposit(self, amount_mvr: float) -> int:
        """Calculate spins based on deposit amount"""
        if amount_mvr >= 20000:
            return 250

        for threshold, spins in reversed(self.deposit_tiers):
            if amount_mvr >= threshold:
                return spins

        return 0

    def _generate_spin_hash(self, user_id: int, timestamp: float) -> str:
        """Generate unique hash for spin to prevent duplicates"""
        data = f"{user_id}_{timestamp}_{random.random()}"
        return hashlib.sha256(data.encode()).hexdigest()

    def _check_anti_cheat(self, user_id: int) -> Tuple[bool, str]:
        """Check for suspicious spinning behavior"""
        current_time = time.time()

        # Clean old entries (older than 60 seconds)
        if user_id in self.recent_spins:
            self.recent_spins[user_id] = [
                (ts, h) for ts, h in self.recent_spins[user_id]
                if current_time - ts < 60
            ]
        else:
            self.recent_spins[user_id] = []

        # Check for rapid spinning (more than 50 spins in 60 seconds is suspicious)
        if len(self.recent_spins[user_id]) > 50:
            return False, "⚠️ Too many spins in short time. Please wait a moment."

        return True, ""

    def spin_wheel(self, user_id: int) -> Optional[Dict]:
        """Spin the wheel for ANIMATION ONLY (returns display prize, 0 chips)"""
        # Anti-cheat check
        is_valid, error_msg = self._check_anti_cheat(user_id)
        if not is_valid:
            return None

        # Calculate total weight from display wheel
        total_weight = sum(prize['weight'] for prize in self.display_wheel)

        # Random selection based on weights
        rand = random.randint(1, total_weight)
        current_weight = 0

        for prize in self.display_wheel:
            current_weight += prize['weight']
            if rand <= current_weight:
                # Generate spin hash
                timestamp = time.time()
                spin_hash = self._generate_spin_hash(user_id, timestamp)

                # Track spin for anti-cheat
                if user_id not in self.recent_spins:
                    self.recent_spins[user_id] = []
                self.recent_spins[user_id].append((timestamp, spin_hash))

                return {
                    'prize': prize['name'],
                    'type': 'display',
                    'chips': 0,  # Always 0 for display
                    'hash': spin_hash,
                    'timestamp': timestamp
                }

        return None

    def get_milestone_prize(self) -> Dict:
        """Get a REAL prize from prize pool (for milestone rewards)"""
        # Calculate total weight from prize pool
        total_weight = sum(prize['weight'] for prize in self.prize_pool)

        # Random selection based on weights
        rand = random.randint(1, total_weight)
        current_weight = 0

        for prize in self.prize_pool:
            current_weight += prize['weight']
            if rand <= current_weight:
                return {
                    'name': prize['name'],
                    'chips': prize['chips']
                }

        # Fallback
        return {'name': '🎯 10 Chips', 'chips': 10}

    def should_give_milestone_reward(self, user_id: int, current_spin_in_block: int, milestone: int) -> bool:
        """
        Determine if user should get milestone reward on THIS spin
        Prize is given at a RANDOM spin within the milestone block
        Example: In 10-spin block, prize could appear at spin 1, 3, 7, or 10 (random)
        """
        # Generate a pseudo-random target spin for this user/milestone
        # Uses user_id and milestone to ensure same user gets prize at same position
        seed_value = user_id + milestone
        random.seed(seed_value)
        target_spin = random.randint(1, milestone)
        random.seed()  # Reset seed

        return current_spin_in_block == target_spin

    async def process_spin(self, user_id: int, username: str, spin_count: int = 1) -> Dict:
        """Process one or multiple spins for a user"""
        try:
            # Get user's available spins
            user_data = self.sheets.get_spin_user(user_id)

            if not user_data:
                return {
                    'success': False,
                    'message': "❌ You don't have any spins available!\n\nDeposit to get free spins! 💰"
                }

            available_spins = user_data.get('available_spins', 0)

            if available_spins < spin_count:
                return {
                    'success': False,
                    'message': f"❌ You only have {available_spins} spin(s) available!\n\nYou need {spin_count} spins."
                }

            # Process spins
            results = []
            total_chips = 0
            milestone_prize = None
            current_total = user_data.get('total_spins_used', 0)

            for i in range(spin_count):
                current_total += 1

                # Spin the wheel (just for animation, gives 0 chips)
                prize = self.spin_wheel(user_id)
                if prize:
                    results.append(prize)

                    # Log spin
                    self.sheets.log_spin(
                        user_id=user_id,
                        username=username,
                        prize=prize['prize'],
                        prize_type=prize['type'],
                        chips=0,  # Always 0
                        spin_hash=prize['hash']
                    )

                # Check if this spin should trigger a milestone reward
                # Start from smallest milestone to ensure proper reward order
                for milestone in sorted(self.milestones):
                    # Calculate which spin we are in the current milestone block
                    current_spin_in_block = ((current_total - 1) % milestone) + 1

                    # We're within this milestone's block
                    if current_spin_in_block <= milestone:
                        # Check if we should give reward at this specific spin
                        if self.should_give_milestone_reward(user_id, current_spin_in_block, milestone):
                            # Get random prize from prize pool
                            prize_won = self.get_milestone_prize()
                            milestone_prize = prize_won
                            total_chips += prize_won['chips']

                            # Calculate which milestone block we're in (1st, 2nd, 3rd, etc.)
                            milestone_count = (current_total - 1) // milestone + 1

                            # Log milestone reward
                            self.sheets.log_milestone_reward(
                                user_id=user_id,
                                username=username,
                                milestone_type=f'{milestone}_spins',
                                milestone_count=milestone_count,
                                chips_awarded=prize_won['chips'],
                                triggered_at=current_total
                            )
                            break  # Only give one milestone reward per spin

            # Update user's spin count
            new_available = available_spins - spin_count

            self.sheets.update_spin_user(
                user_id=user_id,
                available_spins=new_available,
                total_spins_used=current_total,
                total_chips_earned=user_data.get('total_chips_earned', 0) + total_chips
            )

            return {
                'success': True,
                'results': results,
                'milestone_prize': milestone_prize,
                'total_chips': total_chips,
                'available_spins': new_available,
                'total_spins_used': current_total,
                'total_chips_earned': user_data.get('total_chips_earned', 0) + total_chips
            }

        except Exception as e:
            logger.error(f"Error processing spin: {e}")
            return {
                'success': False,
                'message': "❌ Error processing spin. Please try again."
            }

    async def add_spins_from_deposit(self, user_id: int, username: str, amount_mvr: float) -> int:
        """Add spins to user based on deposit amount"""
        try:
            spins_to_add = self.calculate_spins_from_deposit(amount_mvr)

            if spins_to_add > 0:
                # Get or create user
                user_data = self.sheets.get_spin_user(user_id)

                if user_data:
                    new_available = user_data.get('available_spins', 0) + spins_to_add
                    new_total_deposit = user_data.get('total_deposit', 0) + amount_mvr

                    self.sheets.update_spin_user(
                        user_id=user_id,
                        available_spins=new_available,
                        total_deposit=new_total_deposit
                    )
                else:
                    # Create new user
                    self.sheets.create_spin_user(
                        user_id=user_id,
                        username=username,
                        available_spins=spins_to_add,
                        total_deposit=amount_mvr
                    )

                logger.info(f"Added {spins_to_add} spins to user {user_id} for deposit of {amount_mvr} MVR")

            return spins_to_add

        except Exception as e:
            logger.error(f"Error adding spins from deposit: {e}")
            return 0


# Command Handlers

async def freespins_command(update: Update, context: ContextTypes.DEFAULT_TYPE, spin_bot: SpinBot):
    """Handle /freespins command"""
    user = update.effective_user

    try:
        # Get user's spin data
        user_data = spin_bot.sheets.get_spin_user(user.id)

        if not user_data or user_data.get('available_spins', 0) == 0:
            await update.message.reply_text(
                "━━━━━━━━━━━━━━━━━━\n"
                "🎰 *FREE SPINS* 🎰\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                "💫 *No spins available right now\\!*\n\n"
                "💰 Make a deposit to unlock free spins\\!\n"
                "🔥 More deposit → More spins → More prizes\\!\n\n"
                "🎁 *Win Amazing Prizes:*\n"
                "💎 Chips\n"
                "📱 iPhone 17 Pro Max\n"
                "💻 MacBook Pro\n"
                "⌚ Apple Watch Ultra\n"
                "🎧 AirPods Pro\n"
                "✨ \\& Many More\\!\n\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "👉 Use /deposit to get started\\!\n"
                "━━━━━━━━━━━━━━━━━━",
                parse_mode='MarkdownV2'
            )
            return

        available = user_data.get('available_spins', 0)
        total_used = user_data.get('total_spins_used', 0)
        total_chips = user_data.get('total_chips_earned', 0)

        # Create spin options keyboard
        keyboard = []

        # Single spin
        keyboard.append([InlineKeyboardButton("🎯 Spin 1x", callback_data="spin_1")])

        # Multi-spin options
        if available >= 10:
            keyboard.append([InlineKeyboardButton("🎰 Spin 10x", callback_data="spin_10")])

        if available >= 50:
            keyboard.append([InlineKeyboardButton("🔥 Spin 50x", callback_data="spin_50")])

        if available >= 100:
            keyboard.append([InlineKeyboardButton("💥 Spin 100x", callback_data="spin_100")])

        if available > 1:
            keyboard.append([InlineKeyboardButton(f"⚡ Spin ALL ({available}x)", callback_data=f"spin_all")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Escape username for MarkdownV2
        username_escaped = user.first_name.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')

        await update.message.reply_text(
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎰 *FREE SPINS* 🎰\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 *{username_escaped}*\n\n"
            f"🎯 Available Spins: *{available}*\n"
            f"💎 Total Chips: *{total_chips}*\n\n"
            f"🎁 *Prize Wheel:*\n"
            f"💰 Chips\n"
            f"📱 iPhone 17 Pro Max\n"
            f"💻 MacBook Pro\n"
            f"⌚ Apple Watch Ultra\n"
            f"🎧 AirPods Pro\n"
            f"✨ \\& Many More Surprises\\!\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚡ *Choose Your Spins:* ⚡\n"
            f"━━━━━━━━━━━━━━━━━━",
            parse_mode='MarkdownV2',
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Error in freespins command: {e}")
        await update.message.reply_text("❌ Error loading spin data. Please try again.")


async def spin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, spin_bot: SpinBot, admin_user_id: int):
    """Handle spin button callbacks"""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    data = query.data

    try:
        # Parse spin count
        if data == "spin_all":
            user_data = spin_bot.sheets.get_spin_user(user.id)
            spin_count = user_data.get('available_spins', 0) if user_data else 0
        else:
            spin_count = int(data.split('_')[1])

        if spin_count == 0:
            await query.edit_message_text("❌ No spins available!")
            return

        # Show processing message
        await query.edit_message_text(f"🎰 Spinning {spin_count}x... Please wait! 🎲")

        # Process spins
        result = await spin_bot.process_spin(user.id, user.username or user.first_name, spin_count)

        if not result['success']:
            await query.edit_message_text(result['message'])
            return

        # Format results message
        if result.get('milestone_prize'):
            # WON A PRIZE - Big celebration!
            prize = result['milestone_prize']
            message = f"━━━━━━━━━━━━━━━━━━\n"
            message += f"🎊 *JACKPOT WINNER* 🎊\n"
            message += f"━━━━━━━━━━━━━━━━━━\n\n"
            message += f"🔥 *{prize['name']}* 🔥\n\n"
            message += f"💰 *\\+{prize['chips']} CHIPS* 💰\n"
            message += f"✨ Added to your balance\\! ✨\n\n"
            message += f"━━━━━━━━━━━━━━━━━━\n"
            message += f"👤 {user.first_name}\n"
            message += f"🎲 Spins Used: {spin_count}\n"
            message += f"💎 Total Earned: *{result['total_chips_earned']} chips*\n"
            message += f"🎯 Spins Left: *{result['available_spins']}*\n"
            message += f"━━━━━━━━━━━━━━━━━━\n\n"
            message += f"🎰 Keep spinning for more prizes\\!"
        else:
            # No prize - Keep it exciting
            message = f"━━━━━━━━━━━━━━━━━━\n"
            message += f"🎰 *SPIN COMPLETE* 🎰\n"
            message += f"━━━━━━━━━━━━━━━━━━\n\n"
            message += f"😎 *Every spin is a new chance…*\n"
            message += f"💫 *Your next one could be legendary\\!*\n\n"
            message += f"━━━━━━━━━━━━━━━━━━\n"
            message += f"👤 {user.first_name}\n"
            message += f"🎲 Spins Used: {spin_count}\n"
            message += f"💎 Total Earned: *{result['total_chips_earned']} chips*\n"
            message += f"🎯 Spins Left: *{result['available_spins']}*\n"
            message += f"━━━━━━━━━━━━━━━━━━\n\n"
            message += f"🔥 Try again\\! Fortune favors the bold\\!"

        # Create keyboard for more spins
        keyboard = [[InlineKeyboardButton("🎰 Spin Again", callback_data="spin_again")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            message,
            parse_mode='MarkdownV2',
            reply_markup=reply_markup if result['available_spins'] > 0 else None
        )

    except Exception as e:
        logger.error(f"Error in spin callback: {e}")
        await query.edit_message_text("❌ Error processing spin. Please try again.")


async def spin_again_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, spin_bot: SpinBot):
    """Handle spin again button"""
    query = update.callback_query
    await query.answer()

    # Call freespins command logic
    user = query.from_user

    try:
        user_data = spin_bot.sheets.get_spin_user(user.id)

        if not user_data or user_data.get('available_spins', 0) == 0:
            await query.edit_message_text(
                "❌ You don't have any spins left!\n\n"
                "Use /deposit to make a deposit and get more free spins!"
            )
            return

        available = user_data.get('available_spins', 0)
        total_used = user_data.get('total_spins_used', 0)
        total_chips = user_data.get('total_chips_earned', 0)

        # Create spin options keyboard
        keyboard = []
        keyboard.append([InlineKeyboardButton("🎯 Spin 1x", callback_data="spin_1")])

        if available >= 10:
            keyboard.append([InlineKeyboardButton("🎰 Spin 10x", callback_data="spin_10")])

        if available >= 50:
            keyboard.append([InlineKeyboardButton("🔥 Spin 50x", callback_data="spin_50")])

        if available >= 100:
            keyboard.append([InlineKeyboardButton("💥 Spin 100x", callback_data="spin_100")])

        if available > 1:
            keyboard.append([InlineKeyboardButton(f"⚡ Spin ALL ({available}x)", callback_data=f"spin_all")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🎰 *FREE SPINS* 🎰\n\n"
            f"👤 {user.first_name}\n\n"
            f"🎲 Available Spins: *{available}*\n"
            f"📊 Total Spins Used: *{total_used}*\n"
            f"💎 Total Chips Earned: *{total_chips}*\n\n"
            f"⭐ Choose how many spins:",
            parse_mode='MarkdownV2',
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Error in spin again: {e}")
        await query.edit_message_text("❌ Error loading spin data. Please try again.")


# Admin Commands

async def pendingspins_command(update: Update, context: ContextTypes.DEFAULT_TYPE, spin_bot: SpinBot, is_admin_func):
    """Admin command to view pending spin rewards"""
    user = update.effective_user

    if not is_admin_func(user.id):
        await update.message.reply_text("❌ Admin access required!")
        return

    try:
        # Get pending rewards (display prizes)
        pending = spin_bot.sheets.get_pending_spin_rewards()

        if not pending:
            await update.message.reply_text("✅ No pending spin rewards!")
            return

        message = "🎰 *PENDING SPIN REWARDS* 🎰\n\n"

        for idx, reward in enumerate(pending, 1):
            message += f"*{idx}\\. User:* {reward['username']}\n"
            message += f"   🆔 `{reward['user_id']}`\n"
            message += f"   🎁 Prize: {reward['prize']}\n"
            message += f"   💎 Chips: {reward['chips']}\n"
            message += f"   📅 Date: {reward['date']}\n"
            message += f"   🔖 ID: `{reward['spin_id']}`\n\n"

        message += "Use `/approvespin <spin_id>` to approve a reward\\."

        await update.message.reply_text(message, parse_mode='MarkdownV2')

    except Exception as e:
        logger.error(f"Error in pendingspins command: {e}")
        await update.message.reply_text("❌ Error fetching pending rewards.")


async def approvespin_command(update: Update, context: ContextTypes.DEFAULT_TYPE, spin_bot: SpinBot, is_admin_func):
    """Admin command to approve a spin reward"""
    user = update.effective_user

    if not is_admin_func(user.id):
        await update.message.reply_text("❌ Admin access required!")
        return

    if not context.args:
        await update.message.reply_text("❌ Usage: /approvespin <spin_id>")
        return

    spin_id = context.args[0]

    try:
        # Get spin details
        spin_data = spin_bot.sheets.get_spin_by_id(spin_id)

        if not spin_data:
            await update.message.reply_text("❌ Spin ID not found!")
            return

        if spin_data.get('approved'):
            await update.message.reply_text("⚠️ This reward was already approved!")
            return

        # Mark as approved
        spin_bot.sheets.approve_spin_reward(spin_id, user.id, user.username or user.first_name)

        # Notify user
        try:
            user_message = (
                f"✅ *REWARD APPROVED* ✅\n\n"
                f"🎁 Your spin reward has been approved\\!\n\n"
                f"Prize: {spin_data['prize']}\n"
                f"💎 Chips: *{spin_data['chips']}*\n\n"
                f"Your chips have been added to your PPPoker account\\!\n"
                f"Thank you for playing\\! 🎰"
            )

            await context.bot.send_message(
                chat_id=spin_data['user_id'],
                text=user_message,
                parse_mode='MarkdownV2'
            )
        except Exception as e:
            logger.error(f"Error notifying user: {e}")

        await update.message.reply_text(
            f"✅ Reward approved\\!\n\n"
            f"User: {spin_data['username']}\n"
            f"Prize: {spin_data['prize']}\n"
            f"Chips: {spin_data['chips']}\n\n"
            f"User has been notified\\.",
            parse_mode='MarkdownV2'
        )

    except Exception as e:
        logger.error(f"Error approving spin: {e}")
        await update.message.reply_text("❌ Error approving reward.")


async def addspins_command(update: Update, context: ContextTypes.DEFAULT_TYPE, spin_bot: SpinBot, is_admin_func):
    """Admin command to manually add spins to a user"""
    user = update.effective_user

    if not is_admin_func(user.id):
        await update.message.reply_text("❌ Admin access required!")
        return

    if len(context.args) < 2:
        await update.message.reply_text("❌ Usage: /addspins <user_id> <spins>")
        return

    try:
        target_user_id = int(context.args[0])
        spins_to_add = int(context.args[1])

        if spins_to_add <= 0:
            await update.message.reply_text("❌ Spins must be positive!")
            return

        # Get or create user
        user_data = spin_bot.sheets.get_spin_user(target_user_id)

        if user_data:
            new_available = user_data.get('available_spins', 0) + spins_to_add
            spin_bot.sheets.update_spin_user(
                user_id=target_user_id,
                available_spins=new_available
            )
        else:
            spin_bot.sheets.create_spin_user(
                user_id=target_user_id,
                username="Unknown",
                available_spins=spins_to_add
            )

        await update.message.reply_text(
            f"✅ Added {spins_to_add} spins to user {target_user_id}!"
        )

        # Notify user
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"🎁 You received {spins_to_add} free spins!\n\nUse /freespins to play!"
            )
        except:
            pass

    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or spin count!")
    except Exception as e:
        logger.error(f"Error adding spins: {e}")
        await update.message.reply_text("❌ Error adding spins.")


async def spinsstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE, spin_bot: SpinBot, is_admin_func):
    """Admin command to view spin statistics"""
    user = update.effective_user

    if not is_admin_func(user.id):
        await update.message.reply_text("❌ Admin access required!")
        return

    try:
        stats = spin_bot.sheets.get_spin_statistics()

        message = "📊 *SPIN BOT STATISTICS* 📊\n\n"
        message += f"👥 Total Users: *{stats['total_users']}*\n"
        message += f"🎲 Total Spins Used: *{stats['total_spins_used']}*\n"
        message += f"💎 Total Chips Awarded: *{stats['total_chips_awarded']}*\n"
        message += f"🎁 Pending Rewards: *{stats['pending_rewards']}*\n"
        message += f"✅ Approved Rewards: *{stats['approved_rewards']}*\n\n"
        message += f"🔝 *Top Spinners:*\n"

        for idx, user_stat in enumerate(stats['top_users'][:5], 1):
            message += f"{idx}\\. {user_stat['username']} \\- {user_stat['total_spins']} spins\n"

        await update.message.reply_text(message, parse_mode='MarkdownV2')

    except Exception as e:
        logger.error(f"Error in spinsstats command: {e}")
        await update.message.reply_text("❌ Error fetching statistics.")
