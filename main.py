import sqlite3 as sq

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import BoundFilter
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from json import dumps, loads

import functions
import keyboards
from config import dp, bot, db_path, contact1, contact2, contact3
from functions import on_start, set_state, set_data, delete_message, get_delay_int, get_delay_str, get_data, update_data


class IsNotRegistered(BoundFilter):
    async def check(self, message: types.Message) -> bool:
        with sq.connect(db_path) as con:
            cur = con.cursor()
            user_info = cur.execute('''
                select id from users where t_id = ?
            ''', (message.from_user.id,)).fetchone()
        return user_info is None


class IsAdmin(BoundFilter):
    async def check(self, message: types.Message) -> bool:
        with sq.connect(db_path) as con:
            cur = con.cursor()
            admin_info = cur.execute('''
                select id from admins where t_id = ?
            ''', (message.from_user.id,)).fetchone()
        return admin_info is not None


class IsFirstAdminLevel(BoundFilter):
    async def check(self, message: types.Message) -> bool:
        with sq.connect(db_path) as con:
            cur = con.cursor()
            admin_access_level = cur.execute('''
                select access_level from admins where t_id = ?
            ''', (message.from_user.id,)).fetchone()
        return admin_access_level is not None and admin_access_level[0] == '1'


class IsSecondAdminLevel(BoundFilter):
    async def check(self, message: types.Message) -> bool:
        with sq.connect(db_path) as con:
            cur = con.cursor()
            admin_access_level = cur.execute('''
                select access_level from admins where t_id = ?
            ''', (message.from_user.id,)).fetchone()
        return admin_access_level is not None and admin_access_level[0] == '2'


class UserMenu(StatesGroup):
    Main = State()


class AdminMenu(StatesGroup):
    Main = State()
    Mailing = State()
    StartMessage = State()
    Balance = State()
    AddUsers = State()
    DeleteUsers = State()

    WaitingUsersList = State()
    WaitingUsersDelay = State()

    WaitingBalanceAdmin = State()
    WaitingBalanceValue = State()
    WaitingBalanceStatistic = State()
    WaitingBalanceMessage = State()
    WaitingBalanceDelay = State()


class AdminAutoMailing(StatesGroup):
    Main = State()
    Add = State()
    Delete = State()


class AdminAdmins(StatesGroup):
    Main = State()
    Add = State()
    Delete = State()


class AdminProducts(StatesGroup):
    Main = State()
    Add = State()
    Delete = State()


class AdminStats(StatesGroup):
    Main = State()
    Add = State()
    Delete = State()


@dp.message_handler(IsNotRegistered(), content_types=types.ContentType.ANY, state='*')
async def not_registered_handler(message: types.Message):
    await functions.registration_insertion(user=message.from_user)
    await set_state(message.from_user.id, 'UserMenu:Main')
    await functions.send_start_message(chat_id=message.chat.id)


@dp.message_handler(IsAdmin(), commands=['admin'], state='*')
async def admin_command_handler(message: types.Message):
    await set_state(message.from_user.id, 'AdminMenu:Main')
    await bot.send_message(message.chat.id, '<i>Вы вошли в админ панель</i>', parse_mode='HTML',
                           reply_markup=await keyboards.admin.main_reply())
    await bot.send_message(message.chat.id, 'Админ-панель',
                           reply_markup=await keyboards.admin.main_inline(message.from_user.id))


@dp.message_handler(commands=['start'], state='*')
async def commands_handler(message: types.Message):
    if message.text == '/start':
        await set_state(message.from_user.id, 'UserMenu:Main')
        await functions.send_start_message(chat_id=message.chat.id)


@dp.message_handler(IsAdmin(), content_types=types.ContentType.ANY, state=[AdminMenu, AdminAutoMailing,
                                                                           AdminAdmins, AdminProducts, AdminStats])
