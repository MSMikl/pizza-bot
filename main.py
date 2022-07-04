import json
import os

import requests

from dotenv import load_dotenv


def main():
    load_dotenv()
    client_id = os.getenv('CLIENT_ID')
    base_url = 'https://api.moltin.com'
    with open('addresses.json', 'r', encoding='UTF-8') as file:
        addresses = json.load(file)
    with open('menu.json', 'r', encoding='UTF-8') as file:
        menu = json.load(file)
    token, _ = get_auth_token(base_url, client_id)
    create_product(base_url, token, menu[0])
    upload_image(base_url, token, menu[0]['product_image']['url'])


def get_auth_token(url, client_id):
    data = {
        'client_id': client_id,
        'grant_type': 'implicit'
    }
    response = requests.post(f'{url}/oauth/access_token', data=data)
    response.raise_for_status()
    auth_info = response.json()
    return (
        f"Bearer {auth_info.get('access_token')}",
        auth_info.get('expires_in')
    )


def upload_image(url, token, image_url):
    headers = {
        'Authorization': token
    }
    file = {
        'file_location': image_url
    }
    response = requests.post(f"{url}/v2/files", headers=headers, files=file)
    print(response.text)


def create_product(url, token, product_data: dict):
    headers = {
        'Authorization': token,
        # 'Content-Type': 'application/json'
    }
    data = {'data': {
        'type': 'product',
        'name': product_data['name'],
        'slug': f"pizza_{product_data['id']}",
        'sku': str(10000 + int(product_data['id'])),
        'manage_stock': False,
        'description': product_data['description'],
        'price': [
            {
                'price_amount': product_data['price'],
                'price_currency': 'USD'
            }
        ],
        'status': 'live',
        'commodity_type': 'physical'
            }
    }
    response = requests.get(f"{url}/v2/products", headers=headers)
    print(response.text)
    # Вот здесь вылезает ошибка - неавторизованный реквест
    response = requests.post(f"{url}/v2/products", json=data, headers=headers)
    print(response.text)


if __name__ == '__main__':
    main()
