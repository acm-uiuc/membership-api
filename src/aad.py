import requests
import json
import time
import os
MAX_ATTEMPTS = 20
SLEEP_TIME = 2.5
def get_entra_access_token(aws_secret):
    print("Getting access token")
    url = "https://login.microsoftonline.com/c8d9148f-9a59-4db3-827d-42ea0c2b6e2e/oauth2/v2.0/token"
    body = {
        'client_id': aws_secret['AAD_CLIENT_ID'],
        'scope': 'https://graph.microsoft.com/.default',
        'grant_type': 'client_credentials',
        'client_secret': aws_secret['AAD_CLIENT_SECRET']
    }
    x = requests.post(url, data=body)
    return x.json()

def get_user_exists(token, email):
    print("Checking if in tenant: ", email)
    emails = email.split("@")
    netid = emails[0]
    formatted = "https://graph.microsoft.com/v1.0/users/{}_illinois.edu%23EXT%23@acmillinois.onmicrosoft.com".format(netid)
    headers = {
        "Authorization": "Bearer " + token,
        "Content-type": "application/json"
    }
    x = requests.get(formatted, headers = headers)
    return (x.status_code == 200)

def add_to_tenant(token: str, email: str):
    url = "https://graph.microsoft.com/v1.0/invitations"
    body = {
        "invitedUserEmailAddress": email,
        "inviteRedirectUrl": "https://acm.illinois.edu"
    }
    headers = {
        "Authorization": "Bearer " + token,
        "Content-type": "application/json"
    }
    response = requests.post(url, json=body, headers=headers)
    return response.status_code >= 200 and response.status_code <= 299

def add_to_group(token, email, i=0):
    netid = email.split("@")[0]
    group_to_add = os.environ.get("PaidMembersEntraGroup")
    reqpage = f"https://graph.microsoft.com/v1.0/groups/{group_to_add}/members/$ref"
    headers = {
        "Authorization": "Bearer " + token,
        "Content-type": "application/json"
    }
    upn = "{}_illinois.edu%23EXT%23@acmillinois.onmicrosoft.com".format(netid)
    reqjson = json.dumps({"@odata.id": "https://graph.microsoft.com/v1.0/users/{}".format(upn)})
    x = requests.post(reqpage, headers = headers, data=reqjson)
    try:
        json_resp = x.json()
    except Exception as e:
        # JSON error usually means that its done, avoid looping on MAX_ATTEMPTS
        if i != MAX_ATTEMPTS:
            return add_to_group(token, email, MAX_ATTEMPTS)
        else:
            raise e
    if (json_resp['error']['message'] == "One or more added object references already exist for the following modified properties: 'members'."):
        if i == 0:
            print("Already in Paid Members group: ", email)
        else:
            print("Added to Paid Members group: ", email)
        return True
    if (x.status_code >= 400 and i < MAX_ATTEMPTS):
        print(f"User not found, retrying in {SLEEP_TIME} seconds, try: ", i)
        time.sleep(SLEEP_TIME)
        return add_to_group(token, email, i+1)
        # the user may exist the microservices may just not have synced yet
    elif (x.status_code >= 400):
        raise ValueError("Could not find the user to add, we're going to error so Stripe tries again.")
    return (x.status_code == 204 or x.status_code == 200)