async def admin_menu_handler(message: types.Message, state: FSMContext):
    user_state = await state.get_state()
    user_data = await state.get_data()

    if message.content_type == 'text' and message.text == '💰 Баланс':
        with sq.connect(db_path) as con:
            cur = con.cursor()
            balance = cur.execute('''
                select balance from users where t_id = ?
            ''', (message.from_user.id,)).fetchone()[0]
        await bot.send_message(message.chat.id, f'На вашем баланса: {balance} руб.',
                               reply_markup=await keyboards.admin.main_reply())
    elif message.content_type == 'text' and message.text == '📊 Статистика':
        await functions.send_stats(chat_id=message.chat.id)
    elif message.content_type == 'text' and message.text == '🛒 Ваши продукты':
        await functions.send_products(chat_id=message.chat.id)
    elif message.content_type == 'text' and message.text == '✅ Запустить рекламу':
        text = f'''Для запуска рекламы перейдите в бот {contact2}'''
        await bot.send_message(message.chat.id, text, reply_markup=await keyboards.admin.main_reply())
    elif message.content_type == 'text' and message.text == '💳 Вывод средств':
        text = f'''Для вывода средств перейдите в бот {contact3}'''
        await bot.send_message(message.chat.id, text, reply_markup=await keyboards.admin.main_reply())
    elif message.content_type == 'text' and message.text == '📞 Поддержка':
        text = f'''📩 Напишите сообщение мне по адресу {contact1}

😉 Так я смогу быстро ответить Вам!'''
        await bot.send_message(message.chat.id, text, reply_markup=await keyboards.admin.main_reply())

    elif user_state == 'AdminMenu:Mailing':
        if 'MailingPhoto' and 'MailingText' in user_data.keys():
            if message.content_type == 'text' and message.text == 'Отмена ✖️':
                await set_state(message.from_user.id, 'AdminMenu:Main')
                await state.reset_data()
                await bot.send_message(message.chat.id, 'Разовая рассылка не запущена ❌',
                                       reply_markup=await keyboards.admin.main_reply())
                await bot.send_message(message.chat.id, 'Админ-панель',
                                       reply_markup=await keyboards.admin.main_inline(message.from_user.id))
            elif user_data['MailingPhoto'] is None:
                if message.content_type == 'photo':
                    await state.update_data(MailingPhoto=message.photo[0].file_id)
                    await bot.send_message(message.chat.id, 'Напишите текст разовой рассылки',
                                           reply_markup=await keyboards.general.cancel())
                else:
                    text = '''Пожалуйста, пришлите <u>изображение</u> разовой рассылки'''
                    await bot.send_message(message.chat.id, text, parse_mode='HTML',
                                           reply_markup=await keyboards.general.cancel())
            elif user_data['MailingText'] is None:
                if message.content_type == 'text':
                    await state.update_data(MailingText=[message.text, message.entities])

                    await bot.send_photo(message.chat.id, user_data['MailingPhoto'])
                    await bot.send_message(message.chat.id, message.text, entities=message.entities)

                    await bot.send_message(message.chat.id, 'Желаете сделать разовую рассылку?',
                                           reply_markup=await keyboards.general.accept())
                else:
                    text = '''Пожалуйста, напишите <u>текст</u> разовой рассылки'''
                    await bot.send_message(message.chat.id, text, parse_mode='HTML',
                                           reply_markup=await keyboards.general.cancel())
            else:
                if message.content_type == 'text' and message.text == 'Да ✔️':
                    await set_state(message.from_user.id, 'AdminMenu:Main')
                    await state.reset_data()

                    text = '''Рассылка запущена
Пожалуйста подождите...'''
                    keyboard = types.ReplyKeyboardRemove()
                    await bot.send_message(message.chat.id, text, reply_markup=keyboard)

                    await functions.mailing(photo=user_data['MailingPhoto'], text=user_data['MailingText'][0],
                                            entities=user_data['MailingText'][1])

                    text = '''Рассылка прошла успешно✅'''
                    keyboard = await keyboards.admin.main_reply()
                    await bot.send_message(message.chat.id, text, reply_markup=keyboard)
                    text = '''Админ-панель'''
                    keyboard = await keyboards.admin.main_inline(message.from_user.id)
                    await bot.send_message(message.chat.id, text, reply_markup=keyboard)
                elif message.content_type == 'text' and message.text == 'Нет ✖️':
                    await set_state(message.from_user.id, 'AdminMenu:Main')
                    await state.reset_data()
                    await bot.send_message(message.chat.id, 'Разовая рассылка не запущена ❌',
                                           reply_markup=await keyboards.admin.main_reply())
                    await bot.send_message(message.chat.id, 'Админ-панель',
                                           reply_markup=await keyboards.admin.main_inline(message.from_user.id))
                else:
                    await bot.send_message(message.chat.id, 'Используйте клавиатуру 👇',
                                           reply_markup=await keyboards.general.accept())
        else:
            await set_state(message.from_user.id, 'AdminMenu:Main')
            await bot.send_message(message.chat.id, 'Что-то пошло не так... ⚠️',
                                   reply_markup=await keyboards.admin.main_reply())
            await bot.send_message(message.chat.id, 'Админ-панель',
                                   reply_markup=await keyboards.admin.main_inline(message.from_user.id))

    elif user_state == 'AdminMenu:StartMessage':
        if 'StrMsgPhoto' and 'StrMsgText' in user_data.keys():
            if message.content_type == 'text' and message.text == 'Отмена ✖️':
                await set_state(message.from_user.id, 'AdminMenu:Main')
                await state.reset_data()
                await bot.send_message(message.chat.id, 'Стартовое сообщение не изменено ❌',
                                       reply_markup=await keyboards.admin.main_reply())
                await bot.send_message(message.chat.id, 'Админ-панель',
                                       reply_markup=await keyboards.admin.main_inline(message.from_user.id))
            elif user_data['StrMsgPhoto'] is None:
                if message.content_type == 'photo':
                    await state.update_data(StrMsgPhoto=message.photo[0].file_id)
                    await bot.send_message(message.chat.id, 'Напишите текст стартового сообщения',
                                           reply_markup=await keyboards.general.cancel())
                else:
                    await bot.send_message(message.chat.id, 'Пожалуйста, пришлите фотографию стартового сообщения',
                                           reply_markup=await keyboards.general.cancel())
            elif user_data['StrMsgText'] is None:
                if message.content_type == 'text':
                    await state.update_data(StrMsgText=message.text)

                    await bot.send_photo(message.chat.id, user_data['StrMsgPhoto'])
                    await bot.send_message(message.chat.id, message.text)

                    await bot.send_message(message.chat.id, 'Желаете изменить стартовое сообщение?',
                                           reply_markup=await keyboards.general.accept())
                else:
                    await bot.send_message(message.chat.id, 'Пожалуйста, напишите текст стартового сообщения',
                                           reply_markup=await keyboards.general.cancel())
            else:
                if message.content_type == 'text' and message.text == 'Да ✔️':
                    await set_state(message.from_user.id, 'AdminMenu:Main')
                    await state.reset_data()

                    with sq.connect(db_path) as con:
                        cur = con.cursor()
                        start_message = cur.execute('''
                            select id from start_message
                        ''').fetchone()
                        if start_message is None:
                            cur.execute('''
                                insert into start_message(photo, text) values(?, ?)
                            ''', (user_data['StrMsgPhoto'], user_data['StrMsgText']))
                        else:
                            cur.execute('''
                                update start_message set photo = ?, text = ?
                            ''', (user_data['StrMsgPhoto'], user_data['StrMsgText']))

                    text = '''Стартовое сообщение изменено ✅'''
                    keyboard = await keyboards.admin.main_reply()
                    await bot.send_message(message.chat.id, text, reply_markup=keyboard)
                    text = '''Админ-панель'''
                    keyboard = await keyboards.admin.main_inline(message.from_user.id)
                    await bot.send_message(message.chat.id, text, reply_markup=keyboard)
                elif message.content_type == 'text' and message.text == 'Нет ✖️':
                    await set_state(message.from_user.id, 'AdminMenu:Main')
                    await state.reset_data()
                    await bot.send_message(message.chat.id, 'Стартовое сообщение не изменено ❌',
                                           reply_markup=await keyboards.admin.main_reply())
                    await bot.send_message(message.chat.id, 'Админ-панель',
                                           reply_markup=await keyboards.admin.main_inline(message.from_user.id))
                else:
                    await bot.send_message(message.chat.id, 'Используйте клавиатуру 👇',
                                           reply_markup=await keyboards.general.accept())
        else:
            await set_state(message.from_user.id, 'AdminMenu:Main')
            await bot.send_message(message.chat.id, 'Что-то пошло не так... ⚠️',
                                   reply_markup=await keyboards.admin.main_reply())
            await bot.send_message(message.chat.id, 'Админ-панель',
                                   reply_markup=await keyboards.admin.main_inline(message.from_user.id))

    elif user_state == 'AdminAutoMailing:Add':
        if 'AutoMailingHours' and 'AutoMailingText' and 'AutoMailingPhoto' in user_data.keys():
            if message.content_type == 'text' and message.text == 'Отмена ✖️':
                await set_state(message.from_user.id, 'AdminAutoMailing:Main')
                await state.reset_data()
                await bot.send_message(message.chat.id, 'Авто-рассылка не добавлена ❌',
                                       reply_markup=await keyboards.admin.main_reply())
                await bot.send_message(message.chat.id, 'Админ-панель',
                                       reply_markup=await keyboards.admin.auto_mailing())
            elif user_data['AutoMailingHours'] is None:
                if message.content_type == 'text':
                    if not message.text.startswith('0') and message.text.isdigit():
                        await state.update_data(AutoMailingHours=int(message.text))
                        await bot.send_message(message.chat.id, 'Напишите текст авто-рассылки',
                                               reply_markup=await keyboards.general.cancel())
                    else:
                        await bot.send_message(message.chat.id, 'Пожалуйста, напишите кол-во часов <u>числом</u>',
                                               parse_mode='HTML', reply_markup=await keyboards.general.cancel())
                else:
                    text = '''Пожалуйста, напишите через какое кол-во часов после регистрации получать рассылку'''
                    await bot.send_message(message.chat.id, text, reply_markup=await keyboards.general.cancel())
            elif user_data['AutoMailingText'] is None:
                if message.content_type == 'text':
                    await state.update_data(AutoMailingText=message.text)
                    await bot.send_message(message.chat.id, 'Пришлите фотографию авто-рассылки',
                                           reply_markup=await keyboards.general.cancel())
                else:
                    await bot.send_message(message.chat.id, 'Пожалуйста, напишите текст авто-рассылки',
                                           reply_markup=await keyboards.general.cancel())
            elif user_data['AutoMailingPhoto'] is None:
                if message.content_type == 'photo':
                    await state.update_data(AutoMailingPhoto=message.photo[0].file_id)

                    await bot.send_photo(message.chat.id, message.photo[0].file_id)
                    await bot.send_message(message.chat.id, user_data['AutoMailingText'])

                    text = f'''Желаете добавить авто-рассылку после {user_data['AutoMailingHours']} часа(ов)?'''
                    keyboard = await keyboards.general.accept()
                    await bot.send_message(message.chat.id, text, reply_markup=keyboard)
                else:
                    await bot.send_message(message.chat.id, 'Пожалуйста, пришлите фотографию авто-рассылки',
                                           reply_markup=await keyboards.general.cancel())
            else:
                if message.content_type == 'text' and message.text == 'Да ✔️':
                    await set_state(message.from_user.id, 'AdminAutoMailing:Main')
                    await state.reset_data()

                    await functions.add_auto_mailing(hours=user_data['AutoMailingHours'],
                                                     text=user_data['AutoMailingText'],
                                                     photo=user_data['AutoMailingPhoto'])

                    await bot.send_message(message.chat.id, 'Авто-рассылка добавлена ✅',
                                           reply_markup=await keyboards.admin.main_reply())
                    await bot.send_message(message.chat.id, 'Админ-панель',
                                           reply_markup=await keyboards.admin.auto_mailing())
                elif message.content_type == 'text' and message.text == 'Нет ✖️':
                    await set_state(message.from_user.id, 'AdminAutoMailing:Main')
                    await state.reset_data()
                    await bot.send_message(message.chat.id, 'Авто-рассылка не добавлена ❌',
                                           reply_markup=await keyboards.admin.main_reply())
                    await bot.send_message(message.chat.id, 'Админ-панель',
                                           reply_markup=await keyboards.admin.auto_mailing())
                else:
                    await bot.send_message(message.chat.id, 'Используйте клавиатуру 👇',
                                           reply_markup=await keyboards.general.accept())
        else:
            await set_state(message.from_user.id, 'AdminMenu:Main')
            await bot.send_message(message.chat.id, 'Что-то пошло не так... ⚠️',
                                   reply_markup=await keyboards.admin.main_reply())
            await bot.send_message(message.chat.id, 'Админ-панель',
                                   reply_markup=await keyboards.admin.main_inline(message.from_user.id))

    elif user_state == 'AdminAdmins:Add':
        if 'AdminId' and 'AdminLevel' in user_data.keys():
            if message.content_type == 'text' and message.text == 'Отмена ✖️':
                await set_state(message.from_user.id, 'AdminAdmins:Main')
                await state.reset_data()
                await bot.send_message(message.chat.id, 'Новый админ не назначен ❌',
                                       reply_markup=await keyboards.admin.main_reply())
                await bot.send_message(message.chat.id, 'Админ-панель',
                                       reply_markup=await keyboards.admin.admins_main())
            elif user_data['AdminId'] is None:
                if message.content_type == 'text':
                    if message.forward_from is not None:
                        await state.update_data(AdminId=message.forward_from.id)
                        text = '''Теперь укажите уровень админки, который хотите назначить'''
                        await bot.send_message(message.chat.id, text,
                                               reply_markup=await keyboards.admin.admin_levels())
                    elif not message.text.startswith('0') and message.text.isdigit():
                        await state.update_data(AdminId=int(message.text))
                        text = '''Теперь укажите уровень админки, который хотите назначить'''
                        await bot.send_message(message.chat.id, text,
                                               reply_markup=await keyboards.admin.admin_levels())
                    else:
                        text = '''Пожалуйста, пришлите сообщение или ID пользователя, которого хотите назначить админом

Важно учитывать что пользователь мог включить запрет на пересылку сообщений.
В таком случае стоит попросить его воспользоваться @get_id_bot, чтобы человек передал вам свой ID'''
                        await bot.send_message(message.chat.id, text, reply_markup=await keyboards.general.cancel())
                else:
                    text = '''Пожалуйста, пришлите сообщение или ID пользователя, которого хотите назначить админом'''
                    await bot.send_message(message.chat.id, text, reply_markup=await keyboards.general.cancel())
            elif user_data['AdminLevel'] is None:
                if message.content_type == 'text' and message.text in ('1', '2'):
                    await state.update_data(AdminLevel=int(message.text))
                    text = f'''Добавление админа
                    
ID: <i>{user_data['AdminId']}</i>
Уровень админки: <i>{message.text}</i>

Желаете добавить нового админа?'''
                    await bot.send_message(message.chat.id, text, parse_mode='HTML',
                                           reply_markup=await keyboards.general.accept())
                else:
                    text = '''Пожалуйста, укажите уровень админки, который хотите назначить'''
                    await bot.send_message(message.chat.id, text,
                                           reply_markup=await keyboards.admin.admin_levels())
            else:
                if message.content_type == 'text' and message.text == 'Да ✔️':
                    await set_state(message.from_user.id, 'AdminAdmins:Main')
                    await state.reset_data()

                    with sq.connect(db_path) as con:
                        cur = con.cursor()
                        cur.execute('''
                            insert into admins(t_id, access_level) values(?, ?)
                        ''', (user_data['AdminId'], user_data['AdminLevel']))

                    await bot.send_message(message.chat.id, 'Новый админ назначен ✅',
                                           reply_markup=await keyboards.admin.main_reply())
                    await bot.send_message(message.chat.id, 'Админ-панель',
                                           reply_markup=await keyboards.admin.admins_main())
                elif message.content_type == 'text' and message.text == 'Нет ✖️':
                    await set_state(message.from_user.id, 'AdminAdmins:Main')
                    await state.reset_data()
                    await bot.send_message(message.chat.id, 'Новый админ не назначен ❌',
                                           reply_markup=await keyboards.admin.main_reply())
                    await bot.send_message(message.chat.id, 'Админ-панель',
                                           reply_markup=await keyboards.admin.admins_main())
                else:
                    await bot.send_message(message.chat.id, 'Используйте клавиатуру 👇',
                                           reply_markup=await keyboards.general.accept())
        else:
            await set_state(message.from_user.id, 'AdminAdmins:Main')
            await bot.send_message(message.chat.id, 'Что-то пошло не так... ⚠️',
                                   reply_markup=await keyboards.admin.main_reply())
            await bot.send_message(message.chat.id, 'Админ-панель',
                                   reply_markup=await keyboards.admin.admins_main())

    elif user_state == 'AdminMenu:Balance':
        if 'UserTid' and 'NewBalance' in user_data.keys():
            if message.content_type == 'text' and message.text == 'Отмена ✖️':
                await set_state(message.from_user.id, 'AdminMenu:Main')
                await state.reset_data()
                await bot.send_message(message.chat.id, 'Баланс пользователя не изменён ❌',
                                       reply_markup=await keyboards.admin.main_reply())
                await bot.send_message(message.chat.id, 'Админ-панель',
                                       reply_markup=await keyboards.admin.main_inline(message.from_user.id))
            elif user_data['UserTid'] is None:
                pass
            elif user_data['NewBalance'] is None:
                if message.content_type == 'text':
                    if message.text == '0' or not message.text.startswith('0') and message.text.isdigit():
                        await state.update_data(NewBalance=int(message.text))
                        text = f'''Изменение баланса

Пользователь: {user_data['UserTid']}
Новый баланс: {message.text} руб

Вы действительно хотите изменить баланс?'''
                        await bot.send_message(message.chat.id, text,
                                               reply_markup=await keyboards.general.accept())
                    else:
                        text = '''Пожалуйста, напишите новый баланс пользователя <b>числом</b>'''
                        await bot.send_message(message.chat.id, text, parse_mode='HTML',
                                               reply_markup=await keyboards.general.cancel())
                else:
                    text = '''Пожалуйста, напишите новый баланс пользователя'''
                    await bot.send_message(message.chat.id, text, reply_markup=await keyboards.general.cancel())
            else:
                if message.content_type == 'text' and message.text == 'Да ✔️':
                    await set_state(message.from_user.id, 'AdminMenu:Main')
                    await state.reset_data()

                    with sq.connect(db_path) as con:
                        cur = con.cursor()
                        cur.execute('''
                            update users set balance = ? where t_id = ?
                        ''', (user_data['NewBalance'], user_data['UserTid']))

                    await bot.send_message(message.chat.id, 'Баланс пользователя изменён ✅',
                                           reply_markup=await keyboards.admin.main_reply())
                    await bot.send_message(message.chat.id, 'Админ-панель',
                                           reply_markup=await keyboards.admin.main_inline(message.from_user.id))
                elif message.content_type == 'text' and message.text == 'Нет ✖️':
                    await set_state(message.from_user.id, 'AdminMenu:Main')
                    await state.reset_data()
                    await bot.send_message(message.chat.id, 'Баланс пользователя не изменён ❌',
                                           reply_markup=await keyboards.admin.main_reply())
                    await bot.send_message(message.chat.id, 'Админ-панель',
                                           reply_markup=await keyboards.admin.main_inline(message.from_user.id))
                else:
                    await bot.send_message(message.chat.id, 'Используйте клавиатуру 👇',
                                           reply_markup=await keyboards.general.accept())
        else:
            await set_state(message.from_user.id, 'AdminMenu:Main')
            await bot.send_message(message.chat.id, 'Что-то пошло не так... ⚠️',
                                   reply_markup=await keyboards.admin.main_reply())
            await bot.send_message(message.chat.id, 'Админ-панель',
                                   reply_markup=await keyboards.admin.main_inline(message.from_user.id))

    elif user_state == 'AdminProducts:Add':
        if message.content_type == 'text':
            if message.text == 'Отмена ✖️':
                await set_state(message.from_user.id, 'AdminProducts:Main')
                await bot.send_message(message.chat.id, 'Продукт не добавлена ❌',
                                       reply_markup=await keyboards.admin.main_reply())
                await bot.send_message(message.chat.id, 'Админ-панель',
                                       reply_markup=await keyboards.admin.products_main())
            else:
                await set_state(message.from_user.id, 'AdminProducts:Main')

                with sq.connect(db_path) as con:
                    cur = con.cursor()
                    cur.execute('''
                        insert into products(text) values(?)
                    ''', (message.text,))

                await bot.send_message(message.chat.id, 'Продукт добавлен ✅',
                                       reply_markup=await keyboards.admin.main_reply())
                await bot.send_message(message.chat.id, 'Админ-панель',
                                       reply_markup=await keyboards.admin.products_main())
        else:
            text = '''Пожалуйста, напишите <b>текст</b> продукта'''
            await bot.send_message(message.chat.id, text, parse_mode='HTML',
                                   reply_markup=await keyboards.general.cancel())

    elif user_state == 'AdminStats:Add':
        if message.content_type == 'text':
            if message.text == 'Отмена ✖️':
                await set_state(message.from_user.id, 'AdminStats:Main')
                await bot.send_message(message.chat.id, 'Статистика не добавлена ❌',
                                       reply_markup=await keyboards.admin.main_reply())
                await bot.send_message(message.chat.id, 'Админ-панель',
                                       reply_markup=await keyboards.admin.stats_main())
            else:
                await set_state(message.from_user.id, 'AdminStats:Main')

                with sq.connect(db_path) as con:
                    cur = con.cursor()
                    cur.execute('''
                        insert into stats(text) values(?)
                    ''', (message.text,))

                await bot.send_message(message.chat.id, 'Статистика добавлена ✅',
                                       reply_markup=await keyboards.admin.main_reply())
                await bot.send_message(message.chat.id, 'Админ-панель',
                                       reply_markup=await keyboards.admin.stats_main())
        else:
            text = '''Пожалуйста, напишите <b>текст</b> статистики'''
            await bot.send_message(message.chat.id, text, parse_mode='HTML',
                                   reply_markup=await keyboards.general.cancel())

    elif user_state == 'AdminMenu:AddUsers':
        if message.content_type == 'text':
            if message.text == 'Отмена ✖️':
                await set_state(message.from_user.id, 'AdminMenu:Main')
                await bot.send_message(message.chat.id, 'Пользователи не добавлены ❌',
                                       reply_markup=await keyboards.admin.main_reply())
                await bot.send_message(message.chat.id, 'Админ-панель',
                                       reply_markup=await keyboards.admin.main_inline(message.from_user.id))
            else:
                await set_state(message.from_user.id, 'AdminMenu:Main')
                with sq.connect(db_path) as con:
                    cur = con.cursor()
                    for user in message.text.split('\n'):
                        if len(user.split(',', maxsplit=1)) == 2:
                            username, user_tid = user.strip().split(',', maxsplit=1)
                            if username.startswith('@') and (not user_tid.startswith('0') and user_tid.isdigit()):
                                cur.execute('''
                                    insert into users(t_id, username) values(?, ?)
                                ''', (user_tid, username))
                await bot.send_message(message.chat.id, 'Пользователи добавлены ✅',
                                       reply_markup=await keyboards.admin.main_reply())
                await bot.send_message(message.chat.id, 'Админ-панель',
                                       reply_markup=await keyboards.admin.main_inline(message.from_user.id))
        else:
            text = '''Пришлите список пользователей в следующем формате:

@username1,111000111
@username2,222000222
@username3,333000333
...'''
            await bot.send_message(message.chat.id, text,
                                   reply_markup=await keyboards.general.cancel())

    elif user_state == 'AdminMenu:DeleteUsers':
        if message.content_type == 'text':
            if message.text == 'Отмена ✖️':
                await set_state(message.from_user.id, 'AdminMenu:Main')
                await bot.send_message(message.chat.id, 'Пользователи не удалены ❌',
                                       reply_markup=await keyboards.admin.main_reply())
                await bot.send_message(message.chat.id, 'Админ-панель',
                                       reply_markup=await keyboards.admin.main_inline(message.from_user.id))
            else:
                await set_state(message.from_user.id, 'AdminMenu:Main')
                with sq.connect(db_path) as con:
                    cur = con.cursor()
                    for user_tid in message.text.split('\n'):
                        if not user_tid.startswith('0') and user_tid.strip().isdigit():
                            cur.execute('''
                                delete from users where t_id = ?
                            ''', (user_tid.strip(),))
                await bot.send_message(message.chat.id, 'Пользователи удалены ✅',
                                       reply_markup=await keyboards.admin.main_reply())
                await bot.send_message(message.chat.id, 'Админ-панель',
                                       reply_markup=await keyboards.admin.main_inline(message.from_user.id))
        else:
            text = '''Пришлите список пользователей в следующем формате:

111000111
222000222
333000333
...'''
            await bot.send_message(message.chat.id, text,
                                   reply_markup=await keyboards.general.cancel())
    elif user_state in ('AdminMenu:WaitingUsersList', 'AdminMenu:WaitingUsersDelay'):
        kb_cancel = await keyboards.general.cancel()
        if message.text == 'Отмена ✖️':
            await set_state(message.from_user.id, 'AdminMenu:Main')
            await set_data(message.from_user.id, {})
            await bot.send_message(message.chat.id, 'Добавление автосценария отменено',
                                   reply_markup=await keyboards.admin.main_reply())
            await bot.send_message(message.chat.id, 'Админ-панель',
                                   reply_markup=await keyboards.admin.main_inline(message.from_user.id))
        elif user_state == 'AdminMenu:WaitingUsersList':
            subscribers = []
            try:
                for line in message.text.split('\n'):
                    username, user_id = line.replace('(', '').replace(')', '').split(' ')
                    subscribers.append({'username': username, 'user_id': int(user_id)})
            except:
                pass

            if subscribers:
                await set_state(message.from_user.id, 'AdminMenu:WaitingUsersDelay')
                await set_data(message.from_user.id, data={'subscribers': subscribers})

                text = 'Введите временную задержку между добавлением подписчиков в формате <code>3д 12ч 25м 13с</code>:'
            else:
                text = ('Не удалось извлечь список пользователей, сообщение не соответвествует шаблону. '
                        'Попробуйте еще раз.')
            await message.answer(text=text, reply_markup=kb_cancel, parse_mode='HTML')

        elif user_state == 'AdminMenu:WaitingUsersDelay':
            try:
                delay = get_delay_int(message.text)
                data = await get_data(message.from_user.id)
                subscribers = data.get('subscribers')
                data = dumps({'subscribers': subscribers, 'delay': delay})
                sql = "INSERT INTO autoscripts (type, state, data, started_at) VALUES (?, ?, ?, UNIXEPOCH() + ?)"
                with sq.connect(db_path) as con:
                    cur = con.cursor()
                    cur.execute(sql, ('subscribers', 'active', data, delay))
                text = 'Автосценарий добавлен'
                await message.answer(text, reply_markup=await keyboards.admin.main_reply())
                await set_state(message.from_user.id, 'AdminMenu:Main')
                await set_data(message.from_user.id, {})
            except:
                text = ('Не удалось извлечь временную задержку между добавлением подписчиков, '
                        'сообщение не соответвествует шаблону. Попробуйте еще раз.')
                await message.answer(text=text, reply_markup=kb_cancel)

    elif user_state in ('AdminMenu:WaitingBalanceAdmin', 'AdminMenu:WaitingBalanceValue',
                        'AdminMenu:WaitingBalanceStatistic', 'AdminMenu:WaitingBalanceMessage',
                        'AdminMenu:WaitingBalanceDelay'):
        kb_cancel = await keyboards.general.cancel()
        if message.text == 'Отмена ✖️':
            await set_state(message.from_user.id, 'AdminMenu:Main')
            await set_data(message.from_user.id, {})
            await bot.send_message(message.chat.id, 'Добавление автосценария отменено',
                                   reply_markup=await keyboards.admin.main_reply())
            await bot.send_message(message.chat.id, 'Админ-панель',
                                   reply_markup=await keyboards.admin.main_inline(message.from_user.id))

        elif user_state == 'AdminMenu:WaitingBalanceValue':
            if message.text.isdigit():
                await set_state(message.from_user.id, 'AdminMenu:WaitingBalanceStatistic')
                await update_data(message.from_user.id, {'value': int(message.text)})
                text = 'Введите текст для статистики:'
            else:
                text = ('Не удалось извлечь значение пополнения баланса, ожидалось число. '
                        'Попробуйте еще раз.')
            await message.answer(text=text, reply_markup=kb_cancel)

        elif user_state == 'AdminMenu:WaitingBalanceStatistic':
            await set_state(message.from_user.id, 'AdminMenu:WaitingBalanceMessage')
            await update_data(message.from_user.id, {'statistic': message.text})
            text = 'Введите текст для сообщения пользователю:'
            await message.answer(text=text, reply_markup=kb_cancel)

        elif user_state == 'AdminMenu:WaitingBalanceMessage':
            await set_state(message.from_user.id, 'AdminMenu:WaitingBalanceDelay')
            await update_data(message.from_user.id, {'msg': message.text})
            text = 'Введите временную задержку в формате <code>3д 12ч 25м 13с</code>:'
            await message.answer(text=text, reply_markup=kb_cancel, parse_mode='HTML')

        elif user_state == 'AdminMenu:WaitingBalanceDelay':
            try:
                delay = get_delay_int(message.text)
                data = await get_data(message.from_user.id)
                data.update({'delay': delay})
                data = dumps(data, ensure_ascii=False)
                sql = "INSERT INTO autoscripts (type, state, data, started_at) VALUES (?, ?, ?, UNIXEPOCH() + ?)"
                with sq.connect(db_path) as con:
                    cur = con.cursor()
                    cur.execute(sql, ('balances', 'active', data, delay))
                text = 'Автосценарий добавлен'
                await message.answer(text, reply_markup=await keyboards.admin.main_reply())
                await set_state(message.from_user.id, 'AdminMenu:Main')
                await set_data(message.from_user.id, {})
            except:
                text = ('Не удалось извлечь временную задержку, сообщение не соответвествует шаблону. '
                        'Попробуйте еще раз.')
                await message.answer(text=text, reply_markup=kb_cancel)





