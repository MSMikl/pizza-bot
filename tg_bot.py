import os

from textwrap import dedent

import redis

from dotenv import load_dotenv
from geopy.distance import distance
from more_itertools import chunked

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Filters, Updater, CallbackContext
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler

from shop import (
    get_products, get_auth_token, get_file_link, add_item_to_cart,
    get_cart, delete_item, create_customer,
    fetch_coordinates, get_pizzerias
)


DB = None

def start(update: Update, context: CallbackContext):
    products = get_products(
        context.bot_data['store_token'],
        context.bot_data['base_url']
    )

    product_keyboards = list(chunked([
        [InlineKeyboardButton(
            f"{product['name']} - {product['price'][0]['amount']}р.",
            callback_data=product['id']
        )] for product in products['data']
    ], context.bot_data['pagesize']))

    context.bot_data['product_keyboards'] = product_keyboards

    keyboard = (
        product_keyboards[0] +
        ([[InlineKeyboardButton(
            'Еще',
            callback_data=min(len(product_keyboards) - 1, 1)
        )]] if (len(products['data']) > context.bot_data['pagesize']) else []) +
        [[InlineKeyboardButton('Моя корзина', callback_data='show_cart')]]
    )
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Приветствуем в нашей пиццерии. Хотите заказать пиццу?',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    message = update.effective_message
    context.bot.delete_message(
        chat_id=message.chat_id,
        message_id=message.message_id
    )
    return 'PRODUCT_CHOICE'


def handle_product(update: Update, context: CallbackContext):
    query = update.callback_query
    if query.data == 'show_cart':
        return show_cart(update, context)
    if len(query.data) <= 2:
        page_number = int(query.data)
        keyboard = (
            context.bot_data['product_keyboards'][page_number] +
            [[InlineKeyboardButton(
                'Еще',
                callback_data=(
                    page_number + 1
                    if page_number < len(context.bot_data['product_keyboards']) - 1
                    else 0
                )
            )]] +
            [[InlineKeyboardButton('Моя корзина', callback_data='show_cart')]]
        )
        message = update.effective_message
        context.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=message.text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return 'PRODUCT_CHOICE'

    product = get_products(
        context.bot_data['store_token'],
        context.bot_data['base_url'],
        query.data
    )['data']
    text = dedent(
        f"""
        {product['name']}
        {product['description']}
        Всего {product['price'][0]['amount']} рублей
        Берете?
        """
    )
    keyboard = [
        [InlineKeyboardButton('Положить в корзину', callback_data=product['sku'])],
        [InlineKeyboardButton('Назад', callback_data='back')],
        [InlineKeyboardButton('Моя корзина', callback_data='show_cart')]
    ]
    image_meta = product.get('relationships', {0: 0}).get('main_image')
    if image_meta:
        image = get_file_link(
            context.bot_data['store_token'],
            context.bot_data['base_url'],
            image_meta['data']['id']
        )
        context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=image,
            caption=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    context.bot.delete_message(
        chat_id=query.message.chat_id,
        message_id=query.message.message_id
    )
    return 'HANDLE_MENU'


def handle_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    if query.data == 'back' or query.data == 'continue':
        return start(update, context)
    elif query.data == 'pay':
        return payment(update, context)
    elif query.data == 'show_cart':
        return show_cart(update, context)
    sku = query.data
    cart = add_item_to_cart(
        context.bot_data['store_token'],
        context.bot_data['base_url'],
        cart_id=update.effective_chat.id,
        sku=sku,
        quantity=1
        )
    query.answer(text='Добавили в корзину')

    return 'HANDLE_MENU'


def make_cart_description(cart):
    cart_content_text = '\n    '.join([
        f"{item['name']} {item['quantity']} шт. - {item['unit_price']*item['quantity']}"
        for item in cart.get('items')
    ])
    text = dedent(f"""
    Сейчас у вас в корзине:
    {cart_content_text}
    Общая цена {cart.get('total_price', 0)}
    """)
    return text


def show_cart(update: Update, context: CallbackContext):
    cart = get_cart(
        context.bot_data['store_token'],
        context.bot_data['base_url'],
        update.effective_chat.id
    )
    keyboard = [
        [InlineKeyboardButton(f"Убрать из корзины {item['name']}", callback_data=f"{item['id']}")]
        for item in cart.get('items')
    ]
    keyboard.append([InlineKeyboardButton('Продолжить покупки', callback_data='continue')])
    if cart['total_price']:
        keyboard.append([InlineKeyboardButton('Оплатить', callback_data='pay')])
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=make_cart_description(cart),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.bot.delete_message(
        chat_id=update.callback_query.message.chat_id,
        message_id=update.callback_query.message.message_id
    )
    return 'HANDLE_CART'


def payment(update: Update, context: CallbackContext):
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Пожалуйста, напишите свой адрес для доставки или пришлите геолокацию'
    )
    message = update.effective_message
    context.bot.delete_message(
        chat_id=message.chat_id,
        message_id=message.message_id
    )
    return 'WAITING_LOCATION'


