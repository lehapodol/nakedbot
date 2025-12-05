from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile, BufferedInputFile
from aiogram.filters import Command, CommandStart
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from locales import get_text
from keyboards import (
    get_main_keyboard, get_profile_keyboard, get_language_keyboard,
    get_shop_keyboard, get_referral_keyboard, get_help_keyboard,
    get_exchange_keyboard, get_withdraw_menu_keyboard,
    get_withdraw_methods_keyboard, get_withdraw_back_keyboard,
    get_admin_withdraw_keyboard, get_buy_credits_keyboard,
    get_subscription_keyboard, get_scenario_keyboard
)
from config import (
    WELCOME_IMAGE, PHOTO_INSTRUCTION_IMAGE, BOT_USERNAME, CREDIT_PRICE_RUB,
    USDT_FIXED_FEE, USDT_MIN_AMOUNT, ADMIN_CHAT_ID, CHANNEL_ID,
    UNDRESS_PROMPT, SCENARIO_PROMPTS
)
from api import process_image, upload_to_telegraph, blur_image_from_url

router = Router()


# ===================== SUBSCRIPTION CHECK =====================

@router.callback_query(F.data == "check_subscription")
async def callback_check_subscription(callback: CallbackQuery, bot: Bot):
    """Handle subscription check button"""
    user_id = callback.from_user.id

    # Get user language
    user = await db.get_user(user_id)
    lang = user["lang"] if user else "ru"

    # Check subscription
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        is_subscribed = member.status in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR
        ]
    except Exception:
        is_subscribed = False

    if is_subscribed:
        # Delete subscription message and show success
        try:
            await callback.message.delete()
        except Exception:
            pass

        await callback.message.answer(
            text=get_text("subscription_success", lang),
            reply_markup=get_main_keyboard(lang)
        )
        await callback.answer()
    else:
        await callback.answer(
            text=get_text("subscription_failed", lang),
            show_alert=True
        )


class UserStates(StatesGroup):
    """User FSM states"""
    waiting_exchange_amount = State()
    waiting_withdraw_wallet = State()
    waiting_withdraw_amount = State()


# ===================== BUTTON TEXT FILTERS =====================

# Russian buttons
BTN_SEND_PHOTO_RU = "🍓Раздеть!"
BTN_PROFILE_RU = "👤 Профиль"
BTN_BUY_RU = "🛍 Купить обработки"
BTN_REFERRAL_RU = "💸 Реферальная программа"

# English buttons
BTN_SEND_PHOTO_EN = "🔞 Send photo"
BTN_PROFILE_EN = "👤 Profile"
BTN_BUY_EN = "🛍 Buy credits"
BTN_REFERRAL_EN = "💸 Referral program"


# ===================== START COMMAND =====================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command with optional deep link"""
    await state.clear()

    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name

    # Parse deep link arguments
    parts = message.text.split()
    args = parts[1] if len(parts) > 1 else None
    referrer_id = None
    utm_source = None

    if args:
        if args.startswith("ref_"):
            try:
                referrer_id = int(args[4:])
                if referrer_id == user_id:
                    referrer_id = None
            except ValueError:
                referrer_id = None
        elif args.startswith("utm_"):
            utm_source = args[4:]

    # Create user if not exists
    is_new = await db.create_user(
        user_id=user_id,
        username=username,
        full_name=full_name,
        referrer_id=referrer_id,
        utm_source=utm_source
    )

    # If user already exists but came via referral link, try to set referrer
    if not is_new and referrer_id:
        await db.set_referrer(user_id, referrer_id)

    # Get user data
    user = await db.get_user(user_id)
    lang = user["lang"] if user else "ru"

    # Send welcome message with photo
    try:
        photo = FSInputFile(WELCOME_IMAGE)
        await message.answer_photo(
            photo=photo,
            caption=get_text("welcome", lang),
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_keyboard(lang)
        )
    except Exception:
        # If no image, send text only
        await message.answer(
            text=get_text("welcome", lang),
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_keyboard(lang)
        )