@dp.callback_query_handler(lambda c: c.data, state=AdminMenu)
async def admin_menu_callback_handler(call: types.CallbackQuery, state: FSMContext):
    user_state = await state.get_state()
    if user_state == 'AdminMenu:Main':
        # Кнопка "Пользователи"
        if call.data == 'admin_users':
            await delete_message(call.message.chat.id, call.message.message_id)
            await functions.send_users_list(chat_id=call.message.chat.id,
                                            keyboard=await keyboards.admin.main_reply())
            await bot.send_message(call.message.chat.id, 'Админ-панель',
                                   reply_markup=await keyboards.admin.main_inline(call.from_user.id))

        # Кнопка "Разовая рассылка"
        elif call.data == 'admin_mailing':
            await set_state(call.from_user.id, 'AdminMenu:Mailing')
            await state.update_data(MailingPhoto=None, MailingText=None)
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            await bot.send_message(call.message.chat.id, 'Пришлите изображение для разовой рассылки',
                                   reply_markup=await keyboards.general.cancel())

        # Кнопка "Стартовая рассылка"
        elif call.data == 'admin_start_message':
            await set_state(call.from_user.id, 'AdminMenu:StartMessage')
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=await keyboards.admin.start_message())

        # Кнопка "Авто-рассылка"
        elif call.data == 'admin_auto-mailing':
            await set_state(call.from_user.id, 'AdminAutoMailing:Main')
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=await keyboards.admin.auto_mailing())

        # Кнопка "Администраторы"
        elif call.data == 'admin_admins':
            await set_state(call.from_user.id, 'AdminAdmins:Main')
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=await keyboards.admin.admins_main())

        # Кнопка "Балансы"
        elif call.data == 'admin_balances':
            await set_state(call.from_user.id, 'AdminMenu:Balance')
            await state.update_data(UserTid=None, NewBalance=None)
            await bot.send_message(call.message.chat.id, 'Выберите пользователя, которому хотите изменить баланс',
                                   reply_markup=await keyboards.general.cancel())
            await functions.send_balances_list(chat_id=call.message.chat.id, user=call.from_user)

        # Кнопка "Продукты"
        elif call.data == 'admin_products':
            await set_state(call.from_user.id, 'AdminProducts:Main')
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=await keyboards.admin.products_main())

        # Кнопка "Статистика"
        elif call.data == 'admin_stats':
            await set_state(call.from_user.id, 'AdminStats:Main')
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=await keyboards.admin.stats_main())

        # Кнопка "Добавить пользователей"
        elif call.data == 'admin_add_users':
            await set_state(call.from_user.id, 'AdminMenu:AddUsers')
            text = '''Пришлите список пользователей в следующем формате:

@username1,111000111
@username2,222000222
@username3,333000333
...'''
            await bot.send_message(call.message.chat.id, text,
                                   reply_markup=await keyboards.general.cancel())

        # Кнопка "Удалить пользователей"
        elif call.data == 'admin_delete_users':
            await set_state(call.from_user.id, 'AdminMenu:DeleteUsers')
            text = '''Пришлите список пользователей в следующем формате:

111000111
222000222
333000333
...'''
            await bot.send_message(call.message.chat.id, text,
                                   reply_markup=await keyboards.general.cancel())

        elif call.data == 'autoscripts':
            kb = keyboards.admin.autoscripts()
            text = 'Выберите автосценарий:'
            await call.message.edit_text(text=text, reply_markup=kb)

        elif call.data == 'add_subscribers':
            await set_state(call.from_user.id, 'AdminMenu:WaitingUsersList')
            await call.answer()
            kb = await keyboards.general.cancel()
            text = ('Отправьте список пользователей в формате:\n\n'
                    '@username1 (1111111111)\n'
                    '@username2 (2222222222)\n'
                    '@username3 (3333333333)')
            await bot.send_message(chat_id=call.from_user.id,
                                   text=text,
                                   reply_markup=kb)
        elif call.data == 'add_balances':
            await set_state(call.from_user.id, 'AdminMenu:WaitingBalanceAdmin')
            await call.answer()
            kb = await keyboards.admin.get_admins_second_level()
            text = 'Выберите админа второго уровня для запуска автосценария:'
            await bot.send_message(chat_id=call.from_user.id,
                                   text=text,
                                   reply_markup=kb)

    elif user_state == 'AdminMenu:WaitingBalanceAdmin':
        if call.data.startswith('choice_admin_'):
            await call.answer()
            admin_id = call.data.replace('choice_admin_', '')
            await update_data(call.from_user.id, {'admin_id': admin_id})
            text = "Отправьте сумму пополнения баланса:"
            await bot.send_message(chat_id=call.from_user.id, text=text, reply_markup=await keyboards.general.cancel())
            await set_state(call.from_user.id, 'AdminMenu:WaitingBalanceValue')



    elif user_state == 'AdminMenu:StartMessage':
        if call.data == 'activate_start_message':
            with sq.connect(db_path) as con:
                cur = con.cursor()
                cur.execute('''
                    update start_message set status = ?
                ''', ('Active',))
            await bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                                reply_markup=await keyboards.admin.start_message())
            await bot.answer_callback_query(call.id, 'Активировано ✅')

        elif call.data == 'deactivate_start_message':
            with sq.connect(db_path) as con:
                cur = con.cursor()
                cur.execute('''
                    update start_message set status = ?
                ''', ('Passive',))
            await bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                                reply_markup=await keyboards.admin.start_message())
            await bot.answer_callback_query(call.id, 'Деактивировано ✅')

        elif call.data == 'admin_edit_start_message':
            await state.update_data(StrMsgPhoto=None, StrMsgText=None)
            await delete_message(call.message.chat.id, call.message.message_id, True)
            await bot.send_message(call.message.chat.id, 'Пришлите фотографию стартового сообщения',
                                   reply_markup=await keyboards.general.cancel())

        elif call.data == 'admin_start_message_back':
            await set_state(call.from_user.id, 'AdminMenu:Main')
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=await keyboards.admin.main_inline(call.from_user.id))

    elif user_state == 'AdminMenu:Balance':
        if call.data.startswith('admin_edit_balance_'):
            user_tid = int(call.data.split('_')[3])
            await state.update_data(UserTid=user_tid)
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=None)
            await bot.send_message(call.message.chat.id, 'Напишите новый баланс пользователя',
                                   reply_markup=await keyboards.general.cancel())



