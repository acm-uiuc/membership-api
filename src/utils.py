import sys
import logging
import os
import json
from typing import Dict
import requests
import asyncio

from graph import GraphAPI

# Get a JSON secret from AWS Secrets Manager
def get_parameter_from_sm(sm_client, parameter_name) -> Dict[str, str | int]:
    try:
        # Retrieve the parameter
        response = sm_client.get_secret_value(SecretId=parameter_name)
        # Get the parameter value
        parameter_value = response["SecretString"]
        # Parse the parameter value into a dictionary
        parameter_dict = json.loads(parameter_value)

        return parameter_dict

    except sm_client.exceptions.ResourceNotFoundException:
        print(f'Parameter "{parameter_name}" not found.', flush=True)
        return {}
    except json.JSONDecodeError:
        print(f'Parameter "{parameter_name}" is not in valid JSON format.', flush=True)
        return {}
    except Exception as e:
        print(f"An error occurred: {e}", flush=True)
        return {}


# Initialize and configure the base logger
def get_logger():
    logger = logging.getLogger(__name__)
    if not logger.handlers:
        log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
        log_format = "%(asctime)s.%(msecs)03d %(levelname)-8s [%(pathname)s:%(lineno)d] %(message)s"
        formatter = logging.Formatter(log_format)

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)

        logger.setLevel(log_level)
        logger.addHandler(stream_handler)
    return logger


# Function to add a custom attribute (request ID) to all log messages
def configure_request_id(request_id):
    class ContextFilter(logging.Filter):
        def filter(self, record):
            record.request_id = request_id
            return True

    logger = get_logger()
    filter = ContextFilter()
    logger.addFilter(filter)
    # Update formatter to include request_id
    for handler in logger.handlers:
        handler.setFormatter(
            logging.Formatter(
                "[%(request_id)s] %(asctime)s.%(msecs)03d %(levelname)-8s {%(pathname)s:%(lineno)d} %(message)s"
            )
        )

def get_run_environment():
    return os.environ.get("RunEnvironment", "prod")

def check_paid_member(gapi_client: GraphAPI, netid: str) -> bool:
    loop = asyncio.get_event_loop()
    paid = loop.run_until_complete(gapi_client.isPaidMember(netid))
    return paid

def create_checkout_session(netid, checkout_key):

    url = "https://api.stripe.com/v1/checkout/sessions"
    
    price = "price_1MUGIRDiGOXU9RuSChPYK6wZ"
    
    payload='success_url=https%3A%2F%2Facm.illinois.edu%2F%23%2Fpaid&line_items%5B0%5D%5Bprice%5D={}&line_items%5B0%5D%5Bquantity%5D=1&mode=payment&cancel_url=https%3A%2F%2Facm.illinois.edu%2F%23%2Fmembership&customer_email={}%40illinois.edu'.format(price, netid)

    headers = {
      'Content-Type': 'application/x-www-form-urlencoded',
      'Authorization': 'Bearer {}'.format(checkout_key)
    }
    
    response = requests.request("POST", url, headers=headers, data=payload)
    if response.status_code != 200:
        raise Exception("Stripe API Error")
    js = response.json()
    return js['url']