from aiogram.fsm.state import State, StatesGroup

class TrainerOnboarding(StatesGroup):
    full_name = State()
    city = State()
    specialization = State()
    experience = State()
    formats = State()
    price = State()
    media = State()
