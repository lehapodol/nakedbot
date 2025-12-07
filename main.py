import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
from handlers import setup_routers
from handlers.payment import check_payments, start_streampay_webhook
from middlewares import SubscriptionMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Main function to start the bot"""
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Initialize bot
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Initialize dispatcher
    dp = Dispatcher(storage=MemoryStorage())
    
    # Setup routers
    router = setup_routers()
    dp.include_router(router)
    
    # Setup subscription check middleware
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())
    
    # Start payment checker in background
    asyncio.create_task(check_payments(bot))
    logger.info("Platega payment checker started")

    # Start Streampay webhook server
    streampay_runner = await start_streampay_webhook(bot)
    if streampay_runner:
        logger.info("Streampay webhook server started")
    else:
        logger.warning("Streampay webhook server is disabled (no credentials)")

    # Start polling
    logger.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

