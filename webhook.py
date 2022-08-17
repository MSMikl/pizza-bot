import os
import sys
import json
from datetime import datetime

import requests
from dotenv import load_dotenv
from flask import Flask, request

from shop import get_auth_token, get_products, get_file_link

load_dotenv()
URL = 'https://api.moltin.com'
SHOP_TOKEN, _ = get_auth_token(URL, os.getenv('CLIENT_ID'), os.getenv('CLIENT_SECRET'))
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


@app.route('/', methods=['POST'])
def webhook():
    """
    Основной вебхук, на который будут приходить сообщения от Facebook.
    """
    data = request.get_json()
    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                if messaging_event.get("message"):  # someone sent us a message
                    sender_id = messaging_event["sender"]["id"]  # the facebook ID of the person sending you the message
                    recipient_id = messaging_event["recipient"]["id"] # the recipient's ID, which should be your page's facebook ID
                    message_text = messaging_event["message"]["text"] # the message's text
                    send_menu(sender_id)
    return "ok", 200


def send_menu(recipient_id):
    products = get_products(SHOP_TOKEN, URL)['data'][:5]
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
                            "title": product['name'],
                            "subtitle": product['description'],
                            "image_url": get_file_link(SHOP_TOKEN, URL, product['relationships']['main_image']['data']['id']),
                            "buttons": [
                                {
                                    "type": "postback",
                                    "title": f"{product['price'][0]['amount']} р.",
                                    "payload": "DEVELOPER_DEFINED_PAYLOAD"
                                }
                            ]
                        } for product in products
                    ]
                }
            }
        }
    }
    response = requests.post("https://graph.facebook.com/v14.0/me/messages", params=params, headers=headers, json=request_content, proxies=proxies)
    print(response.json())
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


if __name__ == '__main__':
    host = os.environ['FLASK_HOST']
    port = os.environ['FLASK_PORT']
    app.run(host=host, port=port)
