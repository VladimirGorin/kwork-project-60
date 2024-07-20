import asyncio
import sqlite3 as sq
from datetime import datetime, timedelta
from html import escape as esc
from json import dumps, loads

from aiogram import types
from aiogram.utils.exceptions import RetryAfter

from config import bot, db_path, storage
import keyboards


async def on_start(dispatcher):
    print(dispatcher)

    await bot.set_my_commands([])

    with sq.connect(db_path) as con:
        cur = con.cursor()

        # admins
        cur.execute('''create table if not exists admins(
            id integer primary key,
            t_id integer,
            access_level default 2
        )''')

        # auto_mailings
        cur.execute('''create table if not exists auto_mailings(
            id integer primary key,
            hours integer,
            text text,
            photo text
        )''')

        # stats
        cur.execute('''create table if not exists products(
            id integer primary key,
            text text
        )''')

        # start_message
        cur.execute('''create table if not exists start_message(
            id integer primary key,
            text text,
            photo text,
            status text default 'Passive'
        )''')

        # stats
        cur.execute('''create table if not exists stats(
            id integer primary key,
            text text
        )''')

        # users
        cur.execute('''create table if not exists users(
            id integer primary key,
            t_id integer,
            first_name text,
            username text,
            balance integer default 0,
            reg_date text,
            state text,
            data text
        )''')

        # users_auto_mailings
        cur.execute('''create table if not exists users_auto_mailings(
            id integer primary key,
            auto_mailing_id integer,
            user_tid integer,
            text text,
            photo text,
            mailing_date text
        )''')

        cur.execute('''create table if not exists autoscripts (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            "type" TEXT,
            state TEXT,
            "data" TEXT,
            started_at text
        )''')

        users = cur.execute('''
            select t_id, state, ifnull(data, '{}') from users
        ''').fetchall()

    for t_id, state, data in users:
        await storage.set_state(user=t_id, chat=t_id, state=state)
        await storage.set_data(user=t_id, chat=t_id, data=loads(data))


async def set_state(t_id, state):
    """
    Функция для назначения состояние.
    :param t_id: Telegram id пользователя, которому нужно назначить состояние.
    :param state: Состояние, которое нужно назначить.
    :return:
    """

    with sq.connect(db_path) as con:
        cur = con.cursor()
        cur.execute(f'''
            update users set state = ? where t_id = ?
        ''', (state, t_id))
    await storage.set_state(user=t_id, chat=t_id, state=state)


async def set_data(t_id, data: dict = {}):
    """
    Функция для назначения данных состояния.
    :param t_id: Telegram id пользователя, которому нужно назначить состояние.
    :param data: Данные состояния, которое нужно назначить.
    :return:
    """
    with sq.connect(db_path) as con:
        cur = con.cursor()
        cur.execute(f'''
            update users set data = ? where t_id = ?
        ''', (dumps(data, ensure_ascii=False), t_id))


async def update_data(t_id, new_data: dict):
    data: dict = await get_data(t_id)
    data.update(new_data)
    await set_data(t_id, data)

async def get_data(t_id):
    """
    Функция для назначения данных состояния.
    :param t_id: Telegram id пользователя, которому нужно назначить состояние.
    :param data: Данные состояния, которое нужно назначить.
    :return:
    """
    sql = "SELECT ifnull(data, '{}') FROM users WHERE t_id = ?"
    with sq.connect(db_path) as con:
        cur = con.cursor()
        data = cur.execute(sql, (t_id,)).fetchone()
    if data:
        return loads(data[0])
    else:
        return {}



async def delete_message(chat_id, message_id, remove_keyboard=False):
    """
    Функция для удаления сообщений.
    :param chat_id: Id чата, где мы хотим удалить сообщение.
    :param message_id: Id сообщения, которое мы хотим удалить
    :param remove_keyboard: Если True, то при ошибке удаления уберёт inline-клавиатуру сообщения.
    :return:
    """

    try:
        await bot.delete_message(chat_id, message_id)
    except Exception as err:
        print(err)
        if remove_keyboard is True:
            await bot.edit_message_reply_markup(chat_id, message_id, reply_markup=None)


