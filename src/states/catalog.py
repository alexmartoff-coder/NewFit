from aiogram.fsm.state import State, StatesGroup

class CatalogFilter(StatesGroup):
    choosing_filter = State()
    entering_city = State()
    entering_district = State()
    entering_specialization = State()
    entering_price_min = State()
    entering_price_max = State()
    waiting_for_username_search = State()
    waiting_for_phone_search = State()
