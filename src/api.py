import datetime
import trace
import traceback
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.event_handler import (
    APIGatewayRestResolver,
    CORSConfig,
    Response,
    content_types,
)
import os
import json

from flask_migrate import current
from aad import add_to_group, add_to_tenant, get_entra_access_token, get_user_exists
from utils.general import create_checkout_session, get_run_environment, get_logger, configure_request_id, check_paid_member, get_parameter_from_sm
from utils.graph import GraphAPI
import boto3
import stripe
RUN_ENV = get_run_environment()
logger = get_logger()

client = boto3.client('secretsmanager', region_name=os.environ.get("AWS_REGION", "us-east-1"))
dynamo = boto3.resource('dynamodb', region_name=os.environ.get("AWS_REGION", "us-east-1"))

TOKEN_VALIDITY_SECONDS = 3590 # it's really 3600 but we save them slightly shorter
TABLE_NAME='infra-membership-api-cache'
EXTERNAL_LIST_TABLE_NAME = 'infra-membership-api-external-lists'
PROVISIONING_LOGGING_TABLE = 'infra-membership-api-provisioning-logs'
SECRET_ID='infra-membership-api-secrets'
MEMBERSHIP_PRODUCT_ID = os.environ.get("MembershipProductId")

global_credentials = get_parameter_from_sm(client, SECRET_ID)

table = dynamo.Table(TABLE_NAME) # type: ignore
list_table = dynamo.Table(EXTERNAL_LIST_TABLE_NAME) # type: ignore
logging_table = dynamo.Table(PROVISIONING_LOGGING_TABLE) # type: ignore

extra_origins = os.environ.get("ValidCorsOrigins", "https://acm.illinois.edu").split(",")

cors_config = CORSConfig(
    allow_origin="https://acm.illinois.edu",
    extra_origins=extra_origins,
    max_age=300,
    allow_credentials=True,
    allow_headers=["authorization"],
)
app = APIGatewayRestResolver(cors=cors_config)

@app.get("/")
def get_ui():
    with open("index.html", "r") as file:
        return Response(
            status_code=200,
            content_type=content_types.TEXT_HTML,
            body=file.read()
        )

@app.get("/api/v1/healthz")
def healthz():
    return Response(
        status_code=200,
        content_type=content_types.APPLICATION_JSON,
        body={"message": "UP"},
    )

@app.get("/api/v1/checkMembership")
def check_membership():
    netid = (app.current_event.get_query_string_value(name="netId", default_value="") or "").lower()
    if netid == "":
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body={
                "message": "No NetID provided."
            },
        )
    gapi = GraphAPI(global_credentials['AAD_CLIENT_ID'], global_credentials['AAD_CLIENT_SECRET'])
    is_paid_member = check_paid_member(gapi, netid)
    current_timestamp = datetime.datetime.now().isoformat()
    if is_paid_member:
        # populate our cache since lot of our netids aren't in it
        condition = "attribute_not_exists(email)"
        # Put the item in the table only if the email does not already exist
        try:
            logging_table.put_item(
                Item={'email': f"{netid}@illinois.edu", "inserted_at": current_timestamp, "inserted_by": "membership-api-query"},
                ConditionExpression=condition
            )
        except Exception:
            print(traceback.format_exc())
    return Response(
        status_code=200,
        content_type=content_types.APPLICATION_JSON,
        body={
            "netId": netid,
            "isPaidMember": is_paid_member
        },
    )

@app.get("/api/v1/checkExternalMembership")
def check_external_membership():
    netid = (app.current_event.get_query_string_value(name="netId", default_value="") or "").lower()
    check_list = (app.current_event.get_query_string_value(name="list", default_value="") or "").lower()
    if netid == "":
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body={
                "message": "No NetID provided."
            },
        )
    if check_list == "":
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body={
                "message": "No check list provided."
            },
        )
    member = False
    try:
        response = list_table.get_item(
            Key={
                'netid_list': f"{netid}_{check_list}"
            } 
        )
        if 'Item' in response:
            member = True
    except KeyError:
        member = False
    return Response(
        status_code=200,
        content_type=content_types.APPLICATION_JSON,
        body={
            "netId": netid,
            "list": check_list,
            "isPaidMember": member
        },
    )

@app.get("/api/v1/checkout/session")
def get_checkout_session():
    netid = (app.current_event.get_query_string_value(name="netid", default_value="") or "").lower()
    if netid == "":
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body={"message": "No NetID provided"}
        )
    gapi = GraphAPI(global_credentials['AAD_CLIENT_ID'], global_credentials['AAD_CLIENT_SECRET'])
    if check_paid_member(gapi, netid):
        return Response(
            status_code=409,
            content_type=content_types.APPLICATION_JSON,
            body={"message": f"{netid} is already a paid member."}
        )
    stripe_key = global_credentials['STRIPE_KEY_CHECKOUT']
    link = create_checkout_session(netid, stripe_key)
    return Response(
        status_code=200,
        content_type=content_types.TEXT_PLAIN,
        body=link
    )

