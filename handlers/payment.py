import asyncio
import aiohttp
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext

import database as db
from locales import get_text
from keyboards import get_invoice_keyboard, get_shop_keyboard, get_payment_keyboard
from config import (
    PLATEGA_URL, PLATEGA_MERCHANT_ID, PLATEGA_API_SECRET,
    PLATEGA_RETURN_URL, PLATEGA_CHECK_INTERVAL,
    PLATEGA_METHOD_SBP, PLATEGA_METHOD_INTERNATIONAL,
    REFERRAL_COMMISSION
)

router = Router()

# Store pending payments for background checking
pending_payments = {}


async def create_platega_invoice(
    amount: float,
    payment_method: int,
    description: str
) -> dict:
    """
    Create payment invoice via Platega.io API
    
    Args:
        amount: Amount in RUB
        payment_method: 2 for SBP, 12 for International
        description: Payment description
    
    Returns:
        dict with transactionId and redirect URL, or error
    """
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-MerchantId': PLATEGA_MERCHANT_ID,
        'X-Secret': PLATEGA_API_SECRET
    }
    
    payload = {
        "paymentMethod": payment_method,
        "paymentDetails": {
            "amount": amount,
            "currency": "RUB"
        },
        "description": description,
        "return": PLATEGA_RETURN_URL,
        "failedUrl": PLATEGA_RETURN_URL
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{PLATEGA_URL}/transaction/process",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "success": True,
                        "transaction_id": data.get("transactionId"),
                        "redirect": data.get("redirect"),
                        "status": data.get("status")
                    }
                else:
                    return {"success": False, "error": f"API error {response.status}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def check_platega_status(transaction_id: str) -> dict:
    """
    Check payment status via Platega.io API
    
    Args:
        transaction_id: Transaction UUID
    
    Returns:
        dict with status or error
    """
    headers = {
        'Accept': 'application/json',
        'X-MerchantId': PLATEGA_MERCHANT_ID,
        'X-Secret': PLATEGA_API_SECRET
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{PLATEGA_URL}/transaction/{transaction_id}",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "success": True,
                        "status": data.get("status"),
                        "data": data
                    }
                else:
                    return {"success": False, "error": f"API error {response.status}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def check_payments(bot: Bot):
    """Background task to check pending Platega payments"""
    while True:
        try:
            payments_to_remove = []
            
            for transaction_id, data in list(pending_payments.items()):
                try:
                    # Check payment status
                    result = await check_platega_status(transaction_id)
                    
                    if result.get("success"):
                        status = result.get("status")
                        
                        # CONFIRMED = payment successful
                        if status == "CONFIRMED":
                            user_id = data["user_id"]
                            photo_count = data["photo_count"]
                            amount_rub = data["amount_rub"]
                            
                            # Get payment from DB
                            payment = await db.get_payment_by_invoice(transaction_id)
                            
                            if payment and payment["status"] == "pending":
                                # Complete payment
                                await db.complete_payment(payment["id"])
                                
                                # Add credits to user
                                await db.add_credits(user_id, photo_count, "premium")
                                
                                # Get user for language
                                user = await db.get_user(user_id)
                                lang = user["lang"] if user else "ru"
                                
                                # Process referral commission
                                if user and user["referrer_id"]:
                                    commission = amount_rub * (REFERRAL_COMMISSION / 100)
                                    await db.add_ref_balance(user["referrer_id"], commission)
                                    await db.create_referral_earning(
                                        referrer_id=user["referrer_id"],
                                        referral_id=user_id,
                                        payment_id=payment["id"],
                                        amount=commission
                                    )
                                
                                # Notify user
                                try:
                                    await bot.send_message(
                                        chat_id=user_id,
                                        text=get_text("payment_success", lang, count=photo_count),
                                        parse_mode=ParseMode.HTML
                                    )
                                except Exception:
                                    pass
                            
                            payments_to_remove.append(transaction_id)
                        
                        # Payment failed or expired
                        elif status in ["FAILED", "EXPIRED", "CANCELED"]:
                            payments_to_remove.append(transaction_id)
                    
                    # Check if payment is older than 32 minutes
                    import time
                    if time.time() - data.get("created_at", 0) > 32 * 60:
                        payments_to_remove.append(transaction_id)
                
                except Exception:
                    pass
            
            # Remove processed payments
            for transaction_id in payments_to_remove:
                pending_payments.pop(transaction_id, None)
        
        except Exception:
            pass
        
        await asyncio.sleep(PLATEGA_CHECK_INTERVAL)


@router.callback_query(F.data.startswith("buy:"))
async def callback_buy_tariff(callback: CallbackQuery, state: FSMContext):
    """Handle tariff selection - store in state"""
    photo_count = int(callback.data.split(":")[1])
    
    await state.update_data(selected_tariff=photo_count)
    
    user = await db.get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    
    await callback.message.edit_text(
        text=get_text("select_payment", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_payment_keyboard(lang)
    )
    await callback.answer()


@router.callback_query(F.data == "pay:sbp")
async def callback_pay_sbp(callback: CallbackQuery, state: FSMContext):
    """Handle SBP QR payment selection"""
    await process_payment(callback, state, PLATEGA_METHOD_SBP)


@router.callback_query(F.data == "pay:international")
async def callback_pay_international(callback: CallbackQuery, state: FSMContext):
    """Handle International payment selection"""
    await process_payment(callback, state, PLATEGA_METHOD_INTERNATIONAL)


async def process_payment(callback: CallbackQuery, state: FSMContext, payment_method: int):
    """Process payment creation for any method"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    lang = user["lang"] if user else "ru"
    
    # Get state data for selected tariff
    data = await state.get_data()
    photo_count = data.get("selected_tariff")
    
    if not photo_count:
        photo_count = 6
    
    prices = await db.get_prices()
    amount_rub = prices.get(photo_count, 300)
    
    # Check for active discount
    discount = await db.get_active_discount()
    if discount:
        discount_percent = discount["percent"]
        amount_rub = amount_rub * (100 - discount_percent) / 100
    
    # Create description
    description = f"{photo_count} обработок для user_id:{user_id}"
    
    # Create Platega invoice
    result = await create_platega_invoice(
        amount=amount_rub,
        payment_method=payment_method,
        description=description
    )
    
    if result.get("success"):
        transaction_id = result.get("transaction_id")
        redirect_url = result.get("redirect")
        
        # Save payment to DB
        await db.create_payment(
            user_id=user_id,
            amount_rub=amount_rub,
            amount_usdt=0,  # Not using USDT
            photo_count=photo_count,
            invoice_id=transaction_id
        )
        
        # Add to pending payments for background checking
        import time
        pending_payments[transaction_id] = {
            "user_id": user_id,
            "photo_count": photo_count,
            "amount_rub": amount_rub,
            "created_at": time.time()
        }
        
        await callback.message.edit_text(
            text=get_text(
                "invoice_created", lang,
                amount=int(amount_rub),
                count=photo_count
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=get_invoice_keyboard(redirect_url, lang)
        )
        await callback.answer()
    else:
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data == "back_to_shop")
async def callback_back_shop(callback: CallbackQuery, state: FSMContext):
    """Handle back to shop"""
    await state.clear()
    
    user = await db.get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    
    prices = await db.get_prices()
    
    await callback.message.edit_text(
        text=get_text("shop_title", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_shop_keyboard(prices, lang)
    )
    await callback.answer()
