import traceback
import requests
import json
import time
import os
import urllib.parse
MAX_ATTEMPTS = 10
SLEEP_TIME = 2.5

def change_upn(token, user_id, new_upn):
    # Function to change user's UPN
    url = f"https://graph.microsoft.com/v1.0/users/{urllib.parse.quote_plus(user_id)}"
    headers = {
        "Authorization": "Bearer " + token,
        "Content-type": "application/json"
    }
    reqjson = json.dumps({"userPrincipalName": new_upn})
    
    response = requests.patch(url, headers=headers, data=reqjson)
    
    if response.status_code == 204:
        print(f"Successfully changed UPN to: {new_upn}")
        return True
    else:
        print(f"Failed to change UPN for {user_id}. Status code: {response.status_code}, Response: {response.text}", flush=True)
        raise Exception(f"Failed to change UPN for {user_id}.")


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

def wait_for_upn(token: str, netid: str, oneshot: bool = False):
    # Prepare the two UPN formats
    external_upn = f"{netid}_illinois.edu#EXT#@acmillinois.onmicrosoft.com"
    internal_upn = f"{netid}@acm.illinois.edu"
    
    # Prepare the base URL for querying users by UPN
    base_url = "https://graph.microsoft.com/v1.0/users"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    attempt = 0
    max_attempts = 1 if oneshot else MAX_ATTEMPTS

    while attempt < max_attempts:
        try:
            # Query for the external UPN first
            url_external = f"{base_url}/{urllib.parse.quote_plus(external_upn)}"
            response_external = requests.get(url_external, headers=headers)

            # Check if the external UPN exists
            if response_external.status_code == 200:
                print(f"UPN found: {external_upn}")
                return external_upn  # Return the external UPN

            elif response_external.status_code != 404:
                # If the error is not 404, print the error
                print(f"Error querying external UPN: {response_external.status_code}, attempt {attempt + 1}/{max_attempts}")

            # Query for the internal UPN next
            url_internal = f"{base_url}/{urllib.parse.quote_plus(internal_upn)}"
            response_internal = requests.get(url_internal, headers=headers)

            # Check if the internal UPN exists
            if response_internal.status_code == 200:
                print(f"UPN found: {internal_upn}")
                return internal_upn  # Return the internal UPN

            elif response_internal.status_code != 404:
                # If the error is not 404, print the error
                print(f"Error querying internal UPN: {response_internal.status_code}, attempt {attempt + 1}/{max_attempts}")

            if oneshot:
                print(f"Neither UPN found on the one-shot attempt for '{external_upn}' or '{internal_upn}'")
                return None

            # If neither UPN was found, print a retry message
            print(f"Neither UPN found yet for '{external_upn}' or '{internal_upn}', retrying...")

        except requests.exceptions.RequestException as e:
            print(f"Request failed on attempt {attempt + 1}/{max_attempts} with error: {str(e)}")
            print(traceback.format_exc())

        if oneshot:
            return None  # Exit immediately if oneshot is true

        # Exponential backoff before retrying
        attempt += 1
        sleep_time = SLEEP_TIME * (2 ** (attempt - 1))  # Exponential backoff
        time.sleep(sleep_time)

    # If all attempts fail, raise an error
    raise Exception(f"UPN not found for netid '{netid}' after {MAX_ATTEMPTS} attempts.")


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

def add_to_group(token, upn, i=0):
    group_to_add = os.environ.get("PaidMembersEntraGroup")
    reqpage = f"https://graph.microsoft.com/v1.0/groups/{group_to_add}/members/$ref"
    headers = {
        "Authorization": "Bearer " + token,
        "Content-type": "application/json"
    }
    reqjson = json.dumps({"@odata.id": "https://graph.microsoft.com/v1.0/users/{}".format(upn)})
    x = requests.post(reqpage, headers = headers, data=reqjson)
    json_resp = x.json()
    if "One or more added object references already exist for the following modified properties" in json_resp['error']['message']:
        return True
    return (x.status_code == 204 or x.status_code == 200)

def get_user_upn(token, netid):
    # Prepare the external UPN (mailNickname) format
    external_mailnickname = f"{netid}_illinois.edu#EXT#"
    
    # Prepare the base URL and the filter query to search by mailNickname
    base_url = "https://graph.microsoft.com/v1.0/users"
    filter_query = f"?$filter=mailNickname eq '{external_mailnickname}'"
    url = base_url + filter_query

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    attempt = 0
    while attempt < MAX_ATTEMPTS:
        try:
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                # Parse the response JSON
                users_data = response.json()

                # Check if any users were found
                if users_data.get('value'):
                    # Get the UPN of the first matched user
                    user = users_data['value'][0]
                    upn = user.get('userPrincipalName')
                    return upn
                else:
                    print(f"No user found with external UPN: {external_mailnickname}")
                    return None

            else:
                print(f"Failed to query user (status code: {response.status_code}), attempt {attempt + 1}/{MAX_ATTEMPTS}")

        except requests.exceptions.RequestException as e:
            print(f"Request failed on attempt {attempt + 1}/{MAX_ATTEMPTS} with error: {str(e)}")

        # Exponential backoff
        attempt += 1
        sleep_time = SLEEP_TIME * (2 ** (attempt - 1))  # Exponential backoff
        time.sleep(sleep_time)

    # If all attempts fail, raise an error
    raise Exception(f"Failed to retrieve UPN for {external_mailnickname} after {MAX_ATTEMPTS} attempts.")