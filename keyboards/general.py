from aiogram import types


async def back():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True).add(
        types.KeyboardButton(text='⬅️ Назад')
    )
    return keyboard


async def cancel(custom_buttons=None):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    buttons = []

    if custom_buttons is None:
        buttons.append(types.KeyboardButton(text='Отмена ✖️'))
    else:
        for button in custom_buttons:
            buttons.append(types.KeyboardButton(text=button))
        buttons.append(types.KeyboardButton(text='Отмена ✖️'))

    keyboard.add(*buttons)
    return keyboard


async def accept():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2).add(
        types.KeyboardButton(text='Да ✔️'),
        types.KeyboardButton(text='Нет ✖️')
    )
    return keyboard


