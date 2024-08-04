import requests
import json
import time
import os
MAX_ATTEMPTS = 20
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
    print(x.text)
    try:
        json_resp = x.json()
    except Exception:
        print(f"Failed to parse JSON response, trying one more time: {x.text}", flush=True)
        return add_to_group(token, email, MAX_ATTEMPTS)
    if (json_resp['error']['message'] == "One or more added object references already exist for the following modified properties: 'members'."):
        print("Already in tenant: ", email)
        return True
    if (x.status_code >= 400 and i < MAX_ATTEMPTS):
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