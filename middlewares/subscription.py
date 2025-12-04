from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, CallbackQuery, TelegramObject
from aiogram.enums import ChatMemberStatus

from config import CHANNEL_ID, ADMIN_IDS
from locales import get_text
from keyboards import get_subscription_keyboard
import database as db


class SubscriptionMiddleware(BaseMiddleware):
    """Middleware to check if user is subscribed to the required channel"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Get user from event
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            # Allow check_subscription callback to pass through
            if event.data == "check_subscription":
                return await handler(event, data)
        
        if not user:
            return await handler(event, data)
        
        user_id = user.id
        
        # Skip check for admins
        if user_id in ADMIN_IDS:
            return await handler(event, data)
        
        # Get bot from data
        bot: Bot = data.get("bot")
        if not bot:
            return await handler(event, data)
        
        # Check subscription
        is_subscribed = await check_subscription(bot, user_id)
        
        if is_subscribed:
            return await handler(event, data)
        
        # User is not subscribed
        # IMPORTANT: If this is /start command with referral, save referrer BEFORE blocking
        if isinstance(event, Message) and event.text:
            await process_start_referral(event, user_id)
        
        # Get user language
        db_user = await db.get_user(user_id)
        lang = db_user["lang"] if db_user else "ru"
        
        if isinstance(event, Message):
            await event.answer(
                text=get_text("subscription_required", lang),
                reply_markup=get_subscription_keyboard(lang)
            )
        elif isinstance(event, CallbackQuery):
            await event.answer(
                text=get_text("subscription_failed", lang),
                show_alert=True
            )
        
        # Don't call the handler - block the request
        return None


async def process_start_referral(message: Message, user_id: int):
    """Process /start command to save referrer before subscription check blocks it"""
    text = message.text or ""
    
    # Only process /start commands
    if not text.startswith("/start"):
        return
    
    # Parse arguments
    parts = text.split()
    if len(parts) < 2:
        # No arguments, just create user without referrer
        await db.create_user(
            user_id=user_id,
            username=message.from_user.username,
            full_name=message.from_user.full_name
        )
        return
    
    args = parts[1]
    referrer_id = None
    utm_source = None
    
    if args.startswith("ref_"):
        try:
            referrer_id = int(args[4:])
            # Don't allow self-referral
            if referrer_id == user_id:
                referrer_id = None
        except ValueError:
            pass
    elif args.startswith("utm_"):
        utm_source = args[4:]
    
    # Try to create user with referrer
    is_new = await db.create_user(
        user_id=user_id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        referrer_id=referrer_id,
        utm_source=utm_source
    )
    
    # If user already exists but came via referral link, try to set referrer
    if not is_new and referrer_id:
        await db.set_referrer(user_id, referrer_id)


async def check_subscription(bot: Bot, user_id: int) -> bool:
    """Check if user is subscribed to the channel"""
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR
        ]
    except Exception:
        # If we can't check (bot not admin in channel, etc.), allow access
        return True

