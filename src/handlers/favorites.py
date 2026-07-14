from aiogram import Router, types, F
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from src.models.models import User, ClientProfile, TrainerProfile, Booking
from src.utils.db import SessionLocal
from src.keyboards.inline import add_admin_button
from src.utils.text import escape_md

router = Router()

from src.models.models import UserRole

@router.message(F.text == "Мои специалисты")
async def show_favorites_categories(message: types.Message, is_admin: bool = False):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🏀 Спорт", callback_data="fav_cat_sport")],
        [types.InlineKeyboardButton(text="💅 Бьюти", callback_data=f"fav_sphere_{UserRole.BEAUTY.value}")]
    ])
    kb = add_admin_button(kb, is_admin=is_admin)
    await message.answer("Выберите категорию специалистов:", reply_markup=kb)

@router.callback_query(F.data == "fav_cat_sport")
async def show_fav_sport_types(callback: types.CallbackQuery, is_admin: bool = False):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="💪 Фитнес", callback_data=f"fav_sphere_{UserRole.TRAINER.value}")],
        [types.InlineKeyboardButton(text="🎾 Теннис", callback_data=f"fav_sphere_{UserRole.TENNIS.value}")],
        [types.InlineKeyboardButton(text="🏸 Падл", callback_data=f"fav_sphere_{UserRole.PADEL.value}")],
        [types.InlineKeyboardButton(text="🌍 Все специалисты", callback_data="fav_sphere_ALL")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="fav_back")]
    ])
    kb = add_admin_button(kb, is_admin=is_admin)
    await callback.message.edit_text("Выберите вид спорта:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "fav_back")
async def show_fav_back(callback: types.CallbackQuery, is_admin: bool = False):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🏀 Спорт", callback_data="fav_cat_sport")],
        [types.InlineKeyboardButton(text="💅 Бьюти", callback_data=f"fav_sphere_{UserRole.BEAUTY.value}")]
    ])
    kb = add_admin_button(kb, is_admin=is_admin)
    await callback.message.edit_text("Выберите категорию специалистов:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("fav_sphere_"))
async def show_favorites(callback: types.CallbackQuery, is_admin: bool = False, effective_user_id: int = None):
    user_id = effective_user_id or callback.from_user.id
    sphere = callback.data.split("_")[2]

    async with SessionLocal() as session:
        # 1. Get client profile
        stmt_cp = select(ClientProfile).where(ClientProfile.user_id == user_id)
        client_profile = (await session.execute(stmt_cp)).scalar_one_or_none()

        if not client_profile:
            await callback.message.answer("Профиль клиента не найден.")
            await callback.answer()
            return

        # 2. Find unique trainers from bookings
        # Avoid DISTINCT on objects with JSON columns
        pro_ids_subquery = (
            select(TrainerProfile.id)
            .join(Booking, Booking.trainer_profile_id == TrainerProfile.id)
            .join(User, TrainerProfile.user_id == User.id)
            .where(Booking.client_id == client_profile.id)
        )

        if sphere != "ALL":
            pro_ids_subquery = pro_ids_subquery.where(User.role == sphere)

        stmt = (
            select(TrainerProfile, User)
            .join(User, TrainerProfile.user_id == User.id)
            .where(TrainerProfile.id.in_(pro_ids_subquery))
            .options(
                selectinload(TrainerProfile.specializations),
                selectinload(TrainerProfile.photos)
            )
        )

        res = await session.execute(stmt)
        specialists = res.all()

        if not specialists:
            text = "В этой категории у вас пока нет специалистов." if sphere != "ALL" else "Вы еще не записывались к специалистам."
            await callback.message.answer(text)
            await callback.answer()
            return

        sphere_names = {
            UserRole.TRAINER.value: "фитнесу",
            UserRole.BEAUTY.value: "бьюти",
            UserRole.TENNIS.value: "теннису",
            UserRole.PADEL.value: "падлу",
            "ALL": ""
        }
        await callback.message.answer(f"Ваши специалисты по {sphere_names.get(sphere, '')} ({len(specialists)}):")

        for profile, user_data in specialists:
            text = (
                f"👤 **{escape_md(user_data.full_name)}**\n"
                f"📞 Телефон: {escape_md(profile.phone) or 'не указан'}\n"
                f"📍 {escape_md(profile.city)}"
                f"{f', {escape_md(profile.district)}' if profile.district else ''}\n"
            )

            if profile.service_prices:
                term = "Услуги" if user_data.role == UserRole.BEAUTY else "Направления"
                text += f"🛠 **{term} и цены:**\n"
                for svc, price in profile.service_prices.items():
                    text += f"• {escape_md(svc)}: {int(price)}₽\n"

                if profile.price_package > 0:
                    text += f"💳 Цена (пакет 12): {int(profile.price_package)}₽\n"
            else:
                specs_str = ", ".join([s.name for s in profile.specializations]) or "не указаны"
                text += f"🎯 Специализации: {escape_md(specs_str)}\n"
                text += (
                    f"💰 Разовое: {int(profile.price_single)}₽\n"
                    f"💳 12 занятий: {int(profile.price_package)}₽\n"
                )

            text += f"⭐ Рейтинг: {profile.rating:.1f}"

            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="Забронировать время", callback_data=f"book_{profile.user_id}")]
            ])

            if len(profile.photos) > 1:
                nav_row = [
                    types.InlineKeyboardButton(text="⬅️", callback_data=f"fav_photo_0_{profile.user_id}"),
                    types.InlineKeyboardButton(text=f"1/{len(profile.photos)}", callback_data="none"),
                    types.InlineKeyboardButton(text="➡️", callback_data=f"fav_photo_1_{profile.user_id}")
                ]
                kb.inline_keyboard.insert(0, nav_row)
            kb = add_admin_button(kb, is_admin=is_admin)

            if profile.photos:
                await callback.message.answer_photo(profile.photos[0].file_id, caption=text, reply_markup=kb, parse_mode="Markdown")
            elif profile.photo_url:
                await callback.message.answer_photo(profile.photo_url, caption=text, reply_markup=kb, parse_mode="Markdown")
            else:
                await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")

    await callback.answer()

