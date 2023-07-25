import json
import requests
import os, boto3
import traceback
client = boto3.client('secretsmanager', region_name=os.environ.get("AWS_REGION", "us-east-1"))


STRIPE_SECRET_ID='infra-membership-api-stripe-secret'

def check_paid_member(netid: str) -> bool:
    url= f'https://membership.acm.illinois.edu/api/v1/checkMembership?netId={netid}'
    response = requests.request("GET", url)
    resp = response.json()
    return resp['isPaidMember']

def create_checkout_session(netid):

    url = "https://api.stripe.com/v1/checkout/sessions"
    
    price = "price_1MUGIRDiGOXU9RuSChPYK6wZ"
    
    payload='success_url=https%3A%2F%2Facm.illinois.edu%2F%23%2Fpaid&line_items%5B0%5D%5Bprice%5D={}&line_items%5B0%5D%5Bquantity%5D=1&mode=payment&cancel_url=https%3A%2F%2Facm.illinois.edu%2F%23%2Fmembership&customer_email={}%40illinois.edu'.format(price, netid)
    keys = json.loads(client.get_secret_value(SecretId=STRIPE_SECRET_ID)['SecretString'])
    stripe_key = keys['STRIPE_KEY_CHECKOUT']

    headers = {
      'Content-Type': 'application/x-www-form-urlencoded',
      'Authorization': 'Bearer {}'.format(stripe_key)
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
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': "No NetID provided"
        }

    if check_paid_member(netid):
        return {
            'statusCode': 400,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': 'The given NetID is already an ACM Paid Memeber.'
        }
    try:
        link = create_checkout_session(netid)
    except Exception:
        print(traceback.format_exc())
        return {
            'statusCode': 500, 'headers': {'Access-Control-Allow-Origin': '*'}, 'body': "Error."
        }
    return {'statusCode': 200, 'headers': {'Access-Control-Allow-Origin': '*'}, 'body': link}