@dp.callback_query_handler(lambda c: c.data, state=AdminAdmins)
async def admin_admins_callback_handler(call: types.CallbackQuery, state: FSMContext):
    user_state = await state.get_state()

    if user_state == 'AdminAdmins:Main':
        if call.data == 'admin_admins_add':
            await set_state(call.from_user.id, 'AdminAdmins:Add')
            #print(await state.get_state())
            await state.update_data(AdminId=None, AdminLevel=None)
            await delete_message(call.message.chat.id, call.message.message_id, True)
            text = '''Пришлите сообщение или ID пользователя, которого хотите назначить админом'''
            await bot.send_message(call.message.chat.id, text, reply_markup=await keyboards.general.cancel())

        elif call.data == 'admin_admins_delete':
            await set_state(call.from_user.id, 'AdminAdmins:Delete')
            await delete_message(call.message.chat.id, call.message.message_id, True)
            await functions.send_admins_list_to_delete(chat_id=call.message.chat.id, user=call.from_user)

        elif call.data == 'admin_admins_back':
            await set_state(call.from_user.id, 'AdminMenu:Main')
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=await keyboards.admin.main_inline(call.from_user.id))

    elif user_state == 'AdminAdmins:Delete':
        if call.data.startswith('admin_delete_admin_'):
            await set_state(call.from_user.id, 'AdminAdmins:Main')

            admin_tid = int(call.data.split('_')[3])
            with sq.connect(db_path) as con:
                cur = con.cursor()
                cur.execute('''
                    delete from admins where t_id = ?
                ''', (admin_tid,))
            await set_state(admin_tid, 'UserMenu:Main')

            await bot.answer_callback_query(call.id, 'Админ удалён ✅')
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=None)
            await bot.send_message(call.message.chat.id, 'Админ-панель',
                                   reply_markup=await keyboards.admin.admins_main())

        elif call.data == 'admin_delete_admins_back':
            await set_state(call.from_user.id, 'AdminAdmins:Main')
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=None)
            await bot.send_message(call.message.chat.id, 'Админ-панель',
                                   reply_markup=await keyboards.admin.admins_main())