async def registration_insertion(user):
    """
    Функция для добавления данных пользователя в БД при регистрации.
    :param user: Данные пользователя.
    :return:
    """

    reg_date = datetime.now()
    with sq.connect(db_path) as con:
        cur = con.cursor()
        cur.execute('''
            insert into users(t_id, first_name, username, reg_date) values(?, ?, ?, ?)
        ''', (user.id, user.first_name, f'@{user.username}', reg_date.strftime('%d-%m-%Y %H:%M')))
        auto_mailings = cur.execute('''
            select id, hours, text, photo from auto_mailings
        ''').fetchall()
        for record_id, hours, text, photo in auto_mailings:
            cur.execute('''
                insert into users_auto_mailings(auto_mailing_id, user_tid, text, photo, mailing_date)
                values(?, ?, ?, ?, ?)
            ''', (record_id, user.id, text, photo,
                  (reg_date + timedelta(hours=hours)).strftime('%d-%m-%Y %H:%M')))


async def auto_mailing():
    """
    Функция для авто-рассылки.
    :return:
    """

    with sq.connect(db_path) as con:
        cur = con.cursor()
        auto_mailings = cur.execute('''
            select users_auto_mailings.id, user_tid, users.first_name, text, photo, mailing_date
            from users_auto_mailings join users on users_auto_mailings.user_tid = users.t_id
        ''').fetchall()
    for record_id, user_tid, user_first_name, text, photo, mailing_date in auto_mailings:
        if datetime.now() >= datetime.strptime(mailing_date, '%d-%m-%Y %H:%M'):
            with sq.connect(db_path) as con:
                cur = con.cursor()
                cur.execute('''
                    delete from users_auto_mailings where id = ?
                ''', (record_id,))
            try:
                text = text.replace('USERNAME', user_first_name)
                await bot.send_photo(user_tid, photo)
                await asyncio.sleep(0.1)
                await bot.send_message(user_tid, text)
                await asyncio.sleep(0.1)
            except RetryAfter as err:
                await asyncio.sleep(err.timeout)
                await bot.send_photo(user_tid, photo)
                await asyncio.sleep(0.1)
                await bot.send_message(user_tid, text)
                await asyncio.sleep(0.1)
            except Exception as err:
                print(err)


async def send_start_message(chat_id):
    """
    Функция отправляет сообщение при старте бота.
    :param chat_id: Id чата, куда необходимо отправить сообщение.
    :return:
    """

    with sq.connect(db_path) as con:
        cur = con.cursor()
        start_message = cur.execute('''
            select photo, text, status from start_message
        ''').fetchone()
    if start_message is not None and start_message[2] == 'Active':
        photo, text, status = start_message
        if len(photo):
            await bot.send_photo(chat_id, photo)

        await bot.send_message(chat_id, text, reply_markup=types.ReplyKeyboardRemove())
    else:
        await bot.send_message(chat_id, 'Главное меню', reply_markup=types.ReplyKeyboardRemove())


async def mailing(photo, text, entities):
    """
    Функция для разовой рассылки сообщения пользователям.
    :param photo: File_id изображение, которое хотим разослать.
    :param text: Текст, который хотим разослать.
    :param entities: Данные о форматировании текста, который хотим разослать.
    :return:
    """

    with sq.connect(db_path) as con:
        cur = con.cursor()
        users = cur.execute('''
            select t_id, first_name from users
        ''').fetchall()
        admins = [x[0] for x in cur.execute('''
            select t_id from admins
        ''').fetchall()]
        users = [x for x in users if x[0] not in admins]

    for user_tid, user_first_name in users:
        try:

            text = text.replace('USERNAME', user_first_name)
            await bot.send_photo(user_tid, photo)
            await asyncio.sleep(0.1)
            await bot.send_message(user_tid, text, entities=entities)
            await asyncio.sleep(0.1)
        except RetryAfter as err:
            await asyncio.sleep(err.timeout)
            await bot.send_photo(user_tid, photo)
            await asyncio.sleep(0.1)
            await bot.send_message(user_tid, text, entities=entities)
            await asyncio.sleep(0.1)
        except Exception as err:
            print(err)


