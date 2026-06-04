from aiogram.fsm.state import State, StatesGroup

class TrainerOnboarding(StatesGroup):
    full_name = State()
    city = State()
    specialization = State()
    experience = State()
    formats = State()
    price_single = State()
    price_package = State()
    photo = State()
    video = State()
