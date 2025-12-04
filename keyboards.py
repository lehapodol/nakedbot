from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from locales import get_text
from config import SUPPORT_URL, DISCOUNTS, TERMS_URL, PRIVACY_URL, CHANNEL_URL


def get_subscription_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Subscription check keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_subscribe", lang),
            url=CHANNEL_URL
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_check_subscription", lang),
            callback_data="check_subscription"
        )
    )
    
    return builder.as_markup()


def get_main_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    """Main menu reply keyboard"""
    builder = ReplyKeyboardBuilder()
    
    builder.row(
        KeyboardButton(text=get_text("btn_send_photo", lang)),
        KeyboardButton(text=get_text("btn_profile", lang))
    )
    builder.row(
        KeyboardButton(text=get_text("btn_buy", lang)),
        KeyboardButton(text=get_text("btn_referral", lang))
    )
    
    return builder.as_markup(resize_keyboard=True)


def get_profile_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Profile inline keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_change_lang", lang),
            callback_data="change_lang"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_support", lang),
            url=SUPPORT_URL
        )
    )
    
    return builder.as_markup()


def get_language_keyboard() -> InlineKeyboardMarkup:
    """Language selection keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang:ru"),
        InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang:en")
    )
    
    return builder.as_markup()


def get_shop_keyboard(prices: dict, lang: str = "ru") -> InlineKeyboardMarkup:
    """Shop tariffs keyboard"""
    builder = InlineKeyboardBuilder()
    
    for count, price in sorted(prices.items()):
        discount = DISCOUNTS.get(count, "")
        discount_text = f" {discount}" if discount else ""
        
        builder.row(
            InlineKeyboardButton(
                text=get_text("photo_count", lang, count=count),
                callback_data=f"buy:{count}"
            ),
            InlineKeyboardButton(
                text=f"{get_text('price_rub', lang, price=price)}{discount_text}",
                callback_data=f"buy:{count}"
            )
        )
    
    return builder.as_markup()


def get_payment_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Payment method selection keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_sbp", lang),
            callback_data="pay:sbp"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_international", lang),
            callback_data="pay:international"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_back", lang),
            callback_data="back_to_shop"
        )
    )
    
    return builder.as_markup()


def get_invoice_keyboard(pay_url: str, lang: str = "ru") -> InlineKeyboardMarkup:
    """Invoice payment keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_pay", lang),
            url=pay_url
        )
    )
    
    return builder.as_markup()


def get_referral_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Referral program keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_exchange", lang),
            callback_data="ref_exchange"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_partner_panel", lang),
            url=SUPPORT_URL
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_withdraw", lang),
            callback_data="ref_withdraw"
        )
    )
    
    return builder.as_markup()


def get_buy_credits_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Buy credits keyboard after processing"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_buy", lang),
            callback_data="open_shop"
        )
    )

    return builder.as_markup()


def get_scenario_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Keyboard with post-processing scenarios"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_scenario_finish", lang),
            callback_data="scenario:finish"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_scenario_threesome", lang),
            callback_data="scenario:threesome"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_scenario_lingerie", lang),
            callback_data="scenario:lingerie"
        )
    )

    return builder.as_markup()


def get_help_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Help FAQ keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_support", lang),
            url=SUPPORT_URL
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_terms", lang),
            url=TERMS_URL
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_privacy", lang),
            url=PRIVACY_URL
        )
    )
    
    return builder.as_markup()


def get_exchange_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Exchange back keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_back", lang),
            callback_data="ref_back"
        )
    )
    
    return builder.as_markup()


def get_withdraw_menu_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Withdraw menu keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_create_withdraw", lang),
            callback_data="withdraw_create"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_withdraw_history", lang),
            callback_data="withdraw_history"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_back", lang),
            callback_data="ref_back"
        )
    )
    
    return builder.as_markup()