# ===================== HELP COMMAND =====================

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command"""
    user = await db.get_user(message.from_user.id)
    lang = user["lang"] if user else "ru"

    await message.answer(
        text=get_text("help_text", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_help_keyboard(lang),
        disable_web_page_preview=True
    )


# ===================== LANG COMMAND =====================

@router.message(Command("lang"))
async def cmd_lang(message: Message):
    """Handle /lang command"""
    user = await db.get_user(message.from_user.id)
    lang = user["lang"] if user else "ru"

    await message.answer(
        text=get_text("select_lang", lang),
        reply_markup=get_language_keyboard()
    )


# ===================== SEND PHOTO =====================

@router.message(F.text.in_([BTN_SEND_PHOTO_RU, BTN_SEND_PHOTO_EN]))
async def btn_send_photo(message: Message, state: FSMContext):
    """Handle send photo button"""
    user = await db.get_user(message.from_user.id)
    lang = user["lang"] if user else "ru"

    # Reset any previous flow so photos are processed normally
    await state.clear()

    # Пытаемся отправить картинку с caption = photo_instruction
    try:
        photo = FSInputFile(PHOTO_INSTRUCTION_IMAGE)
        await message.answer_photo(
            photo=photo,
            caption=get_text("photo_instruction", lang),
            parse_mode=ParseMode.HTML
        )
    except Exception:
        # Если файла нет или ошибка — просто отправляем текст
        await message.answer(
            text=get_text("photo_instruction", lang),
            parse_mode=ParseMode.HTML
        )

    # Затем отдельным сообщением — "Жду фотографию"
    await message.answer(
        text=get_text("waiting_photo", lang),
        parse_mode=ParseMode.HTML
    )


# ===================== PROFILE =====================

@router.message(F.text.in_([BTN_PROFILE_RU, BTN_PROFILE_EN]))
async def btn_profile(message: Message):
    """Handle profile button"""
    user_id = message.from_user.id
    user = await db.get_user(user_id)

    if not user:
        await db.create_user(
            user_id=user_id,
            username=message.from_user.username,
            full_name=message.from_user.full_name
        )
        user = await db.get_user(user_id)

    lang = user["lang"]
    lang_display = "🇷🇺 ru" if lang == "ru" else "🇬🇧 en"

    text = get_text("profile_title", lang) + "\n\n" + get_text(
        "profile_text", lang,
        user_id=user_id,
        free_credits=user["free_credits"],
        premium_credits=user["premium_credits"],
        locale=lang_display
    )

    await message.answer(
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_profile_keyboard(lang)
    )


@router.callback_query(F.data == "change_lang")
async def callback_change_lang(callback: CallbackQuery):
    """Handle change language button"""
    user = await db.get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"

    await callback.message.edit_text(
        text=get_text("select_lang", lang),
        reply_markup=get_language_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_lang:"))
async def callback_set_lang(callback: CallbackQuery):
    """Handle language selection"""
    new_lang = callback.data.split(":")[1]
    user_id = callback.from_user.id

    await db.update_user_lang(user_id, new_lang)

    # Send confirmation message
    await callback.message.answer(
        text=get_text("lang_changed", new_lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard(new_lang)
    )

    # Delete the language selection message
    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.answer()


# ===================== SHOP =====================

@router.message(F.text.in_([BTN_BUY_RU, BTN_BUY_EN]))
async def btn_buy(message: Message):
    """Handle buy button"""
    user = await db.get_user(message.from_user.id)
    lang = user["lang"] if user else "ru"

    prices = await db.get_prices()

    await message.answer(
        text=get_text("shop_title", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_shop_keyboard(prices, lang)
    )


# ===================== REFERRAL =====================

@router.message(F.text.in_([BTN_REFERRAL_RU, BTN_REFERRAL_EN]))
async def btn_referral(message: Message):
    """Handle referral button"""
    user_id = message.from_user.id
    user = await db.get_user(user_id)

    if not user:
        await db.create_user(
            user_id=user_id,
            username=message.from_user.username,
            full_name=message.from_user.full_name
        )
        user = await db.get_user(user_id)

    lang = user["lang"]
    referrals_count = await db.get_referrals_count(user_id)

    text = get_text(
        "referral_text", lang,
        balance=int(user["ref_balance"]),
        hold=int(user["hold_balance"]),
        referrals_count=referrals_count,
        bot_username=BOT_USERNAME,
        user_id=user_id
    )

    await message.answer(
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_referral_keyboard(lang),
        disable_web_page_preview=True
    )


@router.callback_query(F.data == "ref_back")
async def callback_ref_back(callback: CallbackQuery, state: FSMContext):
    """Handle back to referral menu"""
    await state.clear()

    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    lang = user["lang"] if user else "ru"

    referrals_count = await db.get_referrals_count(user_id)

    text = get_text(
        "referral_text", lang,
        balance=int(user["ref_balance"]),
        hold=int(user["hold_balance"]),
        referrals_count=referrals_count,
        bot_username=BOT_USERNAME,
        user_id=user_id
    )

    await callback.message.edit_text(
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_referral_keyboard(lang),
        disable_web_page_preview=True
    )
    await callback.answer()


# ===================== EXCHANGE =====================

@router.callback_query(F.data == "ref_exchange")
async def callback_ref_exchange(callback: CallbackQuery, state: FSMContext):
    """Handle exchange referral balance"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    lang = user["lang"] if user else "ru"

    # Calculate available credits (balance / price per credit)
    available_credits = int(user["ref_balance"] / CREDIT_PRICE_RUB)

    await state.set_state(UserStates.waiting_exchange_amount)

    await callback.message.edit_text(
        text=get_text("exchange_prompt", lang, available_credits=available_credits),
        parse_mode=ParseMode.HTML,
        reply_markup=get_exchange_keyboard(lang)
    )
    await callback.answer()


