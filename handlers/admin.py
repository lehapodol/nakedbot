from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

import database as db
from locales import get_text
from keyboards import (
    get_admin_keyboard, get_broadcast_confirm_keyboard,
    get_user_manage_keyboard, get_back_to_admin_keyboard,
    get_user_group_keyboard, get_credit_type_keyboard,
    get_broadcast_button_keyboard, get_buy_credits_keyboard
)
from config import ADMIN_IDS, BOT_USERNAME

router = Router()


class AdminStates(StatesGroup):
    """Admin FSM states"""
    waiting_broadcast = State()
    waiting_broadcast_button = State()
    waiting_user_search = State()
    waiting_credits_amount = State()
    waiting_utm_name = State()
    waiting_price_update = State()
    # New states
    waiting_mass_credits_amount = State()
    waiting_discount_percent = State()
    waiting_discount_duration = State()


def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in ADMIN_IDS


async def get_users_by_group(group: str) -> list:
    """Get user IDs by group name"""
    if group == "unpaid":
        return await db.get_users_unpaid_invoices()
    elif group == "zero_free":
        return await db.get_users_zero_free_credits()
    elif group == "never_paid":
        return await db.get_users_never_paid()
    else:  # all
        return await db.get_all_user_ids()


# ===================== ADMIN COMMAND =====================

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    """Handle /admin command"""
    if not is_admin(message.from_user.id):
        return
    
    await state.clear()
    
    user = await db.get_user(message.from_user.id)
    lang = user["lang"] if user else "ru"
    
    total_users = await db.get_users_count()
    today_users = await db.get_today_users_count()
    total_payments = await db.get_total_payments()
    
    text = get_text(
        "admin_panel", lang,
        total_users=total_users,
        today_users=today_users,
        total_payments=int(total_payments)
    )
    
    await message.answer(
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_admin_keyboard(lang)
    )


@router.callback_query(F.data == "admin:back")
async def callback_admin_back(callback: CallbackQuery, state: FSMContext):
    """Handle back to admin panel"""
    if not is_admin(callback.from_user.id):
        return
    
    await state.clear()
    
    user = await db.get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    
    total_users = await db.get_users_count()
    today_users = await db.get_today_users_count()
    total_payments = await db.get_total_payments()
    
    text = get_text(
        "admin_panel", lang,
        total_users=total_users,
        today_users=today_users,
        total_payments=int(total_payments)
    )
    
    await callback.message.edit_text(
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_admin_keyboard(lang)
    )
    await callback.answer()


# ===================== BROADCAST =====================

