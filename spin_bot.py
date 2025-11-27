"""
Telegram Spin Bot Module
Handles spin wheel functionality with counter-based rewards
Integrates with main Billionaires PPPoker Bot
"""

import random
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import hashlib
import time

logger = logging.getLogger(__name__)

# Global semaphore to limit concurrent animations (prevents Telegram rate limits)
# Only allows 5 animations to run simultaneously, others wait in queue
animation_semaphore = asyncio.Semaphore(5)


class TelegramRateLimiter:
    """
    Rate limiter to prevent Telegram API bans

    Telegram Limits:
    - Message sending: ~30 messages/second
    - Message editing: ~20 edits/second
    - We use conservative limits to ensure 100% safety
    """

    def __init__(self):
        # Conservative limits (lower than Telegram's actual limits for safety)
        self.edit_delay = 0.06  # ~16 edits/second (safe limit: 20/sec)
        self.send_delay = 0.04  # ~25 messages/second (safe limit: 30/sec)

        # Locks to ensure sequential operations
        self.edit_lock = asyncio.Lock()
        self.send_lock = asyncio.Lock()

        # Tracking for logging
        self.last_edit_time = 0
        self.last_send_time = 0
        self.edit_count = 0
        self.send_count = 0

    async def wait_for_edit(self):
        """Wait before performing a message edit"""
        async with self.edit_lock:
            current_time = time.time()
            time_since_last = current_time - self.last_edit_time

            if time_since_last < self.edit_delay:
                sleep_time = self.edit_delay - time_since_last
                await asyncio.sleep(sleep_time)

            self.last_edit_time = time.time()
            self.edit_count += 1

            if self.edit_count % 100 == 0:
                logger.info(f"Rate limiter: {self.edit_count} edits processed safely")

    async def wait_for_send(self):
        """Wait before sending a new message"""
        async with self.send_lock:
            current_time = time.time()
            time_since_last = current_time - self.last_send_time

            if time_since_last < self.send_delay:
                sleep_time = self.send_delay - time_since_last
                await asyncio.sleep(sleep_time)

            self.last_send_time = time.time()
            self.send_count += 1

            if self.send_count % 100 == 0:
                logger.info(f"Rate limiter: {self.send_count} messages sent safely")


# Global rate limiter instance
rate_limiter = TelegramRateLimiter()


