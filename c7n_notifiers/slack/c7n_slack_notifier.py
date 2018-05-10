#!/usr/bin/env python3

import base64
import json
import os
import logging
import urllib.request
import zlib

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def decode_c7n_message(message):
    try:
        decoded = base64.b64decode(message)
        decompressed = zlib.decompress(decoded)
        message_dict = json.loads(decompressed.decode('utf8'))
    except:
        logger.error(
            "Unable to decode message for Cloud Custodian. Message received "
            "was: {}".format(message)
        )
        raise
    logger.debug(
        "Decoded message from Cloud Custodian: {}".format(message_dict)
    )
    return message_dict


def send_slack_message(webhook_url, message):
    if type(message) is not str:
        raise TypeError(
            "Slack message must be string, but is {}".format(type(message))
        )
    logger.debug(
        "Sending message to slack webhook {}: {}".format(webhook_url, message)
    )
    message_body = {'text': message}
    message_json = json.dumps(message_body)
    post_data = message_json.encode('utf8')
    req = urllib.request.Request(webhook_url,
                                 headers={'content-type': 'application/json'},
                                 data=post_data)
    response = urllib.request.urlopen(req)
    logger.debug("Message response: {}".format(response))


def lambda_handler(event, context):
    webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
    if webhook_url is None:
        raise RuntimeError(
            "Env Var SLACK_WEBHOOK_URL must be set"
        )

    c7n_message = event['Records'][0]['Sns']['Message']
    logger.debug(
        "Recieved encoded message from Cloud Custodian: {}".format(c7n_message)
    )
    message = decode_c7n_message(c7n_message)
    send_slack_message(webhook_url, str(message))


def get_resource_info(resource_type, resource_data):
    if resource_type == 'ec2':
        return get_ec2_info(resource_data)


def get_ec2_info(resource_data):
    resource_id = resource_data['InstanceId']
    creation_date = resource_data['LaunchTime']
    resource_info = (resource_id, creation_date)
    return resource_info


