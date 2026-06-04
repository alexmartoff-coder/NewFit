import asyncio
import logging
from aiogram import Bot, Dispatcher
from src.utils.config import settings
from src.handlers import start, trainer_onboarding, client_onboarding, catalog, profiles, booking, subscriptions, admin
from src.utils.db import init_db, engine
from src.middlewares.admin_middleware import AdminMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def main():
    # Initialize database
    await init_db(engine)

    # Initialize bot and dispatcher
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    # Register middleware
    dp.message.middleware(AdminMiddleware())
    dp.callback_query.middleware(AdminMiddleware())

    # Include routers
    dp.include_router(start.router)
    dp.include_router(trainer_onboarding.router)
    dp.include_router(client_onboarding.router)
    dp.include_router(catalog.router)
    dp.include_router(profiles.router)
    dp.include_router(booking.router)
    dp.include_router(subscriptions.router)
    dp.include_router(admin.router)

    logger.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