async def send_users_list(chat_id, keyboard):
    """
    Функция для отправки сообщения/сообщений с данными обо всех пользователях.
    :param chat_id: Id чата, куда хотим отправить сообщение/сообщения.
    :param keyboard: Клавиатура, прикрепляемая к сообщению.
    :return:
    """

    with sq.connect(db_path) as con:
        cur = con.cursor()
        users = cur.execute('''
            select username, t_id from users
        ''').fetchall()

    texts = ['''Список всех пользователей

''']
    number = 0
    for username, t_id in users:
        number += 1
        if username == '@None':
            texts.append(f'''{number}) <a href="tg://user?id={t_id}">Пользователь</a> ( {t_id} )
''')
        else:
            texts.append(f'''{number}) {esc(username)} ( {t_id} )
''')

    sending_message = ''''''
    for text in texts:
        if len(sending_message) + len(text) >= 4096:
            await bot.send_message(chat_id, sending_message, parse_mode='HTML')
            sending_message = text
        else:
            sending_message += text
        if texts.index(text) == len(texts) - 1:
            await bot.send_message(chat_id, sending_message, parse_mode='HTML', reply_markup=keyboard)


async def add_auto_mailing(hours, text, photo):
    """
    Функция для добавления в БД авто-рассылки.
    :param hours: Кол-во часов после регистрации, после которое пользователи получат рассылку.
    :param text: Текст авто-рассылки.
    :param photo: Фотография авто-рассылки.
    :return:
    """

    with sq.connect(db_path) as con:
        cur = con.cursor()
        last_record_id = cur.execute('''
            select id from auto_mailings order by id desc
        ''').fetchone()
        if last_record_id is not None:
            last_record_id = last_record_id[0]
        else:
            last_record_id = 0
        cur.execute('''
            insert into auto_mailings(id, hours, text, photo) values(?, ?, ?, ?)
        ''', (last_record_id + 1, hours, text, photo))
        users = cur.execute('''
            select t_id, reg_date from users
        ''').fetchall()
        admins = [x[0] for x in cur.execute('''
            select t_id from admins
        ''').fetchall()]
        users = [x for x in users if x[0] not in admins]
        for user_tid, user_reg_date in users:
            if not user_reg_date:
                user_reg_date = datetime.now().strftime('%d-%m-%Y %H:%M')
            mailing_date = datetime.strptime(user_reg_date, '%d-%m-%Y %H:%M') + timedelta(hours=hours)
            if mailing_date > datetime.now():
                cur.execute('''
                    insert into users_auto_mailings(auto_mailing_id, user_tid, text, photo, mailing_date)
                    values(?, ?, ?, ?, ?)
                ''', (last_record_id + 1, user_tid, text, photo, mailing_date.strftime('%d-%m-%Y %H:%M')))


async def send_auto_mailing_to_delete(chat_id):
    """
    Функция для отправки списка авто-рассылок, которые можно удалить.
    :param chat_id: Id чата, куда отправиться список.
    :return:
    """

    with sq.connect(db_path) as con:
        cur = con.cursor()
        auto_mailings = cur.execute('''
            select id, hours from auto_mailings
        ''').fetchall()

    texts = ['''Выберите авто-рассылку, которую хотите удалить
    
''']
    for auto_mailing_info in auto_mailings:
        record_id, auto_mailing_hours = auto_mailing_info
        texts.append(f'''{auto_mailings.index(auto_mailing_info) + 1}) Кол-во часов: {auto_mailing_hours}
''')

    message = ''''''
    for text in texts:
        if len(message) + len(text) > 4096:
            await bot.send_message(chat_id, message)
            message = text
        else:
            message += text
        if texts.index(text) == len(texts) - 1:
            keyboard = await keyboards.admin.delete_auto_mailings(list(map(lambda i: i[0], auto_mailings)))
            await bot.send_message(chat_id, message, reply_markup=keyboard)


