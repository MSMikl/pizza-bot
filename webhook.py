import json
import os

import redis
import requests

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from flask import Flask, request

from shop import get_auth_token, get_file_link, get_products_by_category_id, add_item_to_cart, get_cart, delete_item


app = Flask(__name__)

@app.route('/', methods=['GET'])
def verify():
    """
    При верификации вебхука у Facebook он отправит запрос на этот адрес. На него нужно ответить VERIFY_TOKEN.
    """
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == os.environ["FB_VERIFY_TOKEN"]:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200

    return "Hello world", 200

@app.route('/moltin/', methods=['POST'])
def update_menu():
    if not request.headers.get('X-Moltin-Secret-Key') == os.environ['FB_VERIFY_TOKEN']:
        return 'Bad request', 400
    for category, id in app.config['APP_CATEGORIES'].items():
        menu = json.dumps(get_products_by_category_id(app.config['APP_SHOP_TOKEN'], app.config['APP_URL'], id))
    app.config['APP_DATABASE'].set(category, menu)
    return "Menu updated", 201        

def handle_start(sender_id, message_text, postback, app_params):
    send_menu(sender_id, app_params)
    return "MENU_AWAITING"

@app.route('/', methods=['POST'])
def webhook():
    """
    Основной вебхук, на который будут приходить сообщения от Facebook.
    """
    data = request.get_json()
    message_text = None
    postback = None
    if not data["object"] == "page":
        return "ok", 200
    for entry in data["entry"]:
        for messaging_event in entry["messaging"]:
            if messaging_event.get("message"):  # someone sent us a message
                sender_id = messaging_event["sender"]["id"]  # the facebook ID of the person sending you the message
                recipient_id = messaging_event["recipient"]["id"] # the recipient's ID, which should be your page's facebook ID
                message_text = messaging_event['message']["text"] # the message's text
                handle_users_reply(sender_id, message_text, postback, app.config.get_namespace('APP_'))
            elif messaging_event.get('postback'):
                sender_id = messaging_event["sender"]["id"]
                postback = messaging_event.get('postback')

                handle_users_reply(sender_id, message_text, postback, app.config.get_namespace('APP_'))
    return "ok", 200

def handle_menu(sender_id, message_text, postback, app_params):
    if postback:
        if postback['payload'] in app_params['categories'].keys():
            send_menu(sender_id, app_params, postback['payload'])
            return 'MENU_AWAITING'
        elif postback['title'] == 'Корзина':
            cart = get_cart(app_params['shop_token'], app_params['url'], sender_id)
            send_cart(sender_id, cart)
            return 'CART'
        elif postback['title'] == 'В корзину':
            add_item_to_cart(app_params['shop_token'], app_params['url'], sender_id, postback['payload'], 1)
            send_message(sender_id, "Добавили в заказ")
            return 'MENU_AWAITING'
    return 'MENU_AWAITING'

def handle_cart(sender_id, message_text, postback, app_params):
    if not postback:
        return 'CART'
    if postback['title'] == 'Добавить еще одну':
        cart = add_item_to_cart(app_params['shop_token'], app_params['url'], sender_id, postback['payload'], 1)
        send_cart(sender_id, cart)
        return 'CART'
    elif postback['title'] == 'Убрать из заказа':
        cart = delete_item(app_params['shop_token'], app_params['url'], sender_id, postback['payload'])
        send_cart(sender_id, cart)
        return 'CART'
    elif postback['title'] == 'К меню':
        send_menu(sender_id, app_params)
        return 'MENU_AWAITING'
    else:
        return 'CART'

def handle_users_reply(sender_id, message_text, postback, app_params):
    states_functions = {
        'START': handle_start,
        'MENU_AWAITING': handle_menu,
        'CART': handle_cart,
    }
    recorded_state = app_params['database'].get(f"fb_{sender_id}")
    if not recorded_state or recorded_state.decode('utf-8') not in states_functions.keys():
        user_state = "START"
    else:
        user_state = recorded_state.decode('utf-8')
    if message_text == "/start":
        user_state = "START"
    state_handler = states_functions[user_state]
    next_state = state_handler(sender_id, message_text, postback, app_params)
    app_params['database'].set(f"fb_{sender_id}", next_state.encode('utf-8'))

def send_menu(recipient_id, app_params, category='front_page'):
    products = json.loads(app_params['database'].get(category))['data']
    http_proxy = os.environ['HTTP_PROXY']
    proxies = { 
            "http": http_proxy,
            "https": http_proxy,
            }
    params = {"access_token": os.environ["FB_PAGE_ACCESS_TOKEN"]}
    headers = {"Content-Type": "application/json"}
    request_content = {
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": [
                        {
                            "title": "Пиццерия",
                            "image_url": "https://www.clipartkey.com/mpngs/m/74-747872_diner-clipart-lasagna-logo-pizza-vector-png.png",
                            "buttons":
                                [
                                    {
                                        "type": "postback",
                                        "title": "Корзина",
                                        "payload": "Корзина"
                                    },
                                    {
                                        "type": "postback",
                                        "title": "Акции",
                                        "payload": "Акции"                               
                                    },
                                    {
                                        "type": "postback",
                                        "title": "Сделать заказ",
                                        "payload": "Сделать заказ"
                                    }
                                ]
                        }
                    ] + [
                        {
                            "title": f"{product['name']} {product['price'][0]['amount']} р.",
                            "subtitle": product['description'],
                            "image_url": get_file_link(app_params['shop_token'], app_params['url'], product['relationships']['main_image']['data']['id']),
                            "buttons": [
                                {
                                    "type": "postback",
                                    "title": "В корзину",
                                    "payload": product['sku']
                                }
                            ]
                        } for product in products
                    ] + [
                        {
                            "title": "Не нашли пиццу по вкусу?",
                            "subtitle": 'Другие категории здесь',
                            "image_url": "https://primepizza.ru/uploads/position/large_0c07c6fd5c4dcadddaf4a2f1a2c218760b20c396.jpg",
                            "buttons":
                                [
                                    {
                                        "type": "postback",
                                        "title": "Особые",
                                        "payload": 'special'
                                    },
                                    {
                                        "type": "postback",
                                        "title": "Сытные",
                                        "payload": 'nourishing'
                                    },
                                    {
                                        "type": "postback",
                                        "title": "Острые",
                                        "payload": 'spicy'
                                    }
                                ]
                        }                        
                    ]
                }
            }
        }
    }
    response = requests.post("https://graph.facebook.com/v14.0/me/messages", params=params, headers=headers, json=request_content, proxies=proxies)
    response.raise_for_status()   

