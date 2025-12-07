import asyncio
import logging
import time
import aiohttp
from aiohttp import web
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
    REFERRAL_COMMISSION,
    USDT_RUB_RATE,
    STREAMPAY_WEBHOOK_PORT,
)
from streampay import (
    streampay_create_payment,
    streampay_get_currencies,
    streampay_is_configured,
    validate_streampay_signature,
)

router = Router()

# Store pending payments for background checking
pending_payments = {}

logger = logging.getLogger(__name__)

async def _get_streampay_currency() -> str:
    """Fetch Streampay currencies and pick suitable option for UA/KZ/AZN/UZS."""
    preferred = ["UAH", "KZT", "AZN", "UZS", "USDT"]
    try:
        currencies = await streampay_get_currencies()
        available = {
            str(item.get("system_currency") or item.get("code") or "").upper()
            for item in currencies
        }
        for code in preferred:
            if code in available:
                return code
    except Exception as exc:
        logger.warning("Failed to fetch Streampay currencies: %s", exc)
    return "USDT"


async def finalize_successful_payment(bot: Bot, payment: dict):
    """Mark payment completed, credit user and handle referrals."""
    if payment.get("status") != "pending":
        return

    payment_id = payment.get("id")
    user_id = payment.get("user_id")
    photo_count = payment.get("photo_count", 0)
    amount_rub = payment.get("amount_rub", 0)

    await db.complete_payment(payment_id)
    await db.add_credits(user_id, photo_count, "premium")

    user = await db.get_user(user_id)
    lang = user["lang"] if user else "ru"

    if user and user.get("referrer_id"):
        commission = amount_rub * (REFERRAL_COMMISSION / 100)
        await db.add_ref_balance(user["referrer_id"], commission)
        await db.create_referral_earning(
            referrer_id=user["referrer_id"],
            referral_id=user_id,
            payment_id=payment_id,
            amount=commission
        )

    try:
        await bot.send_message(
            chat_id=user_id,
            text=get_text("payment_success", lang, count=photo_count),
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass



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

                            if payment:
                                await finalize_successful_payment(bot, payment)

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
    await process_payment(callback, state, PLATEGA_METHOD_INTERNATIONAL, provider="streampay")


async def process_payment(callback: CallbackQuery, state: FSMContext, payment_method: int, provider: str = "platega"):
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
    
    if provider == "streampay" and not streampay_is_configured():
        logger.warning(
            "Streampay is not configured; falling back to Platega international payment"
        )
        provider = "platega"
        payment_method = PLATEGA_METHOD_INTERNATIONAL

    if provider == "streampay":
        await process_streampay_payment(
            callback=callback,
            lang=lang,
            user_id=user_id,
            photo_count=photo_count,
            amount_rub=amount_rub
        )
        return

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


async def process_streampay_payment(
    callback: CallbackQuery,
    lang: str,
    user_id: int,
    photo_count: int,
    amount_rub: float,
):
    """Create Streampay invoice for international payments."""
    if not streampay_is_configured():
        logger.warning("Streampay is not configured; blocking international payment")
        await callback.answer(get_text("payment_unavailable", lang), show_alert=True)
        return

    system_currency = await _get_streampay_currency()
    amount_usdt = round(amount_rub / USDT_RUB_RATE, 2)
    external_id = f"streampay-{user_id}-{int(time.time())}"
    description = f"{photo_count} обработок для user_id:{user_id}"

    try:
        payment_id = await db.create_payment(
            user_id=user_id,
            amount_rub=amount_rub,
            amount_usdt=amount_usdt,
            photo_count=photo_count,
            invoice_id="",
            external_id=external_id,
            currency=system_currency,
            provider="streampay"
        )

        response = await streampay_create_payment(
            external_id=external_id,
            customer=str(user_id),
            description=description,
            system_currency=system_currency,
            amount=amount_usdt
        )

        invoice_id = response.get("invoice_id")
        pay_url = response.get("pay_url")

        if invoice_id:
            await db.update_payment_invoice(payment_id, str(invoice_id))

        if not pay_url:
            raise ValueError("Payment link not found in Streampay response")

        await callback.message.edit_text(
            text=get_text(
                "invoice_created", lang,
                amount=int(amount_rub),
                count=photo_count
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=get_invoice_keyboard(pay_url, lang)
        )
        await callback.answer()
    except Exception as exc:
        logger.error("Failed to create Streampay invoice: %s", exc)
        await callback.answer("❌ Ошибка", show_alert=True)


async def streampay_webhook_handler(request: web.Request, bot: Bot):
    """Process Streampay webhook with signature verification."""
    signature = request.headers.get("Signature")
    if not signature:
        return web.Response(status=400, text="missing signature")

    try:
        payload = {}
        if request.can_read_body:
            try:
                payload = await request.json()
            except Exception:
                payload = {}

        query_params = dict(request.query)
        values = {k: str(v) for k, v in (query_params or payload).items() if v is not None}

        if not values:
            return web.Response(status=400, text="empty payload")

        if not validate_streampay_signature(values, signature):
            return web.Response(status=403, text="invalid signature")

        status_value = str(
            values.get("status")
            or values.get("payment_status")
            or values.get("state")
            or ""
        ).lower()

        external_id = values.get("external_id") or values.get("externalId") or values.get("order_id") or values.get("order")
        invoice_id = values.get("invoice") or values.get("invoice_id") or values.get("id") or values.get("payment_id")

        payment = None
        if external_id:
            payment = await db.get_payment_by_external_id(external_id)

        if not payment and invoice_id:
            payment = await db.get_payment_by_invoice(invoice_id)

        if not payment:
            return web.Response(status=404, text="payment not found")

        success_statuses = {"paid", "success", "completed", "confirmed"}
        if status_value in success_statuses:
            await finalize_successful_payment(bot, payment)

        return web.Response(text="ok")
    except Exception as exc:
        logger.error("Error handling Streampay webhook: %s", exc)
        return web.Response(status=500, text="error")


async def start_streampay_webhook(bot: Bot):
    """Start aiohttp server for Streampay webhooks."""
    if not streampay_is_configured():
        logger.warning("Streampay credentials are missing; webhook server not started")
        return None

    app = web.Application()
    app.router.add_post("/streampay/webhook", lambda request: streampay_webhook_handler(request, bot))
    app.router.add_get("/streampay/webhook", lambda request: streampay_webhook_handler(request, bot))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", STREAMPAY_WEBHOOK_PORT)
    await site.start()
    logger.info("Streampay webhook server started on port %s", STREAMPAY_WEBHOOK_PORT)
    return runner


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
