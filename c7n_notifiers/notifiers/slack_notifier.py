#!/usr/bin/env python3
import json
from operator import itemgetter
import os
import logging
import urllib.request

import jinja2

import lib.c7n
import lib.resources

logger = logging.getLogger('c7n_notifiers')
logger.setLevel(logging.DEBUG)

# This loads resources from the resource_mappings.yaml file
# We do this on Lambda container start so we only have to read the file once
resource_mappings = lib.resources.get_mappings()


def send_slack_message(webhook_url, message):
    if type(message) is not str:
        raise TypeError(
            "Slack message must be string, but is {}".format(type(message))
        )
    logger.debug(
        "Sending message to slack webhook {}: {}".format(webhook_url, message)
    )
    message_body = {
        'attachments': [
            {
                'text': message,
                'color': 'warning'
             }
        ]
    }

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

    encoded_message = event['Records'][0]['Sns']['Message']
    logger.debug(
        "Received encoded message from Cloud Custodian: {}".format(
            encoded_message
        )
    )
    c7n_message = lib.c7n.decode_message(encoded_message)
    resource_type = c7n_message['policy']['resource']
    resources_data = c7n_message['resources']

    resources = []
    for resource in resources_data:
        resources.append(
            lib.resources.get_resource_info(
                resource_type,
                resource,
                resource_mappings=resource_mappings[resource_type]
            )
        )

    logger.debug("resources: {}".format(resources))

    # Sort resources by CreationDateTime
    resources.sort(key=itemgetter('CreationDateTime'), reverse=True)

    # Formatting resource info in Python since slack doesn't support robust
    # formatting.
    formatted_lines = []
    line_layout = "{:<22} {:<28} {}"
    header_line = line_layout.format("ResourceId",
                                     "CreationDateTime",
                                     "Creator")
    formatted_lines.append(header_line)
    for resource in resources:
        # If creator tag is not set then JMESpath returns an empty list
        # in this case set the creator to unknown
        if len(resource['Creator']) == 0:
            creator = "unknown"
        else:
            creator = resource['Creator'][0]
        formatted_lines.append(
            line_layout.format(resource['ResourceId'],
                               str(resource['CreationDateTime']),
                               creator)
        )

    slack_message_info = {}
    slack_message_info['account_id'] = c7n_message['account_id']
    slack_message_info['region'] = c7n_message['region']
    slack_message_info['resource_type'] = resource_type
    slack_message_info['resources'] = "\n".join(formatted_lines)

    current_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = current_dir + "/templates"
    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_path)
    )
    slack_message_template = jinja_env.get_template('reaper')
    slack_message = slack_message_template.render(**slack_message_info)

    send_slack_message(webhook_url, slack_message)
