import aiosqlite
from datetime import datetime, date
from typing import Optional
from config import DATABASE_PATH


async def init_db():
    """Initialize database tables"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                lang TEXT DEFAULT 'ru',
                free_credits INTEGER DEFAULT 1,
                premium_credits INTEGER DEFAULT 0,
                ref_balance REAL DEFAULT 0,
                hold_balance REAL DEFAULT 0,
                referrer_id INTEGER,
                utm_source TEXT,
                is_banned INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Payments table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount_rub REAL,
                amount_usdt REAL,
                photo_count INTEGER,
                invoice_id TEXT,
                external_id TEXT,
                currency TEXT,
                provider TEXT DEFAULT 'platega',
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                paid_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Migration: add missing columns if table already exists
        try:
            await db.execute("ALTER TABLE payments ADD COLUMN external_id TEXT")
        except aiosqlite.OperationalError:
            pass
        try:
            await db.execute("ALTER TABLE payments ADD COLUMN currency TEXT")
        except aiosqlite.OperationalError:
            pass
        try:
            await db.execute("ALTER TABLE payments ADD COLUMN provider TEXT DEFAULT 'platega'")
        except aiosqlite.OperationalError:
            pass
        
        # UTM tags table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS utm_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Referral earnings table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referral_earnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referral_id INTEGER,
                payment_id INTEGER,
                amount REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (referrer_id) REFERENCES users(user_id),
                FOREIGN KEY (referral_id) REFERENCES users(user_id),
                FOREIGN KEY (payment_id) REFERENCES payments(id)
            )
        """)
        
        # Prices table (for dynamic pricing)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS prices (
                photo_count INTEGER PRIMARY KEY,
                price_rub REAL
            )
        """)
        
        # Withdrawals table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                method TEXT,
                wallet_address TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                processed_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Discounts table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS discounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                percent INTEGER,
                expires_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.commit()


# ===================== USER FUNCTIONS =====================

async def get_user(user_id: int) -> Optional[dict]:
    """Get user by ID"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ?", 
            (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def create_user(
    user_id: int, 
    username: str = None, 
    full_name: str = None,
    referrer_id: int = None,
    utm_source: str = None
) -> bool:
    """Create new user. Returns True if created, False if exists"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute(
                """INSERT INTO users 
                   (user_id, username, full_name, referrer_id, utm_source) 
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, username, full_name, referrer_id, utm_source)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def set_referrer(user_id: int, referrer_id: int) -> bool:
    """Set referrer for existing user who doesn't have one yet. Returns True if updated."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "UPDATE users SET referrer_id = ? WHERE user_id = ? AND referrer_id IS NULL",
            (referrer_id, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def update_user_lang(user_id: int, lang: str):
    """Update user language"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET lang = ? WHERE user_id = ?",
            (lang, user_id)
        )
        await db.commit()


async def add_credits(user_id: int, credits: int, credit_type: str = "premium"):
    """Add credits to user"""
    field = "premium_credits" if credit_type == "premium" else "free_credits"
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            f"UPDATE users SET {field} = {field} + ? WHERE user_id = ?",
            (credits, user_id)
        )
        await db.commit()


async def remove_credits(user_id: int, credits: int, credit_type: str = "premium"):
    """Remove credits from user"""
    field = "premium_credits" if credit_type == "premium" else "free_credits"
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            f"UPDATE users SET {field} = MAX(0, {field} - ?) WHERE user_id = ?",
            (credits, user_id)
        )
        await db.commit()


async def get_all_users() -> list:
    """Get all users"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE is_banned = 0")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_users_count() -> int:
    """Get total users count"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        return row[0]


async def get_today_users_count() -> int:
    """Get users registered today"""
    today = date.today().isoformat()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM users WHERE DATE(created_at) = ?",
            (today,)
        )
        row = await cursor.fetchone()
        return row[0]


async def ban_user(user_id: int):
    """Ban user"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET is_banned = 1 WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


async def unban_user(user_id: int):
    """Unban user"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET is_banned = 0 WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


async def get_referrals_count(user_id: int) -> int:
    """Get referrals count for user"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM users WHERE referrer_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        return row[0]


async def add_ref_balance(user_id: int, amount: float):
    """Add to referral balance"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET ref_balance = ref_balance + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()


