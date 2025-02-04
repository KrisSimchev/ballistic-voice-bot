import requests
import re
from config import SHOPIFY_API_KEY, SHOPIFY_PASSWORD, SHOPIFY_API_VERSION

API_KEY = SHOPIFY_API_KEY
PASSWORD = SHOPIFY_PASSWORD
API_VERSION = SHOPIFY_API_VERSION
SHOP_NAME = 'ballistic-sport.myshopify.com'

# Base URL for Shopify API requests
BASE_URL = f"https://{API_KEY}:{PASSWORD}@{SHOP_NAME}/admin/api/{API_VERSION}/"

def get_order_details_by_id(order_id):
    order_url = f"{BASE_URL}orders/{order_id}.json"
    fulfillment_url = f"{BASE_URL}orders/{order_id}/fulfillments.json"

    # Fetch order details
    order_response = requests.get(order_url)
    if order_response.status_code == 200:
        order_data = order_response.json().get('order')

        # Fetch fulfillment details
        fulfillment_response = requests.get(fulfillment_url)
        if fulfillment_response.status_code == 200:
            fulfillments = fulfillment_response.json().get('fulfillments', [])
            tracking_info = []
            success_count = 0
            all_items_fulfilled = True

            shipping_lines = order_data.get('shipping_lines', [])
            shipping_method = "No shipping method available"
            if shipping_lines:
                shipping_method = shipping_lines[0].get('title', 'Unknown shipping method')

            # Collect detailed tracking information for each fulfillment

            for fulfillment in fulfillments:
                if 'tracking_number' in fulfillment and fulfillment[
                        'tracking_number']:
                    status = fulfillment.get('status', 'No status available')
                    if status == 'success':
                        success_count += 1
                    if status == 'cancelled':
                        all_items_fulfilled = False

            # Calculate total number of items ordered
            total_items_ordered = sum(
                item['quantity'] for item in order_data.get('line_items', []))

            # Check if all ordered items have a successful fulfillment
            if not all_items_fulfilled:
                all_items_fulfilled = success_count == total_items_ordered

            # Extracting key information from the order
            important_details = {
                "financial_status":
                order_data[
                    "financial_status"],  # e.g., paid, pending, refunded
                "fulfillment_status":
                tracking_info,  # Updated to include detailed fulfillment statuses
                "order_date":
                order_data["created_at"],
                "total_price":
                order_data["total_price"],
                "currency":
                order_data["currency"],
                "customer_email":
                order_data.get("email",
                               "No email provided"),  # Added email field
                "line_items": [{
                    "title": item["title"],
                    "quantity": item["quantity"]
                } for item in order_data["line_items"]],
                "shipping_address":
                order_data.get("shipping_address",
                               "No shipping address provided"),
                "shipping_method": shipping_method,
                "all_items_fulfilled_successfully":
                all_items_fulfilled  # True if all items have been successfully fulfilled
            }
            return important_details
        else:
            return f"Error: Fulfillment data fetch failed with status code {fulfillment_response.status_code}"
    else:
        # Handle errors or non-existent orders
        return f"Error: Order details fetch failed with status code {order_response.status_code}"


def track_order(order_identifier):

    email_pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    phone_pattern = r"^(?:\+[\d\s-]{8,14}\d|0\d{9,14})$"

    if re.match(email_pattern, order_identifier):
        order_ids = get_orders_by_email(order_identifier)
    elif re.match(phone_pattern, order_identifier):
        order_ids = get_orders_by_phone(order_identifier)
    else:
        order_ids = get_orders_by_order_number(order_identifier)

    if isinstance(order_ids, str):
        return order_ids

    order_info = []
    for order_id in order_ids:
        order_details = get_order_details_by_id(order_id)
        order_info.append(order_details)

    return order_info

def get_orders_by_order_number(order_number):
    order_url = f"{BASE_URL}orders.json"
    params = {"name": order_number, "status": "any", "fields": "id"}
    response = requests.get(order_url, params)
    if response.status_code == 200:
        orders = response.json().get('orders', [])
        order_ids = [order['id'] for order in orders]
        return order_ids
    else:
        return f"Error: Status code {response.status_code}"

    
def get_orders_by_phone(phone):
    order_url = f"{BASE_URL}orders.json"
    params = {
        "limit": 250,  # Fetch up to 250 orders at once
        "status": "any",
        "fields": "id,billing_address,created_at"
    }
    matching_orders = []
    while True:
        response = requests.get(order_url, params=params)
        if response.status_code == 200:
            data = response.json()
            orders = data.get('orders', [])
            matching_orders.extend([
                order['id'] for order in orders
                if 'billing_address' in order
                and (order['billing_address'].get('phone') == phone or
                order['billing_address'].get('phone') == '+359' + phone[1:] or
                order['billing_address'].get('phone') == '0' + phone[4:] or
                order['billing_address'].get('phone') == '0' + phone[3:] or
                order['billing_address'].get('phone') == '359' + phone[1:])
            ])

            # Check for pagination
            next_page_info = data.get('next_page_info')
            if next_page_info:
                params['page_info'] = next_page_info
            else:
                break
        else:
            return f"Error: Status code {response.status_code}"
    return matching_orders


def get_orders_by_email(email):
    order_url = f"{BASE_URL}orders.json"
    params = {"email": email, "status": "any", "fields": "id"}
    response = requests.get(order_url, params)
    if response.status_code == 200:
        orders = response.json().get('orders', [])
        order_ids = [order['id'] for order in orders]
        return order_ids
    else:
        return f"Error: Status code {response.status_code}"
    

def escalate_to_human():
    pass