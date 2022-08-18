import os

import requests


def get_auth_token(url, client_id, client_secret):
    data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }
    response = requests.post(f'{url}/oauth/access_token', data=data)
    response.raise_for_status()
    auth_info = response.json()
    return (
        f"Bearer {auth_info.get('access_token')}",
        auth_info.get('expires_in')
    )


def get_products(token, url, id=None):
    headers = {
        'Authorization': token
    }
    response = requests.get(
        f'{url}/v2/products/{id if id else ""}',
        headers=headers
    )
    response.raise_for_status()
    return response.json()


def get_products_by_category_id(token, url, category_id):
    headers = {
        'Authorization': token
    }
    params = {
        'filter': f'eq(category.id,{category_id})'
    }
    response = requests.get(
        f'{url}/v2/products/',
        headers=headers,
        params=params
    )
    response.raise_for_status()
    return response.json()
    


def get_file_link(token, url, id):
    headers = {
        'Authorization': token
    }
    response = requests.get(
        f"{url}/v2/files/{id}",
        headers=headers
    )
    response.raise_for_status()
    return response.json().get('data', {0: 0}).get('link', {0: 0}).get('href')


def add_item_to_cart(token, url, cart_id, sku, quantity):
    headers = {
        'Authorization': token,
        'Content-Type': 'application/json'
    }
    data = {
        'data': {
            'sku': sku,
            'quantity': quantity,
            "type": "cart_item"
        }
    }
    response = requests.post(
        f'{url}/v2/carts/{cart_id}/items',
        headers=headers,
        json=data
    )
    response.raise_for_status()
    cart = response.json()
    selected_data = {
        'items': [
            {
                'name': item['name'],
                'quantity': item['quantity'],
                'unit_price': item['unit_price']['amount'],
                'id': item['id']
            }
            for item in cart['data']
        ],
        'total_price': cart['meta']['display_price']['with_tax']['amount']
    }
    
    return selected_data


def delete_item(token, url, cart_id, item_id):
    headers = {
        'Authorization': token
    }
    response = requests.delete(
        f"{url}/v2/carts/{cart_id}/items/{item_id}",
        headers=headers,
        )
    response.raise_for_status()
    cart = response.json()
    selected_data = {
        'items': [
            {
                'name': item['name'],
                'quantity': item['quantity'],
                'unit_price': item['unit_price']['amount'],
                'id': item['id']
            }
            for item in cart['data']
        ],
        'total_price': cart['meta']['display_price']['with_tax']['amount']
    }    
    return selected_data


def get_cart(token, url, cart_id):
    headers = {
        'Authorization': token
    }
    response = requests.get(
        f'{url}/v2/carts/{cart_id}/items',
        headers=headers
    )
    response.raise_for_status()
    cart = response.json()
    selected_data = {
        'items': [
            {
                'name': item['name'],
                'quantity': item['quantity'],
                'unit_price': item['unit_price']['amount'],
                'id': item['id']
            }
            for item in cart['data']
        ],
        'total_price': cart['meta']['display_price']['with_tax']['amount']
    }    
    return selected_data


def create_or_update_customer(
    token,
    url,
    user_name,
    user_email=None,
    address=None,
    latitude=None,
    longitude=None
):
    headers = {
        'Authorization': token,
        'Content-Type': 'application/json'
    }
    data = {
        'data': {
            'type': 'customer',
            'name': user_name,
            'email': (user_email if user_email else f"{user_name}@email.com"),
            'latitude': latitude,
            'longitude': longitude,
            'address': address
        }
    }
    response = requests.get(f"{url}/v2/customers", headers=headers)
    response.raise_for_status()
    for customer in response.json()['data']:
        if customer.get('name') == user_name:
            response = requests.put(
                f"{url}/v2/customers/{customer['id']}",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            return response.json()
    response = requests.post(f"{url}/v2/customers", headers=headers, json=data)
    response.raise_for_status()
    return response.json()


def create_product(token, url, product_data: dict):
    headers = {
        "Authorization": token,
        'Content-Type': 'application/json'
    }
    data = product_data
    response = requests.post(f"{url}/v2/products", headers=headers, json=data)
    response.raise_for_status()
    return response.json()


def get_pizzerias(token, url):
    headers = {
        "Authorization": token
    }
    response = requests.get(
        f"{url}/v2/flows/pizzeria/entries",
        headers=headers
    )
    response.raise_for_status()
    return response.json().get('data')


def fetch_coordinates(address):
    apikey = os.getenv('YANDEX_API_KEY')
    base_url = "https://geocode-maps.yandex.ru/1.x"
    response = requests.get(base_url, params={
        "geocode": address,
        "apikey": apikey,
        "format": "json",
    })
    response.raise_for_status()
    found_places = response.json()['response']['GeoObjectCollection']['featureMember']

    if not found_places:
        return None, None

    most_relevant = found_places[0]
    lon, lat = most_relevant['GeoObject']['Point']['pos'].split(" ")
    return lon, lat