@dp.callback_query_handler(lambda c: c.data, state=AdminAutoMailing)
async def admin_auto_mailing_callback_handler(call: types.CallbackQuery, state: FSMContext):
    user_state = await state.get_state()

    if user_state == 'AdminAutoMailing:Main':
        if call.data == 'admin_auto-mailing_add':
            await set_state(call.from_user.id, 'AdminAutoMailing:Add')
            await state.update_data(AutoMailingHours=None, AutoMailingText=None, AutoMailingPhoto=None)
            await delete_message(call.message.chat.id, call.message.message_id, True)
            text = '''Напишите через какое кол-во часов после регистрации получать рассылку'''
            await bot.send_message(call.message.chat.id, text, reply_markup=await keyboards.general.cancel())

        elif call.data == 'admin_auto-mailing_delete':
            await set_state(call.from_user.id, 'AdminAutoMailing:Delete')
            await delete_message(call.message.chat.id, call.message.message_id, True)
            await functions.send_auto_mailing_to_delete(chat_id=call.message.chat.id)

        elif call.data == 'admin_auto-mailing_back':
            await set_state(call.from_user.id, 'AdminMenu:Main')
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=await keyboards.admin.main_inline(call.from_user.id))

    elif user_state == 'AdminAutoMailing:Delete':
        if call.data.startswith('admin_delete_auto-mailing_'):
            auto_mailing_id = int(call.data.split('_')[3])
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=None)
            with sq.connect(db_path) as con:
                cur = con.cursor()
                auto_mailing_info = cur.execute('''
                    select hours, text, photo from auto_mailings where id = ?
                ''', (auto_mailing_id,)).fetchone()
            if auto_mailing_info is not None:
                hours, text, photo = auto_mailing_info
                text += f'''
                
Рассылка приходит через {hours} часов после регистрации'''
                await bot.send_photo(call.message.chat.id, photo, text,
                                     reply_markup=await keyboards.admin.totally_delete_auto_mailing(auto_mailing_id))
            else:
                await bot.answer_callback_query(call.id, 'Такой авто-рассылки больше нет')

        elif call.data.startswith('admin_totally_delete_auto-mailing_'):
            await set_state(call.from_user.id, 'AdminAutoMailing:Main')

            auto_mailing_id = int(call.data.split('_')[4])
            with sq.connect(db_path) as con:
                cur = con.cursor()
                cur.execute('''
                    delete from auto_mailings where id = ?
                ''', (auto_mailing_id,))
                cur.execute('''
                    delete from users_auto_mailings where auto_mailing_id = ?
                ''', (auto_mailing_id,))

            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=None)
            await bot.answer_callback_query(call.id, 'Авто-рассылка удалена ✅')
            await bot.send_message(call.message.chat.id, 'Админ-меню',
                                   reply_markup=await keyboards.admin.auto_mailing())

        elif call.data == 'admin_totally_deleting_auto-mailing_back':
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=None)
            await functions.send_auto_mailing_to_delete(chat_id=call.message.chat.id)

        elif call.data == 'admin_delete_auto-mailings_back':
            await set_state(call.from_user.id, 'AdminAdmins:Main')
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=None)
            await bot.send_message(call.message.chat.id, 'Админ-панель',
                                   reply_markup=await keyboards.admin.admins_main())


