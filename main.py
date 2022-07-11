import json
import os

import requests

from dotenv import load_dotenv



def clear_catalog(url, token):
    headers = {
        'Authorization': token,
    }
    response = requests.get(f"{url}/v2/products", headers=headers)
    response.raise_for_status()
    pizzas = response.json()['data']
    for pizza in pizzas:
        response = requests.delete(
            f"{url}/v2/products/{pizza['id']}",
            headers=headers
        )
    response = requests.get(f"{url}/v2/products", headers=headers)
    response.raise_for_status()


    ### Функция для первоначальной авторизации в магазине
    
def get_auth_token(url, client_id, store_id, client_secret):
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {
        'client_id': client_id,
        'store_id': store_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }
    response = requests.post(
        f'{url}/oauth/access_token',
        data=data,
        headers=headers
    )
    response.raise_for_status()
    auth_info = response.json()
    return (
        f"Bearer {auth_info.get('access_token')}",
        auth_info.get('expires_in')
    )


### Функция для загрузки картинки в магазин

def upload_image(url, token, image_url):
    headers = {
        'Authorization': token,
    }
    file = {
        'file_location': (None, image_url)
    }
    response = requests.post(f"{url}/v2/files", headers=headers, files=file)
    response.raise_for_status()
    return response.json()['data']['id']


### Функция для создания товара в магазине

def create_product(url, token, product_data: dict, product_image=None):
    headers = {
        'Authorization': token,
        'Content-Type': 'application/json'
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
                'amount': product_data['price'],
                'currency': 'RUB',
                'includes_tax': True
            }
        ],
        'status': 'live',
        'commodity_type': 'physical'
            }
    }
    response = requests.post(
        f"{url}/v2/products",
        json=data,
        headers=headers
    )
    response.raise_for_status()

    if not product_image:
        return
    product_id = response.json()['data']['id']
    data = {
        'data': {
            'type': 'main_image',
            'id': product_image
        }
    }
    response = requests.post(
        f"{url}/v2/products/{product_id}/relationships/main-image",
        json=data,
        headers=headers
    )
    response.raise_for_status()


### Функция для создания Flow в магазине

def create_flow(
    url,
    token,
    description,
    slug,
    name
):
    headers = {
        'Authorization': token,
        'Content-Type': 'application/json'
    }
    data = {
        'data': {
            'type': 'flow',
            'name': name,
            'description': description,
            'slug': slug,
            'enabled': True

        }
    }
    response = requests.post(
        f"{url}/v2/flows",
        json=data,
        headers=headers
    )
    response.raise_for_status()
    return response.json()['data']['id']


### Функция для создания либо обновления поля во Flow

def create_or_update_field(
    url,
    token,
    name,
    slug,
    field_type,
    description,
    base_flow
):
    headers = {
        'Authorization': token,
        'Content-Type': 'application/json'
    }
    data = {
        'data': {
            'type': 'field',
            'name': name,
            'slug': slug,
            'field_type': field_type,
            'description': description,
            'required': False,
            'enabled': True,
            'relationships': {
                'flow': {
                    'data': {
                        'type': 'flow'
                    }
                }
            }
        }
    }
    response = requests.get(f"{url}/v2/flows/", headers=headers)
    response.raise_for_status()
    for flow in response.json()['data']:
        if flow['slug'] == base_flow:
            flow_id = flow['id']
            data['data']['relationships']['flow']['data']['id'] = flow_id
            break

    response = requests.get(
        f"{url}/v2/flows/{base_flow}/fields",
        headers=headers
    )
    response.raise_for_status()
    field_id = None
    for field in response.json()['data']:
        if field['slug'] == slug or field['name'] == name:
            field_id = field['id']
    if field_id:
        response = requests.put(
            f"{url}/v2/fields/{field_id}",
            headers=headers,
            json=data
        )
        response.raise_for_status()
        return
    response = requests.post(
        f"{url}/v2/fields",
        headers=headers,
        json=data
    )
    response.raise_for_status()


### Функция для создания записи во Flow

def create_entry(url, token, flow_slug, entry_data: dict):
    data = {
        'data': entry_data
    }
    headers = {
        'Authorization': token,
        'Content-Type': 'application/json'
    }
    data['data']['type'] = 'entry'
    response = requests.post(
        f"{url}/v2/flows/{flow_slug}/entries",
        headers=headers,
        json=data
    )
    response.raise_for_status()
