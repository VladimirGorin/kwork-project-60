import sqlite3 as sq

from aiogram import types

from config import db_path


async def main_reply():
    """
    Главная reply-клавиатура администраторов.
    :return: Reply-клавиатура.
    """

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2).add(
        types.KeyboardButton(text='💰 Баланс'),
        types.KeyboardButton(text='📊 Статистика'),
        types.KeyboardButton(text='🛒 Ваши продукты'),
        types.KeyboardButton(text='✅ Запустить рекламу'),
        types.KeyboardButton(text='💳 Вывод средств'),
        types.KeyboardButton(text='📞 Поддержка')
    )
    return keyboard


async def main_inline(admin_tid):
    """
    Главная inline-клавиатура администраторов.
    :param admin_tid: Telegram id администратора.
    :return: Inline-клавиатура
    """

    keyboard = types.InlineKeyboardMarkup(row_width=1)
    buttons = [
        types.InlineKeyboardButton(callback_data='admin_users', text='Пользователи'),
        types.InlineKeyboardButton(callback_data='admin_mailing', text='Разовая рассылка'),
        types.InlineKeyboardButton(callback_data='admin_start_message', text='Стартовая рассылка'),
        types.InlineKeyboardButton(callback_data='admin_auto-mailing', text='Авто-рассылка')
    ]

    with sq.connect(db_path) as con:
        cur = con.cursor()
        admin_access_level = cur.execute('''
            select access_level from admins where t_id = ?
        ''', (admin_tid,)).fetchone()[0]

    if int(admin_access_level) == 1:
        buttons += [
            types.InlineKeyboardButton(callback_data='admin_admins', text='Админы'),
            types.InlineKeyboardButton(callback_data='admin_balances', text='Балансы'),
            types.InlineKeyboardButton(callback_data='admin_products', text='Продукты'),
            types.InlineKeyboardButton(callback_data='admin_stats', text='Статистика'),
            types.InlineKeyboardButton(callback_data='admin_add_users', text='Добавить пользователей'),
            types.InlineKeyboardButton(callback_data='admin_delete_users', text='Удалить пользователей'),
            types.InlineKeyboardButton(callback_data='autoscripts', text='Автосценарии')
        ]

    keyboard.add(*buttons)
    return keyboard


# Раздел "Стартовая рассылка"
async def start_message():
    """
    Клавиатура для управления стартовым сообщением.
    :return: Inline-клавиатура.
    """

    with sq.connect(db_path) as con:
        cur = con.cursor()
        status = cur.execute('''
            select status from start_message
        ''').fetchone()

    keyboard = types.InlineKeyboardMarkup(row_width=1)
    if status is not None and status[0] == 'Active':
        keyboard.add(types.InlineKeyboardButton(callback_data='deactivate_start_message', text='Деактивировать ⏹'))
    elif status is not None and status[0] == 'Passive':
        keyboard.add(types.InlineKeyboardButton(callback_data='activate_start_message', text='Активировать ▶️'))
    keyboard.add(
        types.InlineKeyboardButton(callback_data='admin_edit_start_message', text='Изменить сообщение'),
        types.InlineKeyboardButton(callback_data='admin_start_message_back', text='⬅️ Назад')
    )
    return keyboard


# Раздел "Авто-рассылка"
async def auto_mailing():
    """
    Клавиатура для управления авто-рассылкой.
    :return: Inline-клавиатура.
    """

    keyboard = types.InlineKeyboardMarkup(row_width=1).add(
        types.InlineKeyboardButton(callback_data='admin_auto-mailing_add', text='Добавить ➕'),
        types.InlineKeyboardButton(callback_data='admin_auto-mailing_delete', text='Удалить ➖'),
        types.InlineKeyboardButton(callback_data='admin_auto-mailing_back', text='⬅️ Назад')
    )
    return keyboard


async def delete_auto_mailings(auto_mailings):
    """
    Клавиатура для удаления авто-рассылок.
    :param auto_mailings: Список с ID авто-рассылок, которые можно удалить.
    :return: Inline-клавиатура.
    """

    keyboard = types.InlineKeyboardMarkup(row_width=5)
    buttons = []

    for admin_tid in auto_mailings:
        buttons.append(
            types.InlineKeyboardButton(callback_data=f'admin_delete_auto-mailing_{admin_tid}',
                                       text=str(auto_mailings.index(admin_tid) + 1))
        )

    keyboard.add(*buttons)
    keyboard.add(types.InlineKeyboardButton(callback_data='admin_delete_auto-mailings_back', text='⬅️ Назад'))
    return keyboard


async def totally_delete_auto_mailing(auto_mailing_id):
    """
    Клавиатура для остаточного удаления авто-рассылки.
    :param auto_mailing_id: Id авто-рассылки, которое хотим удалить.
    :return: Inline-клавиатура.
    """

    keyboard = types.InlineKeyboardMarkup(row_width=2).add(
        types.InlineKeyboardButton(callback_data=f'admin_totally_delete_auto-mailing_{auto_mailing_id}',
                                   text='Удалить ❌'),
        types.InlineKeyboardButton(callback_data='admin_totally_deleting_auto-mailing_back',
                                   text='⬅️ Назад')
    )
    return keyboard


# Раздел "Админы"
async def admins_main():
    """
    Главная клавиатура раздела "Администраторы".
    :return: Inline-клавиатура
    """

    keyboard = types.InlineKeyboardMarkup(row_width=1).add(
        types.InlineKeyboardButton(callback_data='admin_admins_add', text='Добавить ➕'),
        types.InlineKeyboardButton(callback_data='admin_admins_delete', text='Удалить ➖'),
        types.InlineKeyboardButton(callback_data='admin_admins_back', text='⬅️ Назад')
    )
    return keyboard