@router.message(UserStates.waiting_exchange_amount)
async def process_exchange_amount(message: Message, state: FSMContext):
    """Process exchange amount input"""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    lang = user["lang"] if user else "ru"

    # Check if input is a number
    try:
        amount = int(message.text)
    except ValueError:
        await message.answer(
            text=get_text("exchange_error_number", lang),
            parse_mode=ParseMode.HTML,
            reply_markup=get_exchange_keyboard(lang)
        )
        return

    # Check if user has enough balance
    max_credits = int(user["ref_balance"] / CREDIT_PRICE_RUB)

    if amount <= 0 or amount > max_credits:
        await message.answer(
            text=get_text("exchange_error_insufficient", lang, max_credits=max_credits),
            parse_mode=ParseMode.HTML,
            reply_markup=get_exchange_keyboard(lang)
        )
        return

    # Process exchange
    cost = amount * CREDIT_PRICE_RUB
    await db.deduct_ref_balance(user_id, cost)
    await db.add_credits(user_id, amount, "premium")

    await state.clear()

    await message.answer(
        text=get_text("exchange_success", lang, credits=amount),
        parse_mode=ParseMode.HTML,
        reply_markup=get_referral_keyboard(lang)
    )


# ===================== WITHDRAW =====================

@router.callback_query(F.data == "ref_withdraw")
async def callback_ref_withdraw(callback: CallbackQuery, state: FSMContext):
    """Handle withdraw menu"""
    await state.clear()

    user = await db.get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"

    await callback.message.edit_text(
        text=get_text("withdraw_menu", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_withdraw_menu_keyboard(lang)
    )
    await callback.answer()


@router.callback_query(F.data == "withdraw_create")
async def callback_withdraw_create(callback: CallbackQuery, state: FSMContext):
    """Handle create withdrawal request"""
    await state.clear()

    user = await db.get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"

    await callback.message.edit_text(
        text=get_text("withdraw_info", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_withdraw_methods_keyboard(lang)
    )
    await callback.answer()


@router.callback_query(F.data == "withdraw_usdt")
async def callback_withdraw_usdt(callback: CallbackQuery, state: FSMContext):
    """Handle USDT TRC20 withdrawal"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    lang = user["lang"] if user else "ru"

    # Check if balance is sufficient
    max_amount = user["ref_balance"] - USDT_FIXED_FEE

    if max_amount < USDT_MIN_AMOUNT:
        await callback.message.edit_text(
            text=get_text("withdraw_usdt_insufficient", lang, max_amount=int(max_amount)),
            parse_mode=ParseMode.HTML,
            reply_markup=get_withdraw_back_keyboard(lang)
        )
        await callback.answer()
        return

    # Ask for wallet address
    await state.set_state(UserStates.waiting_withdraw_wallet)

    await callback.message.edit_text(
        text=get_text("withdraw_usdt_prompt", lang, available=int(user["ref_balance"])),
        parse_mode=ParseMode.HTML,
        reply_markup=get_withdraw_back_keyboard(lang)
    )
    await callback.answer()


@router.message(UserStates.waiting_withdraw_wallet)
async def process_withdraw_wallet(message: Message, state: FSMContext):
    """Process wallet address input"""
    user = await db.get_user(message.from_user.id)
    lang = user["lang"] if user else "ru"

    wallet = message.text.strip()

    # Save wallet and ask for amount
    await state.update_data(wallet=wallet)
    await state.set_state(UserStates.waiting_withdraw_amount)

    await message.answer(
        text=get_text("withdraw_amount_prompt", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_withdraw_back_keyboard(lang)
    )


@router.message(UserStates.waiting_withdraw_amount)
async def process_withdraw_amount(message: Message, state: FSMContext, bot: Bot):
    """Process withdrawal amount input"""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    lang = user["lang"] if user else "ru"

    # Check if input is a number
    try:
        amount = float(message.text)
    except ValueError:
        await message.answer(
            text=get_text("exchange_error_number", lang),
            parse_mode=ParseMode.HTML,
            reply_markup=get_withdraw_back_keyboard(lang)
        )
        return

    # Check minimum amount
    if amount < USDT_MIN_AMOUNT:
        await message.answer(
            text=get_text("withdraw_error_amount", lang),
            parse_mode=ParseMode.HTML,
            reply_markup=get_withdraw_back_keyboard(lang)
        )
        return

    # Check if user has enough balance (amount + fee)
    total_needed = amount + USDT_FIXED_FEE
    if total_needed > user["ref_balance"]:
        await message.answer(
            text=get_text("withdraw_error_amount", lang),
            parse_mode=ParseMode.HTML,
            reply_markup=get_withdraw_back_keyboard(lang)
        )
        return

    # Get wallet from state
    data = await state.get_data()
    wallet = data.get("wallet", "")

    # Create withdrawal and move to hold
    await db.move_to_hold(user_id, total_needed)
    withdrawal_id = await db.create_withdrawal(
        user_id=user_id,
        amount=amount,
        method="USDT_TRC20",
        wallet_address=wallet
    )

    await state.clear()

    # Notify user
    await message.answer(
        text=get_text("withdraw_created", lang, amount=int(amount), wallet=wallet),
        parse_mode=ParseMode.HTML,
        reply_markup=get_referral_keyboard(lang)
    )

    # Notify admins
    user_data = await db.get_user(user_id)
    user_link = f"@{user_data['username']}" if user_data['username'] else user_data['full_name']

    try:
        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=get_text(
                "admin_withdraw_notification", "ru",
                user_link=user_link,
                user_id=user_id,
                amount=int(amount),
                method="USDT TRC20",
                wallet=wallet
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_withdraw_keyboard(withdrawal_id)
        )
    except Exception:
        pass


@router.callback_query(F.data == "withdraw_history")
async def callback_withdraw_history(callback: CallbackQuery):
    """Handle withdrawal history"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    lang = user["lang"] if user else "ru"

    withdrawals = await db.get_user_withdrawals(user_id)

    if not withdrawals:
        await callback.message.edit_text(
            text=get_text("withdraw_history_empty", lang),
            parse_mode=ParseMode.HTML,
            reply_markup=get_withdraw_menu_keyboard(lang)
        )
        await callback.answer()
        return

    # Format history
    history_lines = []
    for w in withdrawals:
        status_key = f"withdraw_status_{w['status']}"
        status = get_text(status_key, lang)
        date = w["created_at"][:10] if w["created_at"] else ""
        history_lines.append(f"• {date} — {int(w['amount'])}₽ — {status}")

    history_text = "\n".join(history_lines)

    await callback.message.edit_text(
        text=get_text("withdraw_history", lang, history=history_text),
        parse_mode=ParseMode.HTML,
        reply_markup=get_withdraw_menu_keyboard(lang)
    )
    await callback.answer()


# ===================== ADMIN WITHDRAW CALLBACKS =====================

@router.callback_query(F.data.startswith("admin_withdraw:"))
async def callback_admin_withdraw(callback: CallbackQuery, bot: Bot):
    """Handle admin withdrawal approval/rejection"""
    parts = callback.data.split(":")
    action = parts[1]
    withdrawal_id = int(parts[2])

    withdrawal = await db.get_withdrawal(withdrawal_id)
    if not withdrawal:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    user_id = withdrawal["user_id"]
    amount = withdrawal["amount"]

    if action == "approve":
        # Approve withdrawal
        await db.update_withdrawal_status(withdrawal_id, "approved")
        await db.release_from_hold(user_id, amount + USDT_FIXED_FEE)

        # Notify user
        user = await db.get_user(user_id)
        lang = user["lang"] if user else "ru"

        try:
            await bot.send_message(
                chat_id=user_id,
                text=get_text("withdraw_approved_user", lang, amount=int(amount)),
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass

        await callback.message.edit_text(
            text=callback.message.text + "\n\n✅ <b>Одобрено</b>",
            parse_mode=ParseMode.HTML
        )
        await callback.answer("Заявка одобрена", show_alert=True)

    elif action == "reject":
        # Reject withdrawal
        await db.update_withdrawal_status(withdrawal_id, "rejected")
        await db.return_from_hold(user_id, amount + USDT_FIXED_FEE)

        # Notify user
        user = await db.get_user(user_id)
        lang = user["lang"] if user else "ru"

        try:
            await bot.send_message(
                chat_id=user_id,
                text=get_text("withdraw_rejected_user", lang, amount=int(amount)),
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass

        await callback.message.edit_text(
            text=callback.message.text + "\n\n❌ <b>Отклонено</b>",
            parse_mode=ParseMode.HTML
        )
        await callback.answer("Заявка отклонена", show_alert=True)


# ===================== SHOP CALLBACK =====================

@router.callback_query(F.data == "open_shop")
async def callback_open_shop(callback: CallbackQuery):
    """Handle open shop callback"""
    user = await db.get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"

    prices = await db.get_prices()

    await callback.message.answer(
        text=get_text("shop_title", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_shop_keyboard(prices, lang)
    )
    await callback.answer()


# ===================== PHOTO PROCESSING =====================

@router.message(F.photo)
async def process_photo(message: Message, state: FSMContext, bot: Bot):
    """Handle photo messages - process through AI API"""
    # If user is in another flow, reset it so the photo is processed
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()

    user_id = message.from_user.id
    user = await db.get_user(user_id)

    if not user:
        await db.create_user(
            user_id=user_id,
            username=message.from_user.username,
            full_name=message.from_user.full_name
        )
        user = await db.get_user(user_id)

    lang = user["lang"]

    # Check credits - premium first, then free
    has_premium = user["premium_credits"] > 0
    has_free = user["free_credits"] > 0

    if not has_premium and not has_free:
        await message.answer(
            text=get_text("no_credits", lang),
            parse_mode=ParseMode.HTML,
            reply_markup=get_buy_credits_keyboard(lang)
        )
        return

    # Determine if result should be blurred (free credit used)
    use_blur = not has_premium and has_free

    # Send processing message
    processing_msg = await message.answer(
        text=get_text("processing_photo", lang),
        parse_mode=ParseMode.HTML
    )

    # Get photo file
    photo = message.photo[-1]  # Get largest photo

    # Get file URL from Telegram
    file_url = await upload_to_telegraph(bot, photo.file_id)

    if not file_url:
        await processing_msg.edit_text(
            text=get_text("processing_error", lang),
            parse_mode=ParseMode.HTML
        )
        return

    # Process through API
    success, result = await process_image(
        file_url=file_url,
        width=photo.width,
        height=photo.height,
        prompt=UNDRESS_PROMPT
    )

    if success:
        await state.update_data(
            last_photo={
                "file_url": file_url,
                "width": photo.width,
                "height": photo.height
            }
        )
        # Deduct credits (premium first, then free)
        if has_premium:
            await db.remove_credits(user_id, 1, "premium")
        else:
            await db.remove_credits(user_id, 1, "free")

        # Delete processing message
        try:
            await processing_msg.delete()
        except Exception:
            pass

        if use_blur:
            # Blur the result for free credits
            blurred_image = await blur_image_from_url(result)

            if blurred_image:
                # Send blurred result
                await message.answer_photo(
                    photo=BufferedInputFile(
                        blurred_image.read(),
                        filename="result.jpg"
                    ),
                    parse_mode=ParseMode.HTML
                )

                # Send blurred success message
                await message.answer(
                    text=get_text("processing_success_blurred", lang),
                    parse_mode=ParseMode.HTML,
                    reply_markup=get_buy_credits_keyboard(lang)
                )
            else:
                # Blur failed, send error
                await message.answer(
                    text=get_text("processing_error", lang),
                    parse_mode=ParseMode.HTML
                )
                return
        else:
            # Send normal result (premium credit)
            await message.answer_photo(
                photo=result,
                parse_mode=ParseMode.HTML
            )

            # Send success message
            await message.answer(
                text=get_text("processing_success", lang),
                parse_mode=ParseMode.HTML,
                reply_markup=get_buy_credits_keyboard(lang)
            )
        await message.answer(
            text=get_text("processing_scenarios", lang),
            parse_mode=ParseMode.HTML,
            reply_markup=get_scenario_keyboard(lang)
        )
    else:
        # Processing failed
        await processing_msg.edit_text(
            text=get_text("processing_error", lang),
            parse_mode=ParseMode.HTML
        )


# ===================== SCENARIO CALLBACKS =====================

@router.callback_query(F.data.startswith("scenario:"))
async def callback_scenario(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Handle additional scenario processing requests"""
    user_id = callback.from_user.id

    user = await db.get_user(user_id)
    lang = user["lang"] if user else "ru"

    data = await state.get_data()
    last_photo = data.get("last_photo") if data else None

    if not last_photo:
        await callback.answer(
            text=get_text("scenario_no_photo", lang),
            show_alert=True
        )
        return

    has_premium = user["premium_credits"] > 0 if user else False
    has_free = user["free_credits"] > 0 if user else False

    if not has_premium and not has_free:
        await callback.message.answer(
            text=get_text("no_credits", lang),
            parse_mode=ParseMode.HTML,
            reply_markup=get_buy_credits_keyboard(lang)
        )
        await callback.answer()
        return

    scenario_key = callback.data.split(":", maxsplit=1)[1]
    scenario_prompt = SCENARIO_PROMPTS.get(scenario_key)

    if not scenario_prompt:
        await callback.answer("Неизвестный сценарий", show_alert=True)
        return

    use_blur = not has_premium and has_free

    processing_msg = await callback.message.answer(
        text=get_text("processing_photo", lang),
        parse_mode=ParseMode.HTML
    )

    success, result = await process_image(
        file_url=last_photo.get("file_url"),
        width=last_photo.get("width", 512),
        height=last_photo.get("height", 512),
        prompt=f"{UNDRESS_PROMPT}. {scenario_prompt}"
    )

    if success:
        if has_premium:
            await db.remove_credits(user_id, 1, "premium")
        else:
            await db.remove_credits(user_id, 1, "free")

        try:
            await processing_msg.delete()
        except Exception:
            pass

        if use_blur:
            blurred_image = await blur_image_from_url(result)

            if blurred_image:
                await callback.message.answer_photo(
                    photo=BufferedInputFile(
                        blurred_image.read(),
                        filename="result.jpg"
                    ),
                    parse_mode=ParseMode.HTML
                )

                await callback.message.answer(
                    text=get_text("processing_success_blurred", lang),
                    parse_mode=ParseMode.HTML,
                    reply_markup=get_buy_credits_keyboard(lang)
                )
            else:
                await callback.message.answer(
                    text=get_text("processing_error", lang),
                    parse_mode=ParseMode.HTML
                )
                await callback.answer()
                return
        else:
            await callback.message.answer_photo(
                photo=result,
                parse_mode=ParseMode.HTML
            )

            await callback.message.answer(
                text=get_text("processing_success", lang),
                parse_mode=ParseMode.HTML,
                reply_markup=get_buy_credits_keyboard(lang)
            )

        await callback.message.answer(
            text=get_text("processing_scenarios", lang),
            parse_mode=ParseMode.HTML,
            reply_markup=get_scenario_keyboard(lang)
        )
    else:
        await processing_msg.edit_text(
            text=get_text("processing_error", lang),
            parse_mode=ParseMode.HTML
        )

    await callback.answer()
