from aiogram import Bot
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import Dispatcher

bot_token = ''
bot = Bot(bot_token)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

db_path = 'db.db'

contact1 = '@olegsavtsov'

contact2 = '@prodaznic_bot'

contact3 = '@prodaznicmoney_bot'
