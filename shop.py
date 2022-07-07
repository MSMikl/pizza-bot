import requests


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
    return extract_data_from_cart(response.json())


def delete_item(token, url, cart_id, item_id):
    headers = {
        'Authorization': token
    }
    response = requests.delete(
        f"{url}/v2/carts/{cart_id}/items/{item_id}",
        headers=headers,
        )
    response.raise_for_status()
    return extract_data_from_cart(response.json())


def get_cart(token, url, cart_id):
    headers = {
        'Authorization': token
    }
    response = requests.get(
        f'{url}/v2/carts/{cart_id}/items',
        headers=headers
    )
    response.raise_for_status()
    return extract_data_from_cart(response.json())


def extract_data_from_cart(full_cart_data):
    result = {
        'items': [
            {
                'name': item['name'],
                'quantity': item['quantity'],
                'unit_price': item['unit_price']['amount'],
                'id': item['id']
            }
            for item in full_cart_data['data']
        ],
        'total_price': full_cart_data['meta']['display_price']['with_tax']['amount']
    }
    return result


def create_customer(token, url, user_name, user_email):
    headers = {
        'Authorization': token,
        'Content-Type': 'application/json'
    }
    data = {
        'data': {
            'type': 'customer',
            'name': user_name,
            'email': user_email
        }
    }
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
    print(response.text)
