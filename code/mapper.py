import json
import boto3, os, asyncio, time
from graph import GraphAPI

client = boto3.client('secretsmanager', region_name=os.environ.get("AWS_REGION", "us-east-1"))
dynamo = boto3.resource('dynamodb', region_name=os.environ.get("AWS_REGION", "us-east-1"))

TABLE_NAME='infra-membership-api-cache'
EXTERNAL_LIST_TABLE_NAME = 'infra-membership-api-external-lists'
AAD_SECRET_ID='infra-membership-api-aad-secret'
TOKEN_VALIDITY_SECONDS = 3590 # it's really 3600 but we save them slightly shorter

table = dynamo.Table(TABLE_NAME)
list_table = dynamo.Table(EXTERNAL_LIST_TABLE_NAME)

def healthzHandler(context, queryParams):
    return {
        "statusCode": 200,
        "body": "UP"
    }
def notImplemented(context, queryParams):
    return {
        "statusCode": 404,
        "body": "Method not implemented."
    }
def serverError(message):
    return {
        "statusCode": 500,
        "body": f"An error occurred - {message}"
    }
def badRequest(message):
    return {
        "statusCode": 400,
        "body": f"Bad request - {message}"
    }

def getPaidMembership(context, queryParams) -> dict:
    netid = queryParams['netId'].lower()
    aad_secret = json.loads(client.get_secret_value(SecretId=AAD_SECRET_ID)['SecretString'])
    gapi = GraphAPI(aad_secret['CLIENT_ID'], aad_secret['CLIENT_SECRET'])
    loop = asyncio.get_event_loop()
    paid = loop.run_until_complete(gapi.isPaidMember(netid))
    return {
        'statusCode': 200,
        'headers': {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": True
        },
        'body': json.dumps({
            "netId": netid,
            "isPaidMember": paid
        })
    }
def getExternalMembership(context, queryParams) -> dict:
    netid = queryParams['netId'].lower()
    check_list = queryParams['list'].lower()
    member = False
    try:
        response = list_table.get_item(
            Key={
                'netid_list': f"{netid}_{check_list}"
            } 
        )
        print(response)
        if 'Item' in response:
            member = True
    except KeyError:
        member = False
    return {
        'statusCode': 200,
        'headers': {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": True
        },
        'body': json.dumps({
            "netId": netid,
            "list": check_list,
            "isPaidMember": member
        })
    }
def getUI(context, queryParam) -> dict:
    with open("index.html", "r") as file:
        return {
            "statusCode": 200,
            "headers": {
                'Content-Type': 'text/html'
            },
            'body': file.read()
        }

find_handler = {
    "GET": {
        "/api/v1/healthz": healthzHandler,
        "/api/v1/checkMembership": getPaidMembership,
        "/api/v1/checkExternalMembership": getExternalMembership,
        "/": getUI,
    }
}

def execute(method: str, path: str, queryParams: dict, context: dict) -> dict:
    if method not in find_handler or path not in find_handler[method]:
        print(f"ERROR: No handler found for method {method} and path {path}.")
        return notImplemented(context, queryParams)
    func: function = find_handler[method][path]
    return func(context, queryParams)