async def add_to_hold(user_id: int, amount: float):
    """Add to hold balance"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET hold_balance = hold_balance + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()


async def search_user(query: str) -> Optional[dict]:
    """Search user by ID or username"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # Try by ID
        if query.isdigit():
            cursor = await db.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (int(query),)
            )
        else:
            # By username
            username = query.lstrip("@")
            cursor = await db.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,)
            )
        
        row = await cursor.fetchone()
        return dict(row) if row else None


# ===================== PAYMENT FUNCTIONS =====================

async def create_payment(
    user_id: int,
    amount_rub: float,
    amount_usdt: float,
    photo_count: int,
    invoice_id: str,
    *,
    external_id: str = None,
    currency: str = None,
    provider: str = "platega"
) -> int:
    """Create payment record"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO payments
               (user_id, amount_rub, amount_usdt, photo_count, invoice_id, external_id, currency, provider)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, amount_rub, amount_usdt, photo_count, invoice_id, external_id, currency, provider)
        )
        await db.commit()
        return cursor.lastrowid


async def get_pending_payments() -> list:
    """Get all pending payments"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM payments 
               WHERE status = 'pending' 
               AND datetime(created_at, '+30 minutes') > datetime('now')"""
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def complete_payment(payment_id: int):
    """Mark payment as completed"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """UPDATE payments 
               SET status = 'completed', paid_at = ? 
               WHERE id = ?""",
            (datetime.now().isoformat(), payment_id)
        )
        await db.commit()


async def get_total_payments() -> float:
    """Get total payments amount"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(SUM(amount_rub), 0) FROM payments WHERE status = 'completed'"
        )
        row = await cursor.fetchone()
        return row[0]


async def get_payment_by_invoice(invoice_id: str) -> Optional[dict]:
    """Get payment by invoice ID"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM payments WHERE invoice_id = ?",
            (invoice_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_payment_by_external_id(external_id: str) -> Optional[dict]:
    """Get payment by external/order ID"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM payments WHERE external_id = ?",
            (external_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_payment_invoice(payment_id: int, invoice_id: str):
    """Update invoice id for a payment"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE payments SET invoice_id = ? WHERE id = ?",
            (invoice_id, payment_id),
        )
        await db.commit()


# ===================== UTM FUNCTIONS =====================


async def create_utm(name: str) -> bool:
    """Create UTM tag"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO utm_tags (name) VALUES (?)",
                (name,)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def get_all_utm() -> list:
    """Get all UTM tags with stats (users, payments count, total amount)"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT 
                u.name, 
                u.created_at, 
                COUNT(DISTINCT usr.user_id) as users_count,
                COUNT(DISTINCT CASE WHEN p.status = 'completed' THEN p.id END) as payments_count,
                COALESCE(SUM(CASE WHEN p.status = 'completed' THEN p.amount_rub ELSE 0 END), 0) as total_amount
            FROM utm_tags u
            LEFT JOIN users usr ON usr.utm_source = u.name
            LEFT JOIN payments p ON p.user_id = usr.user_id
            GROUP BY u.id
            ORDER BY u.created_at DESC
        """)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# ===================== PRICE FUNCTIONS =====================

async def get_prices() -> dict:
    """Get prices from database or config"""
    from config import PRICES
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM prices")
        rows = await cursor.fetchall()
        
        if rows:
            return {row["photo_count"]: row["price_rub"] for row in rows}
        return PRICES


async def update_price(photo_count: int, price: float):
    """Update or create price"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO prices (photo_count, price_rub) 
               VALUES (?, ?)""",
            (photo_count, price)
        )
        await db.commit()


# ===================== REFERRAL EARNINGS =====================

async def create_referral_earning(
    referrer_id: int,
    referral_id: int,
    payment_id: int,
    amount: float
):
    """Record referral earning"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """INSERT INTO referral_earnings 
               (referrer_id, referral_id, payment_id, amount) 
               VALUES (?, ?, ?, ?)""",
            (referrer_id, referral_id, payment_id, amount)
        )
        await db.commit()


async def deduct_ref_balance(user_id: int, amount: float):
    """Deduct from referral balance"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET ref_balance = ref_balance - ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()