@router.callback_query(F.data == "admin:broadcast")
async def callback_broadcast(callback: CallbackQuery, state: FSMContext):
    """Handle broadcast button - select user group first"""
    if not is_admin(callback.from_user.id):
        return
    
    user = await db.get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    
    await callback.message.edit_text(
        text=get_text("select_user_group", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_user_group_keyboard("broadcast", lang)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("broadcast:group:"))
async def callback_broadcast_group(callback: CallbackQuery, state: FSMContext):
    """Handle broadcast group selection"""
    if not is_admin(callback.from_user.id):
        return
    
    group = callback.data.split(":")[2]
    user = await db.get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    
    await state.update_data(broadcast_group=group)
    await state.set_state(AdminStates.waiting_broadcast)
    
    await callback.message.edit_text(
        text=get_text("broadcast_prompt", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_back_to_admin_keyboard(lang)
    )
    await callback.answer()


@router.message(AdminStates.waiting_broadcast)
async def process_broadcast_message(message: Message, state: FSMContext):
    """Process broadcast message"""
    if not is_admin(message.from_user.id):
        return
    
    user = await db.get_user(message.from_user.id)
    lang = user["lang"] if user else "ru"
    
    # Store message for broadcasting
    await state.update_data(broadcast_message=message)
    await state.set_state(AdminStates.waiting_broadcast_button)
    
    await message.answer(
        text=get_text("broadcast_add_button", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_broadcast_button_keyboard(lang)
    )


@router.callback_query(F.data.startswith("broadcast:button:"))
async def callback_broadcast_button(callback: CallbackQuery, state: FSMContext):
    """Handle broadcast button choice"""
    if not is_admin(callback.from_user.id):
        return
    
    add_button = callback.data.split(":")[2] == "yes"
    user = await db.get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    
    await state.update_data(broadcast_add_button=add_button)
    
    data = await state.get_data()
    group = data.get("broadcast_group", "all")
    user_ids = await get_users_by_group(group)
    
    await callback.message.edit_text(
        text=get_text("broadcast_confirm", lang, count=len(user_ids)),
        parse_mode=ParseMode.HTML,
        reply_markup=get_broadcast_confirm_keyboard(lang)
    )
    await callback.answer()


@router.callback_query(F.data == "broadcast:confirm")
async def callback_broadcast_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Confirm and start broadcast"""
    if not is_admin(callback.from_user.id):
        return
    
    user = await db.get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    
    data = await state.get_data()
    broadcast_msg: Message = data.get("broadcast_message")
    group = data.get("broadcast_group", "all")
    add_button = data.get("broadcast_add_button", False)
    
    if not broadcast_msg:
        await callback.answer("Ошибка: сообщение не найдено", show_alert=True)
        return
    
    await callback.message.edit_text(
        text=get_text("broadcast_started", lang),
        parse_mode=ParseMode.HTML
    )
    
    # Get users by group
    user_ids = await get_users_by_group(group)
    sent = 0
    errors = 0
    
    # Get keyboard if needed
    keyboard = get_buy_credits_keyboard(lang) if add_button else None
    
    for user_id in user_ids:
        try:
            # Copy message with optional keyboard
            if broadcast_msg.photo:
                await bot.send_photo(
                    chat_id=user_id,
                    photo=broadcast_msg.photo[-1].file_id,
                    caption=broadcast_msg.caption,
                    caption_entities=broadcast_msg.caption_entities,
                    reply_markup=keyboard
                )
            elif broadcast_msg.video:
                await bot.send_video(
                    chat_id=user_id,
                    video=broadcast_msg.video.file_id,
                    caption=broadcast_msg.caption,
                    caption_entities=broadcast_msg.caption_entities,
                    reply_markup=keyboard
                )
            elif broadcast_msg.document:
                await bot.send_document(
                    chat_id=user_id,
                    document=broadcast_msg.document.file_id,
                    caption=broadcast_msg.caption,
                    caption_entities=broadcast_msg.caption_entities,
                    reply_markup=keyboard
                )
            else:
                await bot.send_message(
                    chat_id=user_id,
                    text=broadcast_msg.text,
                    entities=broadcast_msg.entities,
                    reply_markup=keyboard
                )
            sent += 1
        except Exception:
            errors += 1
    
    await callback.message.answer(
        text=get_text("broadcast_done", lang, sent=sent, errors=errors),
        parse_mode=ParseMode.HTML,
        reply_markup=get_admin_keyboard(lang)
    )
    
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "broadcast:cancel")
async def callback_broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    """Cancel broadcast"""
    if not is_admin(callback.from_user.id):
        return
    
    await state.clear()
    await callback.answer("Отменено")
    
    # Return to admin panel
    user = await db.get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    
    total_users = await db.get_users_count()
    today_users = await db.get_today_users_count()
    total_payments = await db.get_total_payments()
    
    text = get_text(
        "admin_panel", lang,
        total_users=total_users,
        today_users=today_users,
        total_payments=int(total_payments)
    )
    
    await callback.message.edit_text(
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_admin_keyboard(lang)
    )


# ===================== STATISTICS =====================

@router.callback_query(F.data == "admin:stats")
async def callback_stats(callback: CallbackQuery):
    """Handle statistics button"""
    if not is_admin(callback.from_user.id):
        return
    
    user = await db.get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    
    total_users = await db.get_users_count()
    today_users = await db.get_today_users_count()
    total_payments = await db.get_total_payments()
    
    text = get_text(
        "admin_panel", lang,
        total_users=total_users,
        today_users=today_users,
        total_payments=int(total_payments)
    )
    
    try:
        await callback.message.edit_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_keyboard(lang)
        )
    except TelegramBadRequest:
        pass  # Message is the same, ignore
    await callback.answer()


# ===================== UTM TAGS =====================

@router.callback_query(F.data == "admin:utm")
async def callback_utm(callback: CallbackQuery):
    """Handle UTM tags button"""
    if not is_admin(callback.from_user.id):
        return
    
    user = await db.get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    
    utm_tags = await db.get_all_utm()
    
    if utm_tags:
        utm_list = "\n".join([
            f"• <code>{u['name']}</code>\n"
            f"   👥 {u['users_count']} | 💳 {u['payments_count']} | 💰 {int(u['total_amount'])}₽"
            for u in utm_tags
        ])
    else:
        utm_list = "Нет UTM-меток" if lang == "ru" else "No UTM tags"
    
    await callback.message.edit_text(
        text=get_text("utm_list", lang, utm_list=utm_list),
        parse_mode=ParseMode.HTML,
        reply_markup=get_back_to_admin_keyboard(lang)
    )
    await callback.answer()


@router.message(Command("utm"))
async def cmd_utm(message: Message):
    """Handle /utm command to create UTM tag"""
    if not is_admin(message.from_user.id):
        return
    
    user = await db.get_user(message.from_user.id)
    lang = user["lang"] if user else "ru"
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /utm <название>")
        return
    
    utm_name = args[1].strip()
    
    if await db.create_utm(utm_name):
        await message.answer(
            text=get_text("utm_created", lang, name=utm_name, bot_username=BOT_USERNAME),
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer("UTM-метка с таким названием уже существует")


# ===================== PRICES =====================

@router.callback_query(F.data == "admin:prices")
async def callback_prices(callback: CallbackQuery):
    """Handle prices button"""
    if not is_admin(callback.from_user.id):
        return
    
    user = await db.get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    
    prices = await db.get_prices()
    prices_text = "\n".join([
        f"• {count} фото = {int(price)}₽"
        for count, price in sorted(prices.items())
    ])
    
    await callback.message.edit_text(
        text=get_text("prices_current", lang, prices=prices_text),
        parse_mode=ParseMode.HTML,
        reply_markup=get_back_to_admin_keyboard(lang)
    )
    await callback.answer()


@router.message(Command("price"))
async def cmd_price(message: Message):
    """Handle /price command to update price"""
    if not is_admin(message.from_user.id):
        return
    
    user = await db.get_user(message.from_user.id)
    lang = user["lang"] if user else "ru"
    
    args = message.text.split()
    if len(args) < 3:
        await message.answer("Использование: /price <количество> <цена>")
        return
    
    try:
        count = int(args[1])
        price = float(args[2])
    except ValueError:
        await message.answer("Неверный формат. Используйте числа.")
        return
    
    await db.update_price(count, price)
    
    await message.answer(
        text=get_text("price_updated", lang, count=count, price=int(price)),
        parse_mode=ParseMode.HTML
    )


# ===================== USER MANAGEMENT =====================

@router.callback_query(F.data == "admin:users")
async def callback_users(callback: CallbackQuery, state: FSMContext):
    """Handle users button"""
    if not is_admin(callback.from_user.id):
        return
    
    user = await db.get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    
    await state.set_state(AdminStates.waiting_user_search)
    
    await callback.message.edit_text(
        text=get_text("user_search", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_back_to_admin_keyboard(lang)
    )
    await callback.answer()


@router.message(AdminStates.waiting_user_search)
async def process_user_search(message: Message, state: FSMContext):
    """Process user search"""
    if not is_admin(message.from_user.id):
        return
    
    admin = await db.get_user(message.from_user.id)
    lang = admin["lang"] if admin else "ru"
    
    user = await db.search_user(message.text.strip())
    
    if not user:
        await message.answer("Пользователь не найден" if lang == "ru" else "User not found")
        return
    
    referrals_count = await db.get_referrals_count(user["user_id"])
    
    text = get_text(
        "user_info", lang,
        user_id=user["user_id"],
        username=f"@{user['username']}" if user["username"] else "—",
        full_name=user["full_name"] or "—",
        user_lang=user["lang"],
        created_at=user["created_at"][:10] if user["created_at"] else "—",
        referrer=user["referrer_id"] or "—",
        utm=user["utm_source"] or "—",
        free_credits=user["free_credits"],
        premium_credits=user["premium_credits"],
        ref_balance=int(user["ref_balance"]),
        hold=int(user["hold_balance"])
    )
    
    await state.update_data(managing_user_id=user["user_id"])
    
    await message.answer(
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_user_manage_keyboard(user["user_id"], user["is_banned"], lang)
    )
    
    await state.clear()


@router.callback_query(F.data.startswith("user:ban:"))
async def callback_ban_user(callback: CallbackQuery):
    """Handle ban user button"""
    if not is_admin(callback.from_user.id):
        return
    
    user_id = int(callback.data.split(":")[2])
    await db.ban_user(user_id)
    
    await callback.answer("Пользователь забанен ✅", show_alert=True)
    
    # Refresh user info
    admin = await db.get_user(callback.from_user.id)
    lang = admin["lang"] if admin else "ru"
    user = await db.get_user(user_id)
    
    text = get_text(
        "user_info", lang,
        user_id=user["user_id"],
        username=f"@{user['username']}" if user["username"] else "—",
        full_name=user["full_name"] or "—",
        user_lang=user["lang"],
        created_at=user["created_at"][:10] if user["created_at"] else "—",
        referrer=user["referrer_id"] or "—",
        utm=user["utm_source"] or "—",
        free_credits=user["free_credits"],
        premium_credits=user["premium_credits"],
        ref_balance=int(user["ref_balance"]),
        hold=int(user["hold_balance"])
    )
    
    await callback.message.edit_text(
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_user_manage_keyboard(user["user_id"], user["is_banned"], lang)
    )


@router.callback_query(F.data.startswith("user:unban:"))
async def callback_unban_user(callback: CallbackQuery):
    """Handle unban user button"""
    if not is_admin(callback.from_user.id):
        return
    
    user_id = int(callback.data.split(":")[2])
    await db.unban_user(user_id)
    
    await callback.answer("Пользователь разбанен ✅", show_alert=True)
    
    # Refresh user info
    admin = await db.get_user(callback.from_user.id)
    lang = admin["lang"] if admin else "ru"
    user = await db.get_user(user_id)
    
    text = get_text(
        "user_info", lang,
        user_id=user["user_id"],
        username=f"@{user['username']}" if user["username"] else "—",
        full_name=user["full_name"] or "—",
        user_lang=user["lang"],
        created_at=user["created_at"][:10] if user["created_at"] else "—",
        referrer=user["referrer_id"] or "—",
        utm=user["utm_source"] or "—",
        free_credits=user["free_credits"],
        premium_credits=user["premium_credits"],
        ref_balance=int(user["ref_balance"]),
        hold=int(user["hold_balance"])
    )
    
    await callback.message.edit_text(
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_user_manage_keyboard(user["user_id"], user["is_banned"], lang)
    )


@router.callback_query(F.data.startswith("user:add_credits:"))
async def callback_add_credits(callback: CallbackQuery, state: FSMContext):
    """Handle add credits button"""
    if not is_admin(callback.from_user.id):
        return
    
    user_id = int(callback.data.split(":")[2])
    await state.update_data(credits_action="add", credits_user_id=user_id)
    await state.set_state(AdminStates.waiting_credits_amount)
    
    await callback.message.answer(
        "Введите количество Premium обработок для добавления:"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("user:remove_credits:"))
async def callback_remove_credits(callback: CallbackQuery, state: FSMContext):
    """Handle remove credits button"""
    if not is_admin(callback.from_user.id):
        return
    
    user_id = int(callback.data.split(":")[2])
    await state.update_data(credits_action="remove", credits_user_id=user_id)
    await state.set_state(AdminStates.waiting_credits_amount)
    
    await callback.message.answer(
        "Введите количество Premium обработок для удаления:"
    )
    await callback.answer()


@router.message(AdminStates.waiting_credits_amount)
async def process_credits_amount(message: Message, state: FSMContext):
    """Process credits amount"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        amount = int(message.text)
    except ValueError:
        await message.answer("Введите число")
        return
    
    data = await state.get_data()
    action = data.get("credits_action")
    user_id = data.get("credits_user_id")
    
    if action == "add":
        await db.add_credits(user_id, amount, "premium")
        await message.answer(f"✅ Добавлено {amount} обработок пользователю {user_id}")
    else:
        await db.remove_credits(user_id, amount, "premium")
        await message.answer(f"✅ Удалено {amount} обработок у пользователя {user_id}")
    
    await state.clear()


# ===================== MASS CREDITS =====================

@router.callback_query(F.data == "admin:mass_credits")
async def callback_mass_credits(callback: CallbackQuery, state: FSMContext):
    """Handle mass credits button"""
    if not is_admin(callback.from_user.id):
        return
    
    user = await db.get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    
    await callback.message.edit_text(
        text=get_text("mass_credits_type", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_credit_type_keyboard(lang)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("credits:type:"))
async def callback_credits_type(callback: CallbackQuery, state: FSMContext):
    """Handle credit type selection"""
    if not is_admin(callback.from_user.id):
        return
    
    credit_type = callback.data.split(":")[2]
    user = await db.get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    
    await state.update_data(mass_credit_type=credit_type)
    
    await callback.message.edit_text(
        text=get_text("select_user_group", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_user_group_keyboard("mass_credits", lang)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mass_credits:group:"))
async def callback_mass_credits_group(callback: CallbackQuery, state: FSMContext):
    """Handle mass credits group selection"""
    if not is_admin(callback.from_user.id):
        return
    
    group = callback.data.split(":")[2]
    user = await db.get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    
    await state.update_data(mass_credits_group=group)
    await state.set_state(AdminStates.waiting_mass_credits_amount)
    
    await callback.message.edit_text(
        text=get_text("mass_credits_amount", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_back_to_admin_keyboard(lang)
    )
    await callback.answer()


@router.message(AdminStates.waiting_mass_credits_amount)
async def process_mass_credits_amount(message: Message, state: FSMContext):
    """Process mass credits amount"""
    if not is_admin(message.from_user.id):
        return
    
    user = await db.get_user(message.from_user.id)
    lang = user["lang"] if user else "ru"
    
    try:
        amount = int(message.text)
    except ValueError:
        await message.answer("Введите число")
        return
    
    data = await state.get_data()
    credit_type = data.get("mass_credit_type", "premium")
    group = data.get("mass_credits_group", "all")
    
    # Get users
    user_ids = await get_users_by_group(group)
    
    # Add credits
    await db.bulk_add_credits(user_ids, amount, credit_type)
    
    type_name = "Premium" if credit_type == "premium" else "бесплатных"
    
    await message.answer(
        text=get_text("mass_credits_done", lang, amount=amount, type=type_name, count=len(user_ids)),
        parse_mode=ParseMode.HTML,
        reply_markup=get_admin_keyboard(lang)
    )
    
    await state.clear()


# ===================== DISCOUNT =====================

@router.callback_query(F.data == "admin:discount")
async def callback_discount(callback: CallbackQuery, state: FSMContext):
    """Handle discount button"""
    if not is_admin(callback.from_user.id):
        return
    
    user = await db.get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    
    await callback.message.edit_text(
        text=get_text("select_user_group", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_user_group_keyboard("discount", lang)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("discount:group:"))
async def callback_discount_group(callback: CallbackQuery, state: FSMContext):
    """Handle discount group selection"""
    if not is_admin(callback.from_user.id):
        return
    
    group = callback.data.split(":")[2]
    user = await db.get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    
    await state.update_data(discount_group=group)
    await state.set_state(AdminStates.waiting_discount_percent)
    
    await callback.message.edit_text(
        text=get_text("discount_percent", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_back_to_admin_keyboard(lang)
    )
    await callback.answer()


@router.message(AdminStates.waiting_discount_percent)
async def process_discount_percent(message: Message, state: FSMContext):
    """Process discount percent"""
    if not is_admin(message.from_user.id):
        return
    
    user = await db.get_user(message.from_user.id)
    lang = user["lang"] if user else "ru"
    
    try:
        percent = int(message.text)
        if not 1 <= percent <= 99:
            raise ValueError
    except ValueError:
        await message.answer("Введите число от 1 до 99")
        return
    
    await state.update_data(discount_percent=percent)
    await state.set_state(AdminStates.waiting_discount_duration)
    
    await message.answer(
        text=get_text("discount_duration", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_back_to_admin_keyboard(lang)
    )


@router.message(AdminStates.waiting_discount_duration)
async def process_discount_duration(message: Message, state: FSMContext, bot: Bot):
    """Process discount duration and create discount"""
    if not is_admin(message.from_user.id):
        return
    
    user = await db.get_user(message.from_user.id)
    lang = user["lang"] if user else "ru"
    
    try:
        hours = int(message.text)
        if hours <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите положительное число")
        return
    
    data = await state.get_data()
    percent = data.get("discount_percent")
    group = data.get("discount_group", "all")
    
    # Create discount in DB
    await db.create_discount(percent, hours)
    
    # Get users to notify
    user_ids = await get_users_by_group(group)
    
    # Notify users about discount
    sent = 0
    for user_id in user_ids:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=get_text("discount_notify", lang, percent=percent, hours=hours),
                parse_mode=ParseMode.HTML,
                reply_markup=get_buy_credits_keyboard(lang)
            )
            sent += 1
        except Exception:
            pass
    
    await message.answer(
        text=get_text("discount_created", lang, percent=percent, hours=hours, count=sent),
        parse_mode=ParseMode.HTML,
        reply_markup=get_admin_keyboard(lang)
    )
    
    await state.clear()