def send_cart(recipient_id, cart):
    http_proxy = os.environ['HTTP_PROXY']
    proxies = { 
            "http": http_proxy,
            "https": http_proxy,
            }
    params = {"access_token": os.environ["FB_PAGE_ACCESS_TOKEN"]}
    headers = {"Content-Type": "application/json"}
    request_content = {
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": [
                        {
                            "title": "Ваша корзина",
                            "image_url": "https://postium.ru/wp-content/uploads/2018/08/idealnaya-korzina-internet-magazina-1068x713.jpg",
                            "buttons":
                                [
                                    {
                                        "type": "postback",
                                        "title": "Самомвывоз",
                                        "payload": "Самовывоз"
                                    },
                                    {
                                        "type": "postback",
                                        "title": "Доставка",
                                        "payload": "Доставка"                               
                                    },
                                    {
                                        "type": "postback",
                                        "title": "К меню",
                                        "payload": "К меню"
                                    }
                                ]
                        }
                    ] + [
                        {
                            "title": f"{item['name']} - {item['quantity']} шт.",
                            'subtitle': item.get('description'),
                            'image_url': item.get('image'),
                            'buttons': [
                                {
                                    "type": "postback",
                                    "title": "Добавить еще одну",
                                    "payload": item['sku']
                                },
                                {
                                    "type": "postback",
                                    "title": "Убрать из заказа",
                                    "payload": item['id']
                                }
                            ]
                        } for item in cart['items']
                    ]
                }
            }
        }
    }
    response = requests.post("https://graph.facebook.com/v14.0/me/messages", params=params, headers=headers, json=request_content, proxies=proxies)
    response.raise_for_status()

def send_message(recipient_id, message_text):
    http_proxy = os.environ['HTTP_PROXY']
    proxies = { 
            "http": http_proxy,
            "https": http_proxy,
            }
    params = {"access_token": os.environ["FB_PAGE_ACCESS_TOKEN"]}
    headers = {"Content-Type": "application/json"}
    request_content = {
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": message_text
        }
    }
    response = requests.post("https://graph.facebook.com/v14.0/me/messages", params=params, headers=headers, json=request_content, proxies=proxies)
    response.raise_for_status()

def set_moltin_webhook(url, shop_token):
    headers = {
        'Authorization': shop_token,
        'Content-Type': 'application/json'
    }
    data = {
        'data': {
            "type": "integration",
            "name": "Product change notification",
            "description": "Send message about menu updating",
            "enabled": True,
            "observes": [
                "product.created",
                'product.updated',
                'product.deleted',
            ],
            "integration_type": "webhook",
            "configuration": {
                "url": "https://fb.michalbl4.ru/moltin/",
                "secret_key": os.environ['FB_VERIFY_TOKEN'],
            }
        }
    }
    response = requests.post(
        f"{url}/v2/integrations",
        headers=headers,
        json=data,
    )
    response.raise_for_status()

def refresh_token():
    app.config['APP_SHOP_TOKEN'], _ = get_auth_token(app.config['APP_URL'], os.getenv('CLIENT_ID'), os.getenv('CLIENT_SECRET'))


def main():
    load_dotenv()
    url = 'https://api.moltin.com'

    shop_token, _ = get_auth_token(url, os.getenv('CLIENT_ID'), os.getenv('CLIENT_SECRET'))
    categories = {
        'front_page': '853639e2-b8de-41f8-99c5-cf26496e96f9',
        'spicy': 'd83ce07a-d60c-44f6-936b-729339db5dab',
        'nourishing': '2fcce823-9baa-4b7f-81dc-0030375ae27e',
        'special': 'eb6b470c-91e9-49df-9e00-95826bdffe3f',    
    }
    database = redis.Redis(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        password=os.getenv('DB_PASS'),
        db=0    
    )
    for category, id in categories.items():
        menu = json.dumps(get_products_by_category_id(shop_token, url, id))
        database.set(category, menu)
    set_moltin_webhook(url, shop_token)
    
    app.config.update(
        APP_SHOP_TOKEN = shop_token,
        APP_URL = url,
        APP_CATEGORIES = categories,
        APP_DATABASE = database,
    )

    scheduler = BackgroundScheduler()
    scheduler.add_job(refresh_token, trigger="interval", seconds=3600)

    host = os.environ['FLASK_HOST']
    port = os.environ['FLASK_PORT']
    app.run(host=host, port=port)


if __name__ == '__main__':
    main()