async def move_to_hold(user_id: int, amount: float):
    """Move amount from ref_balance to hold"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """UPDATE users SET 
               ref_balance = ref_balance - ?, 
               hold_balance = hold_balance + ? 
               WHERE user_id = ?""",
            (amount, amount, user_id)
        )
        await db.commit()


async def release_from_hold(user_id: int, amount: float):
    """Release amount from hold (after withdrawal approved)"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET hold_balance = hold_balance - ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()


async def return_from_hold(user_id: int, amount: float):
    """Return amount from hold to balance (after withdrawal rejected)"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """UPDATE users SET 
               ref_balance = ref_balance + ?, 
               hold_balance = hold_balance - ? 
               WHERE user_id = ?""",
            (amount, amount, user_id)
        )
        await db.commit()


# ===================== WITHDRAWAL FUNCTIONS =====================

async def create_withdrawal(
    user_id: int,
    amount: float,
    method: str,
    wallet_address: str = None
) -> int:
    """Create withdrawal request"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO withdrawals 
               (user_id, amount, method, wallet_address) 
               VALUES (?, ?, ?, ?)""",
            (user_id, amount, method, wallet_address)
        )
        await db.commit()
        return cursor.lastrowid


async def get_withdrawal(withdrawal_id: int) -> Optional[dict]:
    """Get withdrawal by ID"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM withdrawals WHERE id = ?",
            (withdrawal_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_user_withdrawals(user_id: int) -> list:
    """Get user's withdrawal history"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM withdrawals 
               WHERE user_id = ? 
               ORDER BY created_at DESC 
               LIMIT 20""",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def update_withdrawal_status(withdrawal_id: int, status: str):
    """Update withdrawal status"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """UPDATE withdrawals 
               SET status = ?, processed_at = ? 
               WHERE id = ?""",
            (status, datetime.now().isoformat(), withdrawal_id)
        )
        await db.commit()


# ===================== USER GROUPS FOR ADMIN =====================

async def get_users_unpaid_invoices() -> list:
    """Get users who created invoice but didn't pay"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT DISTINCT u.user_id 
            FROM users u
            INNER JOIN payments p ON u.user_id = p.user_id
            WHERE p.status = 'pending' 
            AND u.is_banned = 0
            AND u.user_id NOT IN (
                SELECT user_id FROM payments WHERE status = 'completed'
            )
        """)
        rows = await cursor.fetchall()
        return [row["user_id"] for row in rows]


async def get_users_zero_free_credits() -> list:
    """Get users with 0 free credits"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT user_id FROM users WHERE free_credits = 0 AND is_banned = 0"
        )
        rows = await cursor.fetchall()
        return [row["user_id"] for row in rows]


async def get_users_never_paid() -> list:
    """Get users who never made a payment"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT user_id FROM users 
            WHERE is_banned = 0
            AND user_id NOT IN (
                SELECT DISTINCT user_id FROM payments WHERE status = 'completed'
            )
        """)
        rows = await cursor.fetchall()
        return [row["user_id"] for row in rows]


async def get_all_user_ids() -> list:
    """Get all non-banned user IDs"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT user_id FROM users WHERE is_banned = 0"
        )
        rows = await cursor.fetchall()
        return [row["user_id"] for row in rows]


async def bulk_add_credits(user_ids: list, amount: int, credit_type: str = "premium"):
    """Add credits to multiple users"""
    field = "premium_credits" if credit_type == "premium" else "free_credits"
    async with aiosqlite.connect(DATABASE_PATH) as db:
        for user_id in user_ids:
            await db.execute(
                f"UPDATE users SET {field} = {field} + ? WHERE user_id = ?",
                (amount, user_id)
            )
        await db.commit()


# ===================== DISCOUNT FUNCTIONS =====================

async def create_discount(percent: int, duration_hours: int) -> int:
    """Create a discount"""
    from datetime import timedelta
    expires_at = (datetime.now() + timedelta(hours=duration_hours)).isoformat()
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO discounts (percent, expires_at) VALUES (?, ?)",
            (percent, expires_at)
        )
        await db.commit()
        return cursor.lastrowid


async def get_active_discount() -> Optional[dict]:
    """Get current active discount"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM discounts 
            WHERE datetime(expires_at) > datetime('now')
            ORDER BY created_at DESC
            LIMIT 1
        """)
        row = await cursor.fetchone()
        return dict(row) if row else None


async def delete_all_discounts():
    """Delete all discounts"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM discounts")
        await db.commit()