def get_coordinates(update: Update, context: CallbackContext):
    user_reply = update.message
    if user_reply.location:
        lat = user_reply.location.latitude
        lon = user_reply.location.longitude
    else:
        lon, lat = fetch_coordinates(user_reply.text)
    if not lon:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Не удалось определить ваше местоположение. Пожалуйста, введите корректный адрес'
        )
        return 'WAITING_LOCATION'

    pizzerias = get_pizzerias(
        context.bot_data['store_token'],
        context.bot_data['base_url']
        )
    closest_pizzeria = min(pizzerias, key=lambda x: distance((lat, lon), (x.get('latitude'), x.get('longitude'))))
    range = distance((lat, lon), (closest_pizzeria['latitude'], closest_pizzeria['longitude']))
    text = f"Ближайшая к вам пиццерия находится по адресу {closest_pizzeria['address']} на расстоянии {round(range.km, 1)} км"
    if range.km <= 0.5:
        text += '\nОтсюда можем доставить вам пиццу бесплатно. Или вы можете забрать ее самостоятельно'
        keyboard = [
            [InlineKeyboardButton('Самовывоз', callback_data='self_pickup')],
            [InlineKeyboardButton('Доставка', callback_data='delivery')]
        ]
    elif range.km <= 5:
        text += '\nСтоимость доставки до вас от ближайшей пиццерии - 100 рублей'
        keyboard = [
            [InlineKeyboardButton('Самовывоз', callback_data='self_pickup')],
            [InlineKeyboardButton('Доставка', callback_data='delivery')]
        ]
    elif range.km <= 20:
        text += '\nСтоимость доставки до вас от ближайшей пиццерии - 300 рублей'
        keyboard = [
            [InlineKeyboardButton('Самовывоз', callback_data='self_pickup')],
            [InlineKeyboardButton('Доставка', callback_data='delivery')]
        ]
    else:
        text += '\nК сожалению, до вашего адреса пиццу мы доставить не сможем.\nНо вы можете забрать ее самостоятельно'
        keyboard = [
            [InlineKeyboardButton('Самовывоз', callback_data='self_pickup')]
        ]
    context.bot.send_location(
        chat_id=update.effective_chat.id,
        latitude=closest_pizzeria['latitude'],
        longitude=closest_pizzeria['longitude']
    )
    context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    return 'PICKUP_OR_DELIVERY'

    # if not re.fullmatch(r"[^@]+@[^@]+\.[^@]+", user_reply):
    #     return payment(update, context)
    # context.bot.send_message(
    #     chat_id=update.effective_chat.id,
    #     text=f"Вы оставили почту {user_reply}"
    # )
    # create_customer(
    #     context.bot_data['store_token'],
    #     context.bot_data['base_url'],
    #     str(update.effective_chat.id),
    #     user_reply
    # )
    # return 'FINISH'


def handle_cart(update: Update, context: CallbackContext):
    query = update.callback_query
    if query.data == 'continue':
        return start(update, context)
    elif query.data == 'pay':
        return payment(update, context)
    delete_item(
        context.bot_data['store_token'],
        context.bot_data['base_url'],
        update.effective_chat.id,
        query.data
    )
    return show_cart(update, context)


def get_db_connection():
    global DB
    if not DB:
        db_pass = os.getenv('DB_PASS')
        db_host = os.getenv('DB_HOST')
        db_port = int(os.getenv('DB_PORT'))
        DB = redis.Redis(
            host=db_host,
            port=db_port,
            password=db_pass,
            db=0
        )
    return DB


def user_input_handler(update: Update, context: CallbackContext):
    db = get_db_connection()
    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query.data:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return

    if user_reply == '/start':
        user_state = 'START'
    else:
        user_state = db.get(chat_id).decode('UTF-8')

    states_function = {
        'START': start,
        'PRODUCT_CHOICE': handle_product,
        'HANDLE_MENU': handle_menu,
        'HANDLE_CART': handle_cart,
        'WAITING_LOCATION': get_coordinates
    }

    state_handler = states_function[user_state]

    next_state = state_handler(update, context)
    db.set(chat_id, next_state)


def refresh_token(context: CallbackContext):
    context.bot_data['store_token'], context.bot_data['token_lifetime'] = get_auth_token(
        context.bot_data['base_url'],
        context.bot_data['client_id'],
        context.bot_data['client_secret']
    )
    # Каждый раз в случае успешного получения токена убираем предыдущее запланированное задание
    # и создаем новое с новым периодом обновленя
    context.bot_data['refreshing'].schedule_removal()
    context.bot_data['refreshing'] = context.job_queue.run_repeating(
        refresh_token,
        interval=int(context.bot_data['token_lifetime']*0.9)
        )


def main():
    load_dotenv()
    tg_token = os.getenv('TG_TOKEN')
    updater = Updater(tg_token)
    updater.dispatcher.bot_data['base_url'] = 'https://api.moltin.com'
    updater.dispatcher.bot_data['client_id'] = os.getenv('CLIENT_ID')
    updater.dispatcher.bot_data['client_secret'] = os.getenv('CLIENT_SECRET')
    updater.dispatcher.bot_data['pagesize'] = 8  # Размер страницы списка пицц
    # В начале создаем задание по регулярному обновлению токена с дефолтным периодом 120 секунд
    updater.dispatcher.bot_data['refreshing'] = updater.job_queue.run_repeating(
        refresh_token,
        interval=120,
        first=1
        )

    bot_commands = [
        ('start', 'Начать диалог')
    ]
    updater.bot.set_my_commands(bot_commands)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CallbackQueryHandler(user_input_handler))
    dispatcher.add_handler(MessageHandler(Filters.text, user_input_handler))
    dispatcher.add_handler(CommandHandler('start', user_input_handler))
    dispatcher.add_handler(MessageHandler(Filters.location, user_input_handler))
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
