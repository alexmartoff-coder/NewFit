from aiogram.fsm.state import State, StatesGroup

class TrainerOnboarding(StatesGroup):
    full_name = State()
    city = State()
    district = State()
    phone = State()
    sphere = State()
    specialization = State()
    experience = State()
    formats = State()
    price_online = State()
    price_single = State()
    price_services = State()  # New state for Beauty role to enter prices for each service
    price_package = State()
    photo = State()
    video = State()