@dp.callback_query_handler(lambda c: c.data, state=AdminProducts)
async def admin_stats_callback_handler(call: types.CallbackQuery, state: FSMContext):
    user_state = await state.get_state()

    if user_state == 'AdminProducts:Main':
        if call.data == 'admin_products_add':
            await set_state(call.from_user.id, 'AdminProducts:Add')
            await delete_message(call.message.chat.id, call.message.message_id, True)
            text = '''Напишите текст продукта'''
            await bot.send_message(call.message.chat.id, text, reply_markup=await keyboards.general.cancel())

        elif call.data == 'admin_products_delete':
            await set_state(call.from_user.id, 'AdminProducts:Delete')
            await delete_message(call.message.chat.id, call.message.message_id, True)
            await functions.send_products_to_delete(chat_id=call.message.chat.id)

        elif call.data == 'admin_products_back':
            await set_state(call.from_user.id, 'AdminMenu:Main')
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=await keyboards.admin.main_inline(call.from_user.id))

    elif user_state == 'AdminProducts:Delete':
        if call.data.startswith('admin_delete_product_'):
            product_id = int(call.data.split('_')[3])
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=None)
            with sq.connect(db_path) as con:
                cur = con.cursor()
                product_text = cur.execute('''
                    select text from products where id = ?
                ''', (product_id,)).fetchone()
            if product_text is not None:
                await bot.send_message(call.message.chat.id, product_text[0],
                                       reply_markup=await keyboards.admin.totally_delete_product(product_id))
            else:
                await bot.answer_callback_query(call.id, 'Такого продукта больше нет')

        elif call.data.startswith('admin_totally_delete_product_'):
            await set_state(call.from_user.id, 'AdminProducts:Main')

            product_id = int(call.data.split('_')[4])
            with sq.connect(db_path) as con:
                cur = con.cursor()
                cur.execute('''
                    delete from products where id = ?
                ''', (product_id,))

            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=None)
            await bot.answer_callback_query(call.id, 'Продукт удалена ✅')
            await bot.send_message(call.message.chat.id, 'Админ-меню',
                                   reply_markup=await keyboards.admin.products_main())

        elif call.data == 'admin_totally_deleting_product_back':
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=None)
            await functions.send_products_to_delete(chat_id=call.message.chat.id)

        elif call.data == 'admin_delete_products_back':
            await set_state(call.from_user.id, 'AdminProducts:Main')
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=None)
            await bot.send_message(call.message.chat.id, 'Админ-панель',
                                   reply_markup=await keyboards.admin.products_main())


