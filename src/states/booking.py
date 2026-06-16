from aiogram.fsm.state import State, StatesGroup

class BookingSession(StatesGroup):
    choosing_professional = State()
    choosing_date = State()
    choosing_time = State()
    confirming_booking = State()