async def send_admins_list_to_delete(chat_id, user):
    """
    Функция для отправки списка пользователь у которых можно отнять права администратора.
    :param chat_id: Id чата, куда отправиться список.
    :param user: Данные админа, чьи данные не должны быть в списке.
    :return:
    """

    with sq.connect(db_path) as con:
        cur = con.cursor()
        admins = cur.execute('''
            select t_id, access_level from admins
        ''').fetchall()
    if (user.id, '1') in admins:
        admins.remove((user.id, '1'))

    texts = ['''Выберите пользователя, которого хотите лишить админки

''']
    for admin in admins:
        admin_tid, admin_access_level = admin
        texts.append(f'''{admins.index(admin) + 1}) {admin_tid} | {admin_access_level}
''')

    message = ''''''
    for text in texts:
        if len(message) + len(text) > 4096:
            await bot.send_message(chat_id, message)
            message = text
        else:
            message += text
        if texts.index(text) == len(texts) - 1:
            keyboard = await keyboards.admin.delete_admins(list(map(lambda i: i[0], admins)))
            await bot.send_message(chat_id, message, reply_markup=keyboard)


async def send_balances_list(chat_id, user):
    """
    Функция для отправки списка пользователей, чей баланс можно изменить.
    :param chat_id: Id чата, куда должен отправиться список.
    :param user: Данные пользователя, которые не должны учитываться.
    :return:
    """

    with sq.connect(db_path) as con:
        cur = con.cursor()
        balances = cur.execute('''
            select admins.t_id, users.balance from admins join users on admins.t_id = users.t_id
        ''').fetchall()
        balances = [x for x in balances if x[0] != user.id]

    texts = []
    for user_info in balances:
        user_tid, user_balance = user_info
        texts.append(f'''{balances.index(user_info) + 1}) {user_tid} | {user_balance} руб
''')

    message = ''''''
    for text in texts:
        if len(message) + len(text) > 4096:
            await bot.send_message(chat_id, message)
            message = text
        else:
            message += text
        if texts.index(text) == len(texts) - 1:
            keyboard = await keyboards.admin.edit_balances(users=list(map(lambda i: i[0], balances)))
            await bot.send_message(chat_id, message, reply_markup=keyboard)


async def send_products(chat_id):
    with sq.connect(db_path) as con:
        cur = con.cursor()
        stats = cur.execute('''
            select id, text from products
        ''').fetchall()

    if len(stats):
        texts = []
        for record_id, product_text in stats:
            texts.append((record_id, f'''{product_text}
'''))

        message = ''''''
        for record_id, text in texts:
            if len(message) + len(text) > 4096:
                await bot.send_message(chat_id, message)
                message = text
            else:
                message += text
            if texts.index((record_id, text)) == len(texts) - 1:
                await bot.send_message(chat_id, message, reply_markup=await keyboards.admin.main_reply())
    else:
        text = '''Продуктов ещё нет... 🕸'''
        await bot.send_message(chat_id, text, reply_markup=await keyboards.admin.main_reply())


async def send_products_to_delete(chat_id):
    with sq.connect(db_path) as con:
        cur = con.cursor()
        products = cur.execute('''
            select id, text from products
        ''').fetchall()

    texts = ['''Выберите продукт, который хотите удалить

''']
    for product in products:
        record_id, stat_text = product
        texts.append(f'''{products.index(product) + 1}) {stat_text[:25]}...
''')

    message = ''''''
    for text in texts:
        if len(message) + len(text) > 4096:
            await bot.send_message(chat_id, message)
            message = text
        else:
            message += text
        if texts.index(text) == len(texts) - 1:
            keyboard = await keyboards.admin.delete_products(list(map(lambda i: i[0], products)))
            await bot.send_message(chat_id, message, reply_markup=keyboard)


async def send_stats(chat_id):
    """
    Функция для отправки списка со статистикой.
    :param chat_id: Id чата, куда отправиться сообщение/сообщения.
    :return:
    """

    with sq.connect(db_path) as con:
        cur = con.cursor()
        stats = cur.execute('''
            select id, "\n" || text || "\n" from stats where t_id = ?
        ''', (chat_id,)).fetchall()

    if len(stats):
        texts = []
        for record_id, stat_text in stats:
            texts.append((record_id, f'''{stat_text}
'''))

        message = ''''''
        for record_id, text in texts:
            if len(message) + len(text) > 4096:
                await bot.send_message(chat_id, message)
                message = text
            else:
                message += text
            if texts.index((record_id, text)) == len(texts) - 1:
                await bot.send_message(chat_id, message, reply_markup=await keyboards.admin.main_reply())
    else:
        text = '''Статистики ещё нет... 🕸'''
        await bot.send_message(chat_id, text, reply_markup=await keyboards.admin.main_reply())