def get_withdraw_methods_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Withdraw methods keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_usdt_trc20", lang),
            callback_data="withdraw_usdt"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_other_method", lang),
            url=SUPPORT_URL
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_back", lang),
            callback_data="ref_withdraw"
        )
    )
    
    return builder.as_markup()


def get_withdraw_back_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Withdraw back keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_back", lang),
            callback_data="withdraw_create"
        )
    )
    
    return builder.as_markup()


def get_admin_withdraw_keyboard(withdrawal_id: int) -> InlineKeyboardMarkup:
    """Admin withdrawal approval keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=f"admin_withdraw:approve:{withdrawal_id}"
        ),
        InlineKeyboardButton(
            text="❌ Отклонить",
            callback_data=f"admin_withdraw:reject:{withdrawal_id}"
        )
    )
    
    return builder.as_markup()


# ===================== ADMIN KEYBOARDS =====================

def get_admin_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Admin panel keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_broadcast_new", lang),
            callback_data="admin:broadcast"
        ),
        InlineKeyboardButton(
            text=get_text("btn_stats", lang),
            callback_data="admin:stats"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_mass_credits", lang),
            callback_data="admin:mass_credits"
        ),
        InlineKeyboardButton(
            text=get_text("btn_discount", lang),
            callback_data="admin:discount"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_utm", lang),
            callback_data="admin:utm"
        ),
        InlineKeyboardButton(
            text=get_text("btn_prices", lang),
            callback_data="admin:prices"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_users", lang),
            callback_data="admin:users"
        )
    )
    
    return builder.as_markup()


def get_broadcast_confirm_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Broadcast confirmation keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_confirm", lang),
            callback_data="broadcast:confirm"
        ),
        InlineKeyboardButton(
            text=get_text("btn_cancel", lang),
            callback_data="broadcast:cancel"
        )
    )
    
    return builder.as_markup()


def get_user_manage_keyboard(user_id: int, is_banned: bool, lang: str = "ru") -> InlineKeyboardMarkup:
    """User management keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_add_credits", lang),
            callback_data=f"user:add_credits:{user_id}"
        ),
        InlineKeyboardButton(
            text=get_text("btn_remove_credits", lang),
            callback_data=f"user:remove_credits:{user_id}"
        )
    )
    
    if is_banned:
        builder.row(
            InlineKeyboardButton(
                text=get_text("btn_unban", lang),
                callback_data=f"user:unban:{user_id}"
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text=get_text("btn_ban", lang),
                callback_data=f"user:ban:{user_id}"
            )
        )
    
    return builder.as_markup()


def get_back_to_admin_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Back to admin panel keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_back", lang),
            callback_data="admin:back"
        )
    )
    
    return builder.as_markup()


def get_user_group_keyboard(action: str, lang: str = "ru") -> InlineKeyboardMarkup:
    """User group selection keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_group_unpaid", lang),
            callback_data=f"{action}:group:unpaid"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_group_zero_free", lang),
            callback_data=f"{action}:group:zero_free"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_group_never_paid", lang),
            callback_data=f"{action}:group:never_paid"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_group_all", lang),
            callback_data=f"{action}:group:all"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_back", lang),
            callback_data="admin:back"
        )
    )
    
    return builder.as_markup()


def get_credit_type_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Credit type selection keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_credits_premium", lang),
            callback_data="credits:type:premium"
        ),
        InlineKeyboardButton(
            text=get_text("btn_credits_free", lang),
            callback_data="credits:type:free"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_back", lang),
            callback_data="admin:back"
        )
    )
    
    return builder.as_markup()


def get_broadcast_button_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Ask for purchase button in broadcast"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_yes", lang),
            callback_data="broadcast:button:yes"
        ),
        InlineKeyboardButton(
            text=get_text("btn_no", lang),
            callback_data="broadcast:button:no"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_back", lang),
            callback_data="admin:back"
        )
    )
    
    return builder.as_markup()

