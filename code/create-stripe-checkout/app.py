import json
import requests
import os


def create_checkout_session(netid):

    url = "https://api.stripe.com/v1/checkout/sessions"
    
    price = "price_1MUGIRDiGOXU9RuSChPYK6wZ"
    
    payload='success_url=https%3A%2F%2Facm.illinois.edu%2F%23%2Fpaid&line_items%5B0%5D%5Bprice%5D={}&line_items%5B0%5D%5Bquantity%5D=1&mode=payment&cancel_url=https%3A%2F%2Facm.illinois.edu%2F%23%2Fmembership&customer_email={}%40illinois.edu'.format(price, netid)
    headers = {
      'Content-Type': 'application/x-www-form-urlencoded',
      'Authorization': 'Bearer {}'.format(os.environ['STRIPE_KEY'])
    }
    
    response = requests.request("POST", url, headers=headers, data=payload)
    if response.status_code != 200:
        raise Exception("Stripe API Error")
    js = response.json()
    return js['url']

def lambda_handler(event, context):
    email = ""
    try:
        netid = event["queryStringParameters"]["netid"]
    except:
        return {
            'statusCode': 404,
            'body': "No NetID provided"
        }
    try:
        link = create_checkout_session(netid)
    except:
        return {
            'statusCode': 500, 'body': "Error."
        }
    return {'statusCode': 200, 'body': link}