@router.callback_query(F.data.startswith("fav_photo_"))
async def favorite_photo_carousel(callback: types.CallbackQuery, is_admin: bool = False):
    parts = callback.data.split("_")
    idx = int(parts[2])
    target_user_id = int(parts[3])

    async with SessionLocal() as session:
        stmt = select(TrainerProfile).where(TrainerProfile.user_id == target_user_id).options(
            selectinload(TrainerProfile.specializations),
            selectinload(TrainerProfile.photos),
            selectinload(TrainerProfile.user)
        )
        res = await session.execute(stmt)
        profile = res.scalar_one_or_none()

        if not profile or not profile.photos:
            await callback.answer("Фото не найдены.")
            return

        idx = idx % len(profile.photos)
        user = profile.user

        text = (
            f"👤 **{escape_md(user.full_name)}**\n"
            f"📞 Телефон: {escape_md(profile.phone) or 'не указан'}\n"
            f"📍 {escape_md(profile.city)}"
            f"{f', {escape_md(profile.district)}' if profile.district else ''}\n"
        )

        if profile.service_prices:
            term = "Услуги" if user.role == UserRole.BEAUTY else "Направления"
            text += f"🛠 **{term} и цены:**\n"
            for svc, price in profile.service_prices.items():
                text += f"• {escape_md(svc)}: {int(price)}₽\n"

            if profile.price_package > 0:
                text += f"💳 Цена (пакет 12): {int(profile.price_package)}₽\n"
        else:
            specs_str = ", ".join([s.name for s in profile.specializations]) or "не указаны"
            text += f"🎯 Специализации: {escape_md(specs_str)}\n"
            text += (
                f"💰 Разовое: {int(profile.price_single)}₽\n"
                f"💳 12 занятий: {int(profile.price_package)}₽\n"
            )

        text += f"⭐ Рейтинг: {profile.rating:.1f}"

        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Забронировать время", callback_data=f"book_{profile.user_id}")]
        ])

        prev_idx = (idx - 1) % len(profile.photos)
        next_idx = (idx + 1) % len(profile.photos)
        nav_row = [
            types.InlineKeyboardButton(text="⬅️", callback_data=f"fav_photo_{prev_idx}_{target_user_id}"),
            types.InlineKeyboardButton(text=f"{idx+1}/{len(profile.photos)}", callback_data="none"),
            types.InlineKeyboardButton(text="➡️", callback_data=f"fav_photo_{next_idx}_{target_user_id}")
        ]
        kb.inline_keyboard.insert(0, nav_row)
        kb = add_admin_button(kb, is_admin=is_admin)

        try:
            input_media = types.InputMediaPhoto(media=profile.photos[idx].file_id, caption=text, parse_mode="Markdown")
            await callback.message.edit_media(media=input_media, reply_markup=kb)
        except exceptions.TelegramBadRequest:
            pass
        await callback.answer()