async def delete_admins(admins):
    """
    Клавиатура для удаления админов.
    :param admins: Список с telegram id админов, которых можно удалить.
    :return: Inline-клавиатура.
    """

    keyboard = types.InlineKeyboardMarkup(row_width=5)
    buttons = []

    for admin_tid in admins:
        buttons.append(
            types.InlineKeyboardButton(callback_data=f'admin_delete_admin_{admin_tid}',
                                       text=str(admins.index(admin_tid) + 1))
        )

    keyboard.add(*buttons)
    keyboard.add(types.InlineKeyboardButton(callback_data='admin_delete_admins_back', text='⬅️ Назад'))
    return keyboard


async def admin_levels():
    """
    Клавиатура для выбора уровня администратора при его назначении.
    :return: Reply-клавиатура.
    """

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2).add(
        types.KeyboardButton(text='1'),
        types.KeyboardButton(text='2'),
        types.KeyboardButton(text='Отмена ✖️')
    )
    return keyboard


# Раздел "Балансы"
async def edit_balances(users):
    """
    Клавиатура для выбора пользователя, которому можно изменить баланс.
    :param users: Список пользователей, которым можно изменить баланс.
    :return: Inline-клавиатура.
    """

    keyboard = types.InlineKeyboardMarkup(row_width=5)
    buttons = []

    for user_tid in users:
        buttons.append(
            types.InlineKeyboardButton(callback_data=f'admin_edit_balance_{user_tid}',
                                       text=str(users.index(user_tid) + 1))
        )

    keyboard.add(*buttons)
    return keyboard


# Раздел "Продукты"
async def products_main():
    keyboard = types.InlineKeyboardMarkup(row_width=1).add(
        types.InlineKeyboardButton(callback_data='admin_products_add', text='Добавить ➕'),
        types.InlineKeyboardButton(callback_data='admin_products_delete', text='Удалить ➖'),
        types.InlineKeyboardButton(callback_data='admin_products_back', text='⬅️ Назад')
    )
    return keyboard


async def delete_products(stats):
    keyboard = types.InlineKeyboardMarkup(row_width=5)
    buttons = []

    for stat_id in stats:
        buttons.append(
            types.InlineKeyboardButton(callback_data=f'admin_delete_product_{stat_id}',
                                       text=str(stats.index(stat_id) + 1))
        )

    keyboard.add(*buttons)
    keyboard.add(types.InlineKeyboardButton(callback_data='admin_delete_products_back', text='⬅️ Назад'))
    return keyboard


async def totally_delete_product(stat_id):
    keyboard = types.InlineKeyboardMarkup(row_width=2).add(
        types.InlineKeyboardButton(callback_data=f'admin_totally_delete_product_{stat_id}',
                                   text='Удалить ❌'),
        types.InlineKeyboardButton(callback_data='admin_totally_deleting_product_back',
                                   text='⬅️ Назад')
    )
    return keyboard


# Раздел "Статистика"
async def stats_main():
    """
    Главная клавиатура раздела "Статистика".
    :return: Inline-клавиатура.
    """

    keyboard = types.InlineKeyboardMarkup(row_width=1).add(
        types.InlineKeyboardButton(callback_data='admin_stats_add', text='Добавить ➕'),
        types.InlineKeyboardButton(callback_data='admin_stats_delete', text='Удалить ➖'),
        types.InlineKeyboardButton(callback_data='admin_stats_back', text='⬅️ Назад')
    )
    return keyboard


async def delete_stats(stats):
    """
    Клавиатура для удаления статистики.
    :param stats: Список с ID со статистиками, которые можно удалить.
    :return: Inline-клавиатура.
    """

    keyboard = types.InlineKeyboardMarkup(row_width=5)
    buttons = []

    for stat_id in stats:
        buttons.append(
            types.InlineKeyboardButton(callback_data=f'admin_delete_stat_{stat_id}',
                                       text=str(stats.index(stat_id) + 1))
        )

    keyboard.add(*buttons)
    keyboard.add(types.InlineKeyboardButton(callback_data='admin_delete_stats_back', text='⬅️ Назад'))
    return keyboard


async def totally_delete_stat(stat_id):
    """
    Клавиатура для остаточного удаления статистики.
    :param stat_id: Id авто-рассылки, которое хотим удалить.
    :return: Inline-клавиатура.
    """

    keyboard = types.InlineKeyboardMarkup(row_width=2).add(
        types.InlineKeyboardButton(callback_data=f'admin_totally_delete_stat_{stat_id}',
                                   text='Удалить ❌'),
        types.InlineKeyboardButton(callback_data='admin_totally_deleting_stat_back',
                                   text='⬅️ Назад')
    )
    return keyboard


def autoscripts():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(types.InlineKeyboardButton(callback_data='add_subscribers', text='Добавление подписчиков'))
    keyboard.add(types.InlineKeyboardButton(callback_data='add_balances', text='Добавление статистики и балансов'))
    return keyboard


async def get_admins_second_level():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    sql = ('select a.t_id, COALESCE(u.username, first_name, u.t_id) '
           'from admins a inner join users u on a.t_id = u.t_id where access_level = 2')
    with sq.connect(db_path) as con:
        cur = con.cursor()
        admins = cur.execute(sql).fetchall()
        for user_id, username in admins:
            keyboard.add(
                types.InlineKeyboardButton(callback_data=f'choice_admin_{user_id}', text=username)
            )
    return keyboard