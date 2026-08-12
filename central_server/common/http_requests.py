from common.response_fields import ERROR
import requests


def make_request(method, url, endpoint, *, params=None, json_data=None, headers=None):
    """
    Performs a HTTP request to the database server.

    Args:
        method (str): HTTP method ('GET', 'POST', etc.).
        endpoint (str): API path (without base URL).
        params (dict, optional): Query parameters.
        json_data (dict, optional): JSON data to send in request body.

    Returns:
        tuple: (response JSON as dict, error as dict if present)
    """
    url = f'{url}/{endpoint}'
    try:
        response = requests.request(method, url, params=params, json=json_data, headers=headers, timeout=5)

        try:
            response_data = response.json()
        except ValueError:
            return {ERROR: f'Invalid JSON response from {url}'}

        return response_data

    except requests.RequestException as e:
        print(f'Request exception: {e}')
        return {ERROR: f'Request exception in {method} action to {url}'}

    
def get_request(url, endpoint, params=None):
    """
    Performs a GET request to the database server.

    Args:
        endpoint (str): API path.
        params (dict, optional): Params to include in query string.

    Returns:
        tuple: (JSON response as dict, error as dict if present)
    """
    return make_request('GET', url, endpoint, params=params)


def post_request(url, endpoint, json_data):
    """
    Performs a POST request to the database server.

    Args:
        endpoint (str): API path.
        json_data (dict): JSON data to send.

    Returns:
        tuple: (JSON response as dict, error as dict if present)
    """
    return make_request('POST', url, endpoint, json_data=json_data)