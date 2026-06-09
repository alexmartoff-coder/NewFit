from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models.models import Admin

OWNER_ID = 228592391

class AdminMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user_id = None
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id

        data["is_owner"] = False
        data["is_admin"] = False
        data["can_test_trainer"] = False
        data["can_test_client"] = False

        # Check if impersonation is active from FSM
        state = data.get("state")
        if state:
            fsm_data = await state.get_data()
            imp_trainer_id = fsm_data.get("impersonate_trainer_id")
            imp_client_id = fsm_data.get("impersonate_client_id")
            if imp_trainer_id:
                data["effective_user_id"] = imp_trainer_id
            elif imp_client_id:
                data["effective_user_id"] = imp_client_id

        if user_id == OWNER_ID:
            data["is_owner"] = True
            data["is_admin"] = True
            data["can_test_trainer"] = True
            data["can_test_client"] = True
        else:
            # Get SessionLocal from data or use it directly if it was injected by another middleware
            # Usually Aiogram handlers get session from middleware.
            # For simplicity, we assume SessionLocal is available or we create one.
            from src.utils.db import SessionLocal
            async with SessionLocal() as session:
                admin = await session.execute(
                    select(Admin).where(Admin.user_id == user_id)
                )
                admin = admin.scalar_one_or_none()
                if admin:
                    data["is_admin"] = True
                    data["can_test_trainer"] = admin.can_test_trainer
                    data["can_test_client"] = admin.can_test_client

        return await handler(event, data)