async def send_stats_to_delete(chat_id):
    """
    Функция для отправки списка со статистикой, которую можно удалить.
    :param chat_id: Id чата, куда должен отправиться список.
    :return:
    """

    with sq.connect(db_path) as con:
        cur = con.cursor()
        stats = cur.execute('''
            select id, text from stats
        ''').fetchall()

    texts = ['''Выберите статистику, которую хотите удалить
    
''']
    for stat in stats:
        record_id, stat_text = stat
        texts.append(f'''{stats.index(stat) + 1}) {stat_text[:25]}...
''')

    message = ''''''
    for text in texts:
        if len(message) + len(text) > 4096:
            await bot.send_message(chat_id, message)
            message = text
        else:
            message += text
        if texts.index(text) == len(texts) - 1:
            keyboard = await keyboards.admin.delete_stats(list(map(lambda i: i[0], stats)))
            await bot.send_message(chat_id, message, reply_markup=keyboard)


def get_delay_int(delay_str: str) -> int:
    weights = {'д': 86400, 'ч': 3600, 'м': 60, 'с': 1}
    delay_list = delay_str.split(' ')
    delay_int = 0
    for item in delay_list:
        value = int(item[:-1])
        key = item[-1:]
        delay_int += value * weights[key]
    return delay_int


def get_delay_str(delay_int: int) -> str:
    weights = {'д': 86400, 'ч': 3600, 'м': 60, 'с': 1}
    delay_list = []
    f = delay_int
    for key, value in weights.items():
        i, f = divmod(f, value)
        if i:
            delay_list.append(f'{i}{key}')
    return ' '.join(delay_list)


async def run_autoscripts():
    with sq.connect(db_path) as con:
        cur = con.cursor()
        sql = ("SELECT id, type, state, data, started_at "
               " FROM autoscripts WHERE state = 'active' AND started_at < cast(strftime('%s', 'now') as int)")
        autoscripts = cur.execute(sql).fetchall()
    for autoscript_id, type, state, data, started_at in autoscripts:
        data = loads(data)
        if type == 'balances':
            await autoscript_balances(data['admin_id'], data['value'], data['statistic'], data['msg'])
            with sq.connect(db_path) as con:
                cur = con.cursor()
                sql = "UPDATE autoscripts SET state = 'passive' WHERE id = ?"
                cur.execute(sql, (autoscript_id,))
        elif type == 'subscribers':
            if await autoscript_subscribers(data['subscribers']):
                with sq.connect(db_path) as con:
                    cur = con.cursor()
                    sql = "UPDATE autoscripts SET state = 'passive' WHERE id = ?"
                    cur.execute(sql, (autoscript_id,))
            else:
                with sq.connect(db_path) as con:
                    cur = con.cursor()
                    sql = "UPDATE autoscripts SET started_at = cast(strftime('%s', 'now') as int) + ? WHERE id = ?"
                    cur.execute(sql, (data['delay'], autoscript_id,))

async def autoscript_subscribers(subscribers: list) -> bool:
    with sq.connect(db_path) as con:
        cur = con.cursor()

        sql = "SELECT distinct t_id FROM users"
        users = cur.execute(sql).fetchall()
        users = set(user[0] for user in users)
        for subscriber in subscribers:
            if subscriber['user_id'] not in users:
                sql = 'INSERT INTO users (t_id, username) VALUES (?, ?)'
                cur.execute(sql, (subscriber['user_id'], subscriber['username']))
                return False
        else:
            return True


async def autoscript_balances(admin_id: int, value: int, statistic: str, msg: str):
    with sq.connect(db_path) as con:
        cur = con.cursor()
        sql = "INSERT INTO stats (t_id, text) VALUES (?, ?)"
        cur.execute(sql, (admin_id, statistic))

        sql = "UPDATE users SET balance = balance + ? WHERE t_id = ?"
        cur.execute(sql, (value, admin_id))

    await bot.send_message(chat_id=admin_id,
                           text=msg,
                           parse_mode='HTML')