@app.post("/api/v1/provisioning/member")
def provision_member():
    secret = global_credentials['AAD_ENROLL_ENDPOINT_SECRET']
    stripe.api_key = global_credentials['STRIPE_KEY_CHECKOUT']
    body = app.current_event['body']
    try:
        stripe.Webhook.construct_event(body, app.current_event['headers']['Stripe-Signature'], secret)
    except Exception:
        logger.info(traceback.format_exc())
        return Response(
            status_code=421,
            content_type=content_types.APPLICATION_JSON,
            body={"message": "Invalid payload."}
        )
    line_items = {}
    parsed_body: dict = app.current_event.json_body or {}
    try:
        line_items = stripe.checkout.Session.retrieve(
            parsed_body['data']['object']['id'],
            expand=['line_items'],
        ).line_items
        if not line_items:
            raise ValueError("line_items is None")
    except Exception:
        print(traceback.format_exc())
        return Response(
            status_code=421,
            content_type=content_types.APPLICATION_JSON,
            body={"message": "Could not get line items for transaction."}
        )

    isMembershipEvent = False
    try:
        for item in line_items['data']:
            if item['price']['product'] == MEMBERSHIP_PRODUCT_ID: # type: ignore
                isMembershipEvent = True
        if isMembershipEvent:
            logger.info("Found Membership Event")
            email = parsed_body['data']['object']['customer_details']['email'].lower()
            logger.info("Found subscriber: " + email)
        else:
            return Response(
                status_code=200,
                content_type=content_types.APPLICATION_JSON,
                body={"message": "Not a membership event."}
            )
    except Exception:
        logger.error("Error getting line items: " + traceback.format_exc())
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body={"message": "No email in purchase payload."}
        )
    entra_token = get_entra_access_token(global_credentials)['access_token']
    response_object = {}
    current_timestamp = datetime.datetime.now().isoformat()
    if get_user_exists(entra_token, email):
        logger.info("Email already exists, not inviting: " + email)
        response_object = {"message": f"Added (without inviting) {email} to paid members group"}
    else:
        logger.info("Inviting " + email + " to tenant")
        try:
            add_to_tenant(entra_token, email)
        except Exception:
            logger.error(f"Error inviting {email} to tenant: " + traceback.format_exc())
            return Response(
                status_code=500,
                content_type=content_types.APPLICATION_JSON,
                body={"message": "Could not invite to tenant, erroring so Stripe retries the event."}
            )
    try:
        logger.info("Adding to Paid Members Group: " + email)
        add_to_group(entra_token, email)
        response_object = {"message": f"Added and invited {email} to paid members group"}
    except Exception:
        logger.error(f"Error adding {email} to paid members group: " + traceback.format_exc())
        return Response(
            status_code=500,
            content_type=content_types.APPLICATION_JSON,
            body={"message": "Could not add to group, erroring so Stripe retries the event."}
        )
    try:
        logging_table.put_item(
            Item={
                'email': email,
                'inserted_at': current_timestamp,
                'inserted_by': 'membership-api-provisioned'
            } 
        )
    except Exception:
        logger.warn(f"Failed to log purchase to dynamo for email {email}: " + traceback.format_exc())
    response_object['inserted_at'] = current_timestamp
    return Response(
        status_code=201,
        content_type=content_types.APPLICATION_JSON,
        body=response_object
    )





# Templating, ignore
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    ctx = event["requestContext"]
    request_id = ctx["requestId"]
    configure_request_id(request_id)
    if "queryStringParameters" in event and event["queryStringParameters"] is not None:
        full_path = f"{ctx['path']}?" + "&".join(
            [f"{key}={value}" for key, value in event["queryStringParameters"].items()]
        )
    else:
        full_path = ctx["path"]
    try:
        username = event["requestContext"]["authorizer"]["username"]
    except Exception:
        username = "public@acm.illinois.edu"
    log_string = f"REQUEST LOG - START - [{ctx['requestId']}] {ctx['identity']['sourceIp']}: {({username})} - [{ctx['requestTime']}] \"{ctx['httpMethod']} {full_path} {ctx['protocol']}\" {ctx['identity']['userAgent']}"
    print(log_string, flush=True)
    try:
        rval = app.resolve(event, context)
        status_code = rval["statusCode"]
    except Exception:
        logger.info(f"An error occured and bubbled up: {traceback.format_exc()}")
        rval = {
            "statusCode": 502,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"message": "An internal server error occurred."}),
        }
        status_code = 502
    log_string = f"REQUEST LOG - FINISH - [{ctx['requestId']} finished with status code {status_code}"
    print(log_string, flush=True)
    return rval