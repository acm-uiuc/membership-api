import json
import requests
import os 
import stripe
import time
import boto3
import traceback

client = boto3.client('secretsmanager', region_name=os.environ.get("AWS_REGION", "us-east-1"))

STRIPE_SECRET_ID='infra-membership-api-stripe-secret'
AAD_SECRET_ID ='infra-membership-api-aad-secret'
MEMBERSHIP_PRICE_ID = 'price_1MUGIRDiGOXU9RuSChPYK6wZ'

def get_secret_value(name: str, client) -> dict:
    return json.loads(client.get_secret_value(SecretId=name)['SecretString'])
    
def get_access_token(aws_secret):
    print("Getting access token")
    url = "https://login.microsoftonline.com/c8d9148f-9a59-4db3-827d-42ea0c2b6e2e/oauth2/v2.0/token"
    body = {
        'client_id': aws_secret['CLIENT_ID'],
        'scope': 'https://graph.microsoft.com/.default',
        'grant_type': 'client_credentials',
        'client_secret': aws_secret['CLIENT_SECRET']
    }
    x = requests.post(url, data=body)
    return x.json()

def get_user_exists(token, email):
    print("Checking if in tenant: ", email)
    emails = email.split("@")
    netid, domain = emails[0], emails[1]
    formatted = "https://graph.microsoft.com/v1.0/users/{}_illinois.edu%23EXT%23@acmillinois.onmicrosoft.com".format(netid, domain)
    headers = {
        "Authorization": "Bearer " + token,
        "Content-type": "application/json"
    }
    x = requests.get(formatted, headers = headers)
    return (x.status_code == 200)

def add_to_group(token, email, i):
    print("Adding to Paid Members Group: ", email)
    emails = email.split("@")
    netid, domain = emails[0], emails[1]
    reqpage = "https://graph.microsoft.com/v1.0/groups/172fd9ee-69f0-4384-9786-41ff1a43cf8e/members/$ref"
    headers = {
        "Authorization": "Bearer " + token,
        "Content-type": "application/json"
    }
    upn = "{}_illinois.edu%23EXT%23@acmillinois.onmicrosoft.com".format(netid)
    reqjson = json.dumps({"@odata.id": "https://graph.microsoft.com/v1.0/users/{}".format(upn)})
    x = requests.post(reqpage, headers = headers, data=reqjson)
    print(x.text)
    if (x.json()['error']['message'] == "One or more added object references already exist for the following modified properties: 'members'."):
        print("Already in tenant: ", email)
        return True
    if (x.status_code >= 400 and i < 11):
        print("User not found, retrying, try: ", i)
        time.sleep(5)
        return add_to_group(token, email, i+1)
        # the user may exist the microservices may just not have synced yet
    elif (x.status_code >= 400):
        print("Could not find the user to add, we're going to error so Stripe tries again.")
        return {
            'statusCode': '500',
            'body': "We tried to add the user to the paid group but couldn't find them, likely microservices issue. Failing so Stripe retries."
        }
    else:
        print("Finally succeeded adding: ", email)
    return (x.status_code == 204 or x.status_code == 200)

def lambda_handler(event, context):
    email = ""
    aws_stripe_secret = get_secret_value(STRIPE_SECRET_ID, client)
    aws_aad_secret = get_secret_value(AAD_SECRET_ID, client)

    secret = aws_stripe_secret['AAD_ENROLL_ENDPOINT_SECRET']
    stripe.api_key = aws_stripe_secret['STRIPE_KEY_CHECKOUT']
    try:
        if event["queryStringParameters"]["test"]:
            print("Using test key")
            secret = aws_stripe_secret['AAD_ENROLL_TEST_ENDPOINT_SECRET']
    except:
        secret = aws_stripe_secret['AAD_ENROLL_ENDPOINT_SECRET']

    try:
        body = event["body"]
        stripe.Webhook.construct_event(body, event['headers']['Stripe-Signature'], secret)
    except Exception:
        print(traceback.format_exc())
        return {
            'statusCode': 421,
            'body': "Invalid Payload."
        }
    line_items = None
    parsedBody = None
    try:
        parsedBody = json.loads(body)
    except:
        return {
            'statusCode': 421,
            'body': "Invalid JSON Payload."
        }  
    try:
        line_items = stripe.checkout.Session.retrieve(
            parsedBody['data']['object']['id'],
            expand=['line_items'],
        ).line_items
    except Exception:
        print(traceback.format_exc())
        return {
            'statusCode': 421,
            'body': "Could not get line items."
        }
    print(line_items)
    try:
        cancel_url = parsedBody['data']['object']['cancel_url']
        success_url = parsedBody['data']['object']['success_url']
        if cancel_url != "https://acm.illinois.edu/#/membership" or success_url != "https://acm.illinois.edu/#/paid":
            return {
                "statusCode": 200,
                "body": "Not a subscription event."
            }
        email = parsedBody['data']['object']['customer_details']['email'].lower()
        print("Inviting: ", email)
    except:
        return {
            "statusCode": 404,
            "body": "No email found."
        }
    url = "https://graph.microsoft.com/v1.0/invitations"
    body = {
        "invitedUserEmailAddress": email,
        "inviteRedirectUrl": "https://acm.illinois.edu"
    }
    token = get_access_token(aws_aad_secret)['access_token']
    if get_user_exists(token, email):
        print("Email already exists, not inviting: ", email)
        try:
            add_to_group(token, email, 0)
        except:
            return {
                'statusCode': '500',
                'body': "Couldn't add to group, failing so Stripe retries."
            }
        print("Done adding existing user: ", email)
        return {
            'statusCode': 201,
            'body': "User already exists in directory. Added to paid members group."
        }
    headers = {
        "Authorization": "Bearer " + token,
        "Content-type": "application/json"
    }
    x = requests.post(url, json = body, headers = headers)
    resp = x.json()
    resp["Status"] = "Done."
    if x.status_code == 201:
        print("Invited : ", email)
        done = False
        try:
            done = add_to_group(token, email, 0)
        except:
            return {
                'statusCode': '500',
                'body': "Couldn't add to group, failing so Stripe retries."
            }
        print("Done: ", done)
        return {
            'statusCode': 200,
            'body': "Done!"
        }
    else:
        print("Error ", x.status_code, "inviting: ", email, " ", json.dumps(resp))
    print("Done adding new user: ", email)
    return {
        'statusCode': 200,
        'body': "Done!"
    }
