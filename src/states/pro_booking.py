from aiogram.fsm.state import State, StatesGroup

class ProBookingSession(StatesGroup):
    choosing_client = State()
    choosing_date = State()
    choosing_slot = State()
    choosing_service = State()
    choosing_format = State()
    confirming = State()
