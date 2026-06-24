from aiogram.fsm.state import State, StatesGroup

class ClientOnboarding(StatesGroup):
    full_name = State()