class SpinBot:
    """Manages spin wheel functionality and rewards"""

    def __init__(self, api, admin_user_id: int, timezone):
        """Initialize spin bot with sheets manager"""
        self.api = api
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
        ]

        # REAL prize pool (given at milestones)
        # These are the ONLY real rewards users can actually get
        self.prize_pool = [
            {"name": "🏆 500 Chips", "chips": 500, "weight": 1},      # 0.01% (very rare jackpot)
            {"name": "💰 250 Chips", "chips": 250, "weight": 100},    # 1%
            {"name": "💎 100 Chips", "chips": 100, "weight": 200},    # 2%
            {"name": "💵 50 Chips", "chips": 50, "weight": 300},      # 3%
            {"name": "🪙 20 Chips", "chips": 20, "weight": 400},      # 4%
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
            user_data = self.api.get_spin_user(user_id)

            if not user_data:
                return {
                    'success': False,
                    'message': "❌ You don't have any spins available!\n\nDeposit to get free spins! 💰"
                }

            available_spins = user_data.get('available_spins', 0)
            user_pppoker_id = user_data.get('pppoker_id', '')

            # If PPPoker ID is not in Spin Users, try to get it from Deposits
            if not user_pppoker_id:
                user_pppoker_id = self.api.get_pppoker_id_from_deposits(user_id)
                # Update Spin Users with the PPPoker ID for future reference
                if user_pppoker_id:
                    self.api.update_spin_user(user_id=user_id, pppoker_id=user_pppoker_id)

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
                    # Display prizes are not logged - only for animation

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
                            self.api.log_milestone_reward(
                                user_id=user_id,
                                username=username,
                                milestone_type=f'{milestone}_spins',
                                milestone_count=milestone_count,
                                chips_awarded=prize_won['chips'],
                                triggered_at=current_total,
                                pppoker_id=user_pppoker_id
                            )
                            break  # Only give one milestone reward per spin

            # Check for Surprise Rewards (only for multi-spins: 10+)
            surprise_chips = 0
            got_surprise = False
            if spin_count >= 10:
                # 80% chance to get surprise reward, 20% chance to get nothing
                random.seed()  # Use true randomness
                chance = random.random()

                if chance < 0.80:  # 80% chance
                    # Give random chips between 1-20
                    surprise_chips = random.randint(1, 20)
                    got_surprise = True

                    # Log surprise reward as milestone (pending admin approval)
                    self.api.log_milestone_reward(
                        user_id=user_id,
                        username=username,
                        milestone_type='surprise_reward',
                        milestone_count=0,
                        chips_awarded=surprise_chips,
                        triggered_at=current_total,
                        pppoker_id=user_pppoker_id
                    )

            # Update user's spin count
            new_available = available_spins - spin_count

            # Update spin user (DON'T add surprise chips - pending approval!)
            final_chips = user_data.get('total_chips_earned', 0)

            self.api.update_spin_user(
                user_id=user_id,
                username=username,
                available_spins=new_available,
                total_spins_used=current_total,
                total_chips_earned=final_chips
            )

            return {
                'success': True,
                'results': results,
                'milestone_prize': milestone_prize,
                'total_chips': total_chips,  # Milestone chips (pending approval)
                'surprise_chips': surprise_chips if got_surprise else 0,
                'got_surprise': got_surprise,
                'available_spins': new_available,
                'total_spins_used': current_total,
                'total_chips_earned': final_chips
            }

        except Exception as e:
            logger.error(f"Error processing spin: {e}")
            return {
                'success': False,
                'message': "❌ Error processing spin. Please try again."
            }

    async def add_spins_from_deposit(self, user_id: int, username: str, amount_mvr: float, pppoker_id: str = '') -> int:
        """Add spins to user based on deposit amount"""
        try:
            spins_to_add = self.calculate_spins_from_deposit(amount_mvr)

            # Get or create user (do this for ALL deposits, not just ones that give spins)
            user_data = self.api.get_spin_user(user_id)

            if user_data:
                # Update existing user
                new_available = user_data.get('available_spins', 0) + spins_to_add
                new_total_deposit = user_data.get('total_deposit', 0) + amount_mvr

                self.api.update_spin_user(
                    user_id=user_id,
                    username=username,
                    available_spins=new_available,
                    total_deposit=new_total_deposit,
                    pppoker_id=pppoker_id  # Update PPPoker ID even if spins_to_add = 0
                )
            else:
                # Create new user (even if they get 0 spins, store their PPPoker ID)
                self.api.create_spin_user(
                    user_id=user_id,
                    username=username,
                    available_spins=spins_to_add,
                    total_deposit=amount_mvr,
                    pppoker_id=pppoker_id
                )

            if spins_to_add > 0:
                logger.info(f"Added {spins_to_add} spins to user {user_id} for deposit of {amount_mvr} MVR")
            else:
                logger.info(f"Deposit of {amount_mvr} MVR from user {user_id} recorded (no spins - below minimum)")

            return spins_to_add

        except Exception as e:
            logger.error(f"Error adding spins from deposit: {e}")
            return 0

    async def show_spin_animation(self, query, result, spin_count):
        """Show live spinning animation by editing message multiple times"""
        # Use semaphore to limit concurrent animations (prevents Telegram bans)
        # Max 5 animations at once, others wait in queue
        async with animation_semaphore:
            logger.info(f"Animation started for user {query.from_user.id} (queue position acquired)")

            # All possible prizes to show during animation (ALL fake + real prizes mixed)
            # This creates excitement by showing everything users could potentially win
            animation_sequence = [
                # REAL PRIZES (users can actually win these)
                "🎰 ⬆️ 🏆 500 Chips ⬇️ 🎲",
                "🎰 ⬆️ 💰 250 Chips ⬇️ 🎲",
                "🎰 ⬆️ 💎 100 Chips ⬇️ 🎲",
                "🎰 ⬆️ 💵 50 Chips ⬇️ 🎲",
                "🎰 ⬆️ 🪙 20 Chips ⬇️ 🎲",
                "🎰 ⬆️ 🎯 10 Chips ⬇️ 🎲",

                # FAKE DISPLAY PRIZES (physical items - shown for excitement, give 0 chips)
                "🎰 ⬆️ 📱 iPhone 17 Pro Max ⬇️ 🎲",
                "🎰 ⬆️ 💻 MacBook Pro ⬇️ 🎲",
                "🎰 ⬆️ ⌚ Apple Watch Ultra ⬇️ 🎲",
                "🎰 ⬆️ 🎧 AirPods Pro ⬇️ 🎲",
            ]

            # Randomize the sequence every time (different order each spin)
            random.shuffle(animation_sequence)

            # Determine final prize to show
            if result.get('milestone_prize'):
                final_prize = result['milestone_prize']['name']
            else:
                final_prize = "❌ Try Again"

            try:
                # Show spinning animation (6-8 edits) with rate limiting
                for i, frame in enumerate(animation_sequence[:7]):
                    try:
                        await rate_limiter.wait_for_edit()
                        await query.edit_message_text(frame)
                        # Gradually slow down the animation
                        if i < 3:
                            await asyncio.sleep(0.4)  # Fast spinning
                        elif i < 5:
                            await asyncio.sleep(0.6)  # Slowing down
                        else:
                            await asyncio.sleep(0.8)  # Almost stopped
                    except Exception as e:
                        logger.warning(f"Animation frame {i} failed: {e}")
                        # Continue even if one frame fails

                # Show final result for a moment before the full message
                try:
                    await rate_limiter.wait_for_edit()
                    await query.edit_message_text(f"🎊 {final_prize} 🎊")
                    await asyncio.sleep(1.0)
                except:
                    pass

            except Exception as e:
                logger.error(f"Error in spin animation: {e}")
                # Animation failed, continue to show results

            logger.info(f"Animation completed for user {query.from_user.id} (queue slot released)")


# Command Handlers

async def freespins_command(update: Update, context: ContextTypes.DEFAULT_TYPE, spin_bot: SpinBot):
    """Handle /freespins command"""
    user = update.effective_user

    try:
        # Get user's spin data
        user_data = spin_bot.api.get_spin_user(user.id)

        if not user_data or user_data.get('available_spins', 0) == 0:
            # Create deposit button
            keyboard = [[InlineKeyboardButton("💰 Make Deposit", callback_data="deposit_start")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "━━━━━━━━━━━━━━━━━━\n"
                "🎰 *FREE SPINS* 🎰\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                "💫 *No spins available right now\\!*\n\n"
                "💰 Make a deposit to unlock free spins\\!\n"
                "🔥 More deposit → More spins → More prizes\\!\n\n"
                "🎁 *Win Amazing Prizes:*\n"
                "🏆 500 Chips\n"
                "💰 250 Chips\n"
                "💎 100 Chips\n"
                "💵 50 Chips\n"
                "🪙 20 Chips\n"
                "🎯 10 Chips\n"
                "📱 iPhone 17 Pro Max\n"
                "💻 MacBook Pro\n"
                "⌚ Apple Watch Ultra\n"
                "🎧 AirPods Pro\n"
                "✨ Plus Surprise Rewards\\!\n\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "👉 Click button below to get started\\!\n"
                "━━━━━━━━━━━━━━━━━━",
                parse_mode='MarkdownV2',
                reply_markup=reply_markup
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
            f"🏆 500 Chips\n"
            f"💰 250 Chips\n"
            f"💎 100 Chips\n"
            f"💵 50 Chips\n"
            f"🪙 20 Chips\n"
            f"🎯 10 Chips\n"
            f"📱 iPhone 17 Pro Max\n"
            f"💻 MacBook Pro\n"
            f"⌚ Apple Watch Ultra\n"
            f"🎧 AirPods Pro\n"
            f"✨ Plus Surprise Rewards\\!\n\n"
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
            user_data = spin_bot.api.get_spin_user(user.id)
            spin_count = user_data.get('available_spins', 0) if user_data else 0
        else:
            spin_count = int(data.split('_')[1])

        if spin_count == 0:
            await rate_limiter.wait_for_edit()
            await query.edit_message_text("❌ No spins available!")
            return

        # Show processing message
        await rate_limiter.wait_for_edit()
        await query.edit_message_text(f"🎰 Spinning {spin_count}x... Please wait! 🎲")

        # Process spins
        result = await spin_bot.process_spin(user.id, user.username or user.first_name, spin_count)

        # Show spinning animation ONLY for single spins or if milestone prize won
        if spin_count == 1 or result.get('milestone_prize'):
            await spin_bot.show_spin_animation(query, result, spin_count)

        if not result['success']:
            await rate_limiter.wait_for_edit()
            await query.edit_message_text(result['message'])
            return

        # Escape username for MarkdownV2
        username_escaped = user.first_name.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')

        # Format results message
        if result.get('milestone_prize'):
            # WON A MILESTONE PRIZE - Big celebration!
            prize = result['milestone_prize']
            message = f"━━━━━━━━━━━━━━━━━━\n"
            message += f"🎊 *JACKPOT WINNER* 🎊\n"
            message += f"━━━━━━━━━━━━━━━━━━\n\n"
            message += f"🔥 *{prize['name']}* 🔥\n\n"
            message += f"💰 *{prize['chips']} CHIPS WON* 💰\n\n"
            message += f"⏳ *Pending Admin Approval*\n"
            message += f"✅ Your chips will be added to your PPPoker account once approved\\.\n"
            message += f"You'll be notified immediately\\! 🎉\n\n"

            # Add surprise reward if any
            if result.get('got_surprise'):
                message += f"✨ *BONUS SURPRISE\\!* ✨\n"
                message += f"🎁 Surprise Reward: *{result['surprise_chips']} chips*\\!\n"
                message += f"⏳ Pending admin approval\n\n"

            message += f"━━━━━━━━━━━━━━━━━━\n"
            message += f"👤 {username_escaped}\n"
            message += f"🎲 Spins Used: {spin_count}\n"
            message += f"💎 Total Chips: *{result['total_chips_earned']} chips*\n"
            message += f"🎯 Spins Left: *{result['available_spins']}*\n"
            message += f"━━━━━━━━━━━━━━━━━━\n\n"
            message += f"🎰 Keep spinning for more prizes\\!"
        else:
            # No milestone prize
            message = f"━━━━━━━━━━━━━━━━━━\n"
            message += f"🎰 *SPIN COMPLETE* 🎰\n"
            message += f"━━━━━━━━━━━━━━━━━━\n\n"

            # Check if got surprise reward
            if result.get('got_surprise'):
                message += f"✨ *SURPRISE REWARD\\!* ✨\n"
                message += f"🎁 You won *{result['surprise_chips']} chips*\\!\n\n"
                message += f"⏳ *Pending Admin Approval*\n"
                message += f"✅ Your chips will be added to your PPPoker account once approved\\.\n"
                message += f"You'll be notified immediately\\! 🎉\n\n"
            else:
                message += f"😎 *Every spin is a new chance…*\n"
                message += f"💫 *Your next one could be legendary\\!*\n\n"

            message += f"━━━━━━━━━━━━━━━━━━\n"
            message += f"👤 {username_escaped}\n"
            message += f"🎲 Spins Used: {spin_count}\n"
            message += f"💎 Total Chips: *{result['total_chips_earned']} chips*\n"
            message += f"🎯 Spins Left: *{result['available_spins']}*\n"
            message += f"━━━━━━━━━━━━━━━━━━\n\n"
            message += f"🔥 Try again\\! Fortune favors the bold\\!"

        # Create keyboard for more spins
        keyboard = [[InlineKeyboardButton("🎰 Spin Again", callback_data="spin_again")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await rate_limiter.wait_for_edit()
        await query.edit_message_text(
            message,
            parse_mode='MarkdownV2',
            reply_markup=reply_markup if result['available_spins'] > 0 else None
        )

        # Send notification to ALL admins if user won any prize
        if result.get('milestone_prize') or result.get('got_surprise'):
            # Get user's PPPoker ID from user data (stored in Spin Users sheet)
            user_data = spin_bot.api.get_spin_user(user.id)
            user_pppoker_id = user_data.get('pppoker_id', '') if user_data else ''

            # If PPPoker ID is not in Spin Users, try to get it from Deposits
            if not user_pppoker_id:
                user_pppoker_id = spin_bot.api.get_pppoker_id_from_deposits(user.id)

            # Set to "Not found" if still empty
            if not user_pppoker_id:
                user_pppoker_id = 'Not found'

            logger.info(f"PPPoker ID for user {user.id}: {user_pppoker_id}")

            # Build prize information
            prize_info = ""
            new_reward_chips = 0

            if result.get('milestone_prize'):
                prize = result['milestone_prize']
                prize_info += f"🎁 <b>Milestone:</b> {prize['name']} ({prize['chips']} chips)\n"
                new_reward_chips += prize['chips']

            if result.get('got_surprise'):
                prize_info += f"✨ <b>Surprise:</b> {result['surprise_chips']} chips\n"
                new_reward_chips += result['surprise_chips']

            # Get all pending rewards for this user to create approve button AND calculate balance
            try:
                # Small delay to ensure Google Sheets has processed the write
                import asyncio
                await asyncio.sleep(1.0)

                pending_rewards = spin_bot.api.get_pending_spin_rewards()
                logger.info(f"Total pending rewards in system: {len(pending_rewards)}")
                user_pending = [r for r in pending_rewards if str(r['user_id']) == str(user.id)]
                logger.info(f"Pending rewards for user {user.id}: {len(user_pending)}")

                if user_pending:
                    logger.info(f"User pending rewards: {user_pending}")

                # Calculate cumulative pending balance
                total_pending_balance = sum(int(r.get('chips', 0)) for r in user_pending)
                previous_pending = total_pending_balance - new_reward_chips

                # Build pending balance display
                if previous_pending > 0:
                    pending_display = f"💰 <b>Total Pending Balance:</b> <b>{total_pending_balance} chips</b>\n"
                    pending_display += f"   (Previous: {previous_pending} | New: {new_reward_chips})"
                else:
                    pending_display = f"💰 <b>Total Pending Balance:</b> <b>{total_pending_balance} chips</b>\n"
                    pending_display += f"   (New: {new_reward_chips} chips)"

                # Build admin message
                admin_message = (
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🎊 <b>NEW PRIZE WON!</b> 🎊\n"
                    f"━━━━━━━━━━━━━━━━━━\n\n"
                    f"👤 <b>User:</b> {user.first_name} (@{user.username if user.username else 'no username'})\n"
                    f"🆔 <b>Telegram ID:</b> <code>{user.id}</code>\n"
                    f"🎮 <b>PPPoker ID:</b> <code>{user_pppoker_id}</code>\n\n"
                    f"{prize_info}\n"
                    f"{pending_display}\n\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"⏳ Click button below to approve:"
                )

                # Create approve button with all spin IDs for this user
                keyboard = None
                if user_pending:
                    spin_ids = [r['spin_id'] for r in user_pending]
                    spin_ids_str = ','.join(spin_ids)
                    logger.info(f"Creating button with spin IDs: {spin_ids_str}")
                    keyboard = [[InlineKeyboardButton(
                        f"✅ Approve All ({total_pending_balance} chips)",
                        callback_data=f"approve_user_{user.id}_{spin_ids_str}"
                    )]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    logger.info(f"Button created successfully!")
                else:
                    # Fallback if we can't get pending rewards
                    logger.warning(f"No pending rewards found for user {user.id}")
                    reply_markup = None
            except Exception as e:
                logger.error(f"Error getting pending rewards for button: {e}")
                import traceback
                traceback.print_exc()
                # Fallback: show only new reward
                total_pending_balance = new_reward_chips
                pending_display = f"💰 <b>Total Pending Balance:</b> <b>{total_pending_balance} chips</b>\n"
                pending_display += f"   (New: {new_reward_chips} chips)"
                admin_message = (
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🎊 <b>NEW PRIZE WON!</b> 🎊\n"
                    f"━━━━━━━━━━━━━━━━━━\n\n"
                    f"👤 <b>User:</b> {user.first_name} (@{user.username if user.username else 'no username'})\n"
                    f"🆔 <b>Telegram ID:</b> <code>{user.id}</code>\n"
                    f"🎮 <b>PPPoker ID:</b> <code>{user_pppoker_id}</code>\n\n"
                    f"{prize_info}\n"
                    f"{pending_display}\n\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"⏳ Click button below to approve:"
                )
                reply_markup = None

            # Store notification message IDs for button removal later
            # Use a unique key based on user_id to track all pending rewards for this user
            notification_key = f"spin_reward_{user.id}"

            # Initialize storage if not exists
            if not hasattr(context.bot_data, 'spin_notification_messages'):
                context.bot_data['spin_notification_messages'] = {}

            if notification_key not in context.bot_data['spin_notification_messages']:
                context.bot_data['spin_notification_messages'][notification_key] = []

            # Send to super admin (with rate limiting)
            try:
                await rate_limiter.wait_for_send()
                msg = await context.bot.send_message(
                    chat_id=admin_user_id,
                    text=admin_message,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
                # Store message ID
                context.bot_data['spin_notification_messages'][notification_key].append((admin_user_id, msg.message_id))
                logger.info(f"Stored spin notification message ID for super admin")
            except Exception as e:
                logger.error(f"Failed to notify super admin: {e}")

            # Send to all regular admins (with rate limiting)
            try:
                admins_response = spin_bot.api.get_all_admins()

                # Handle paginated response from Django API
                if isinstance(admins_response, dict) and 'results' in admins_response:
                    admins = admins_response['results']
                else:
                    admins = admins_response

                logger.info(f"Found {len(admins)} regular admins to notify for spin reward")

                for admin in admins:
                    try:
                        await rate_limiter.wait_for_send()
                        msg = await context.bot.send_message(
                            chat_id=admin['admin_id'],
                            text=admin_message,
                            parse_mode='HTML',
                            reply_markup=reply_markup
                        )
                        # Store message ID
                        context.bot_data['spin_notification_messages'][notification_key].append((admin['admin_id'], msg.message_id))
                        logger.info(f"Stored spin notification message ID for admin {admin['admin_id']}")
                    except Exception as e:
                        logger.error(f"Failed to notify admin {admin['admin_id']}: {e}")
            except Exception as e:
                logger.error(f"Failed to get admin list: {e}")
                import traceback
                logger.error(traceback.format_exc())

    except Exception as e:
        logger.error(f"Error in spin callback: {e}")
        await rate_limiter.wait_for_edit()
        await query.edit_message_text("❌ Error processing spin. Please try again.")


async def spin_again_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, spin_bot: SpinBot):
    """Handle spin again button"""
    query = update.callback_query
    await query.answer()

    logger.info(f"Spin again button clicked by user {query.from_user.id}")

    # Call freespins command logic
    user = query.from_user

    try:
        user_data = spin_bot.api.get_spin_user(user.id)

        if not user_data or user_data.get('available_spins', 0) == 0:
            await rate_limiter.wait_for_edit()
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

        # Delete the old message and send a new one instead of editing
        # This avoids MarkdownV2 parsing issues when editing
        try:
            await query.delete_message()
        except:
            pass

        # Send new message with spin options
        await rate_limiter.wait_for_send()
        await query.message.reply_text(
            f"🎰 FREE SPINS 🎰\n\n"
            f"👤 {user.first_name}\n\n"
            f"🎲 Available Spins: {available}\n"
            f"📊 Total Spins Used: {total_used}\n"
            f"💎 Total Chips Earned: {total_chips}\n\n"
            f"⭐ Choose how many spins:",
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Error in spin again: {e}")
        import traceback
        traceback.print_exc()
        try:
            await rate_limiter.wait_for_edit()
            await query.edit_message_text("❌ Error loading spin data. Please try again.")
        except:
            await rate_limiter.wait_for_send()
            await query.message.reply_text("❌ Error loading spin data. Please try again.")


# Admin Commands

async def pendingspins_command(update: Update, context: ContextTypes.DEFAULT_TYPE, spin_bot: SpinBot, is_admin_func):
    """Admin command to view pending spin rewards"""
    user = update.effective_user

    if not is_admin_func(user.id):
        if update.callback_query:
            await update.callback_query.answer("❌ Admin access required!")
        else:
            await update.message.reply_text("❌ Admin access required!")
        return

    try:
        # Get pending rewards (display prizes)
        pending = spin_bot.api.get_pending_spin_rewards()

        if not pending:
            if update.callback_query:
                await update.callback_query.message.reply_text("✅ No pending spin rewards!")
            else:
                await update.message.reply_text("✅ No pending spin rewards!")
            return

        # Group rewards by user (from Spin History sheet)
        user_rewards = {}
        for reward in pending:
            user_id = reward.get('user_id')
            if user_id not in user_rewards:
                user_rewards[user_id] = {
                    'username': reward.get('username', 'Unknown'),
                    'user_id': user_id,
                    'pppoker_id': reward.get('pppoker_id', ''),
                    'rewards': [],
                    'total_chips': 0,
                    'row_numbers': []
                }
            user_rewards[user_id]['rewards'].append(reward)
            user_rewards[user_id]['total_chips'] += int(reward.get('chips', 0))
            user_rewards[user_id]['row_numbers'].append(reward.get('row_number'))  # Track row number for approval

        message = "━━━━━━━━━━━━━━━━━━\n"
        message += "🎰 *PENDING SPIN REWARDS* 🎰\n"
        message += "━━━━━━━━━━━━━━━━━━\n\n"

        for idx, (user_id, user_data) in enumerate(user_rewards.items(), 1):
            # Get PPPoker ID from user data
            user_pppoker_id = user_data['pppoker_id']

            # If PPPoker ID is not set, try to get it from Deposits
            if not user_pppoker_id:
                user_pppoker_id = spin_bot.api.get_pppoker_id_from_deposits(int(user_id))

            # Set to "Not found" if still empty
            if not user_pppoker_id:
                user_pppoker_id = 'Not found'

            message += f"*{idx}\\. {user_data['username']}*\n"
            message += f"👤 Telegram ID: `{user_id}`\n"
            message += f"🎮 PPPoker ID: `{user_pppoker_id}`\n\n"

            # List individual rewards
            for reward in user_data['rewards']:
                # Escape prize text for MarkdownV2
                prize_text = reward.get('prize', 'Unknown')
                prize_escaped = prize_text.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')
                message += f"  🎁 {prize_escaped}\n"

            message += f"\n💰 *TOTAL: {user_data['total_chips']} chips* \\({len(user_data['rewards'])} rewards\\)\n"
            message += f"━━━━━━━━━━━━━━━━━━\n\n"

        message += "Click to approve all rewards for user:"

        # Create inline buttons - ONE button per user to approve ALL their rewards
        keyboard = []
        for user_id, user_data in user_rewards.items():
            # Just send user_id - handler will fetch all pending spins for this user
            # This keeps callback_data under Telegram's 64-byte limit
            button_text = f"✅ Approve {user_data['username']} ({user_data['total_chips']} chips)"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"approve_spinhistory_{user_id}")])

        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

        # Send message based on whether it's from callback or command
        if update.callback_query:
            if reply_markup:
                await update.callback_query.message.reply_text(message, parse_mode='MarkdownV2', reply_markup=reply_markup)
            else:
                await update.callback_query.message.reply_text(message, parse_mode='MarkdownV2')
        else:
            if reply_markup:
                await update.message.reply_text(message, parse_mode='MarkdownV2', reply_markup=reply_markup)
            else:
                await update.message.reply_text(message, parse_mode='MarkdownV2')

    except Exception as e:
        logger.error(f"Error in pendingspins command: {e}")
        import traceback
        traceback.print_exc()
        if update.callback_query:
            try:
                await update.callback_query.message.reply_text(f"❌ Error fetching pending rewards.\n\nError: {str(e)}")
            except:
                await context.bot.send_message(
                    chat_id=update.callback_query.message.chat_id,
                    text=f"❌ Error fetching pending rewards.\n\nError: {str(e)}"
                )
        else:
            await update.message.reply_text(f"❌ Error fetching pending rewards.\n\nError: {str(e)}")


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
        spin_data = spin_bot.api.get_spin_by_id(spin_id)

        if not spin_data:
            await update.message.reply_text("❌ Spin ID not found!")
            return

        if spin_data.get('approved'):
            approved_by = spin_data.get('approved_by', 'Unknown admin')
            await update.message.reply_text(
                f"━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ *ALREADY APPROVED* ⚠️\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"This reward was already approved by:\n"
                f"👤 *{approved_by}*\n\n"
                f"Cannot approve twice\\!",
                parse_mode='MarkdownV2'
            )
            return

        # Mark as approved
        approver_name = user.username or user.first_name
        spin_bot.api.approve_spin_reward(spin_id, user.id, approver_name)

        # Update user's total approved chips
        user_data = spin_bot.api.get_spin_user(spin_data['user_id'])
        if user_data:
            current_chips = user_data.get('total_chips_earned', 0)
            new_total = current_chips + spin_data['chips']
            spin_bot.api.update_spin_user(
                user_id=spin_data['user_id'],
                username=spin_data.get('username', 'Unknown'),
                total_chips_earned=new_total
            )

        # Notify user
        try:
            user_message = (
                f"━━━━━━━━━━━━━━━━━━\n"
                f"✅ *REWARD APPROVED* ✅\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"🎊 Congratulations\\!\n\n"
                f"🎁 Prize: *{spin_data['prize']}*\n"
                f"💰 Chips: *{spin_data['chips']}*\n\n"
                f"✨ *Added to your balance\\!* ✨\n"
                f"Your chips have been credited to your PPPoker account\\!\n\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"Thank you for playing\\! 🎰"
            )

            await context.bot.send_message(
                chat_id=spin_data['user_id'],
                text=user_message,
                parse_mode='MarkdownV2'
            )
        except Exception as e:
            logger.error(f"Error notifying user: {e}")

        # Notify ALL admins about the approval
        admin_notification = (
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✅ <b>REWARD APPROVED</b> ✅\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>User:</b> {spin_data['username']}\n"
            f"🎁 <b>Prize:</b> {spin_data['prize']}\n"
            f"💎 <b>Chips:</b> {spin_data['chips']}\n\n"
            f"✅ <b>Approved by:</b> {approver_name}\n"
            f"🔖 <b>Spin ID:</b> <code>{spin_id}</code>\n\n"
            f"━━━━━━━━━━━━━━━━━━"
        )

        # Get admin_user_id from spin_bot
        try:
            # Send to super admin (if not the one who approved)
            if user.id != spin_bot.admin_user_id:
                try:
                    await context.bot.send_message(
                        chat_id=spin_bot.admin_user_id,
                        text=admin_notification,
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify super admin: {e}")

            # Send to all other admins
            admins_response = spin_bot.api.get_all_admins()

            # Handle paginated response from Django API
            if isinstance(admins_response, dict) and 'results' in admins_response:
                admins = admins_response['results']
            else:
                admins = admins_response

            logger.info(f"Notifying {len(admins)} regular admins about approval")

            for admin in admins:
                # Don't notify the admin who approved it
                if admin['admin_id'] != user.id:
                    try:
                        await context.bot.send_message(
                            chat_id=admin['admin_id'],
                            text=admin_notification,
                            parse_mode='HTML'
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify admin {admin['admin_id']}: {e}")
        except Exception as e:
            logger.error(f"Error notifying other admins: {e}")

        await update.message.reply_text(
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✅ *REWARD APPROVED* ✅\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 User: {spin_data['username']}\n"
            f"🎁 Prize: {spin_data['prize']}\n"
            f"💎 Chips: {spin_data['chips']}\n\n"
            f"✅ User has been notified\\!\n"
            f"💰 Manually add {spin_data['chips']} chips to PPPoker ID\\.",
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

        # Get or create spin user (Django API handles this)
        spin_user = spin_bot.api.get_or_create_spin_user(target_user_id)
        spin_user_id = spin_user.get('id')

        # Add spins using the Django API endpoint
        spin_bot.api.add_spins(spin_user_id, spins_to_add)

        await update.message.reply_text(
            f"✅ Added {spins_to_add} spins to user {target_user_id}!"
        )

        # Notify user
        try:
            # Create "Spin Now" button
            keyboard = [[InlineKeyboardButton("🎲 Spin Now", callback_data="play_freespins")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"🎁 You received {spins_to_add} free spins!\n\nClick button to spin!",
                reply_markup=reply_markup
            )
        except:
            pass

    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or spin count!")
    except Exception as e:
        import traceback
        logger.error(f"Error adding spins: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        await update.message.reply_text(f"❌ Error adding spins: {str(e)}")


async def spinsstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE, spin_bot: SpinBot, is_admin_func):
    """Admin command to view spin statistics"""
    user = update.effective_user

    if not is_admin_func(user.id):
        if update.callback_query:
            await update.callback_query.answer("❌ Admin access required!")
        else:
            await update.message.reply_text("❌ Admin access required!")
        return

    try:
        stats = spin_bot.api.get_spin_statistics()

        message = "📊 *SPIN BOT STATISTICS* 📊\n\n"
        message += f"👥 Total Users: *{stats['total_users']}*\n"
        message += f"🎲 Total Spins Used: *{stats['total_spins_used']}*\n"
        message += f"💎 Total Chips Awarded: *{stats['total_chips_awarded']}*\n"
        message += f"🎁 Pending Rewards: *{stats['pending_rewards']}*\n"
        message += f"✅ Approved Rewards: *{stats['approved_rewards']}*\n\n"
        message += f"🔝 *Top Spinners:*\n"

        for idx, user_stat in enumerate(stats['top_users'][:5], 1):
            message += f"{idx}\\. {user_stat['username']} \\- {user_stat['total_spins']} spins\n"

        if update.callback_query:
            await update.callback_query.message.reply_text(message, parse_mode='MarkdownV2')
        else:
            await update.message.reply_text(message, parse_mode='MarkdownV2')

    except Exception as e:
        logger.error(f"Error in spinsstats command: {e}")
        if update.callback_query:
            await update.callback_query.message.reply_text("❌ Error fetching statistics.")
        else:
            await update.message.reply_text("❌ Error fetching statistics.")