@dp.callback_query_handler(lambda c: c.data, state=AdminStats)
async def admin_stats_callback_handler(call: types.CallbackQuery, state: FSMContext):
    user_state = await state.get_state()

    if user_state == 'AdminStats:Main':
        if call.data == 'admin_stats_add':
            await set_state(call.from_user.id, 'AdminStats:Add')
            await delete_message(call.message.chat.id, call.message.message_id, True)
            text = '''Напишите текст статистики'''
            await bot.send_message(call.message.chat.id, text, reply_markup=await keyboards.general.cancel())

        elif call.data == 'admin_stats_delete':
            await set_state(call.from_user.id, 'AdminStats:Delete')
            await delete_message(call.message.chat.id, call.message.message_id, True)
            await functions.send_stats_to_delete(chat_id=call.message.chat.id)

        elif call.data == 'admin_stats_back':
            await set_state(call.from_user.id, 'AdminMenu:Main')
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=await keyboards.admin.main_inline(call.from_user.id))

    elif user_state == 'AdminStats:Delete':
        if call.data.startswith('admin_delete_stat_'):
            stat_id = int(call.data.split('_')[3])
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=None)
            with sq.connect(db_path) as con:
                cur = con.cursor()
                stat_text = cur.execute('''
                    select text from stats where id = ?
                ''', (stat_id,)).fetchone()
            if stat_text is not None:
                await bot.send_message(call.message.chat.id, stat_text[0],
                                       reply_markup=await keyboards.admin.totally_delete_stat(stat_id))
            else:
                await bot.answer_callback_query(call.id, 'Такой статистики больше нет')

        elif call.data.startswith('admin_totally_delete_stat_'):
            await set_state(call.from_user.id, 'AdminStats:Main')

            stat_id = int(call.data.split('_')[4])
            with sq.connect(db_path) as con:
                cur = con.cursor()
                cur.execute('''
                    delete from stats where id = ?
                ''', (stat_id,))

            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=None)
            await bot.answer_callback_query(call.id, 'Статистика удалена ✅')
            await bot.send_message(call.message.chat.id, 'Админ-меню',
                                   reply_markup=await keyboards.admin.stats_main())

        elif call.data == 'admin_totally_deleting_stat_back':
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=None)
            await functions.send_stats_to_delete(chat_id=call.message.chat.id)

        elif call.data == 'admin_delete_stats_back':
            await set_state(call.from_user.id, 'AdminStats:Main')
            await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                reply_markup=None)
            await bot.send_message(call.message.chat.id, 'Админ-панель',
                                   reply_markup=await keyboards.admin.stats_main())


scheduler = AsyncIOScheduler()

if __name__ == '__main__':
    scheduler.start()
    scheduler.add_job(functions.auto_mailing, 'interval', minutes=1, args=())
    scheduler.add_job(functions.run_autoscripts, 'interval', seconds=10, args=())
    executor.start_polling(dp, on_startup=on_start, skip_updates=True)
