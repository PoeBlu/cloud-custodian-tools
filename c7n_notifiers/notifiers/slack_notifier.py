#!/usr/bin/env python3
from datetime import datetime
import json
from operator import itemgetter
import os
import logging
import string
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
    footer_text = "{} - All times in UTC".format(
        datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    )
    message_body = {
        'attachments': [
            {
                'color': 'warning',
                'footer': footer_text,
                'text': message
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
    encoded_message = event['Records'][0]['Sns']['Message']
    logger.debug(
        "Received encoded message from Cloud Custodian: {}".format(
            encoded_message
        )
    )
    c7n_message = lib.c7n.decode_message(encoded_message)
    # Currently assume one webhook url, maybe add support for multiples in
    # the future
    if len(c7n_message['action']['to']) > 1:
        logger.warning(
            "More than one destination (i.e. 'to') has been specified, "
            "but only using the first one. "
        )
    webhook_url = c7n_message['action']['to'][0]
    message_template = c7n_message['action']['template']
    resource_type = c7n_message['policy']['resource']
    resources_data = c7n_message['resources']
    region = c7n_message['region']

    resources = []
    for resource in resources_data:
        resource_info = lib.resources.get_resource_info(
            resource_type,
            resource,
            resource_mappings=resource_mappings[resource_type]
        )
        # Adding region to resource_info makes rendering the resource link
        # easier
        resource_info['region'] = region
        resources.append(resource_info)

    logger.debug("resources: {}".format(resources))

    # Sort resources by CreationDateTime
    resources.sort(key=itemgetter('creation_datetime'), reverse=True)

    # Formatting resource info in Python since slack doesn't support robust
    # formatting.
    formatted_lines = []
    line_layout = "{:<{resource_pad}}  {:<15}  {:<19}  {}"
    header_line = line_layout.format("ResourceId",
                                     "ResourceName",
                                     "CreationDateTime",
                                     "Creator",
                                     resource_pad=19)
    formatted_lines.append(header_line)
    for resource in resources:
        # If Name is a tag and is not set then JMESpath returns an empty list
        # in this case set the Name to empty
        if type(resource['name']) is list:
            if len(resource['name']) == 0:
                name = ""
            else:
                name = resource['name'][0][:15]
        else:
            name = resource['name'][:15]

        # If Creator tag is not set then JMESpath returns an empty list
        # in this case set the creator to empty
        if len(resource['creator']) == 0:
            creator = ""
        else:
            creator = resource['creator'][0][:15]

        if resource.get('link'):
            resource_link = string.Template(
                resource['link']
            ).substitute(resource)
            resource_id = '<{}|{}>'.format(resource_link, resource['id'])
            # Strange padding is needed as slack renders the link, which
            # removes many characters on screen, so need to compensate
            resource_pad = len(resource_id) - len(resource['id']) + 19

        else:
            resource_id = resource['id']
            resource_pad = 19

        datetime_string = resource['creation_datetime'].strftime(
            '%Y-%m-%d %H:%M:%S'
        )

        formatted_lines.append(
            line_layout.format(resource_id,
                               name,
                               datetime_string,
                               creator,
                               resource_pad=resource_pad)
        )

    slack_message_info = {}
    if c7n_message['account'] != '':
        slack_message_info['account_info'] = "{} ({})".format(
            c7n_message['account_id'],
            c7n_message['account']
        )
    else:
        slack_message_info['account_info'] = c7n_message['account_id']

    slack_message_info['region'] = region
    slack_message_info['resource_type'] = resource_type
    slack_message_info['resources'] = "\n".join(formatted_lines)

    current_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = current_dir + "/templates"
    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_path)
    )
    slack_message_template = jinja_env.get_template(message_template)
    slack_message = slack_message_template.render(**slack_message_info)

    send_slack_message(webhook_url, slack_message)
