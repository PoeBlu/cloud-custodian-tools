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
    for resource_info in resources_data:
        resource_info = lib.resources.get_resource_info(
            resource_type,
            resource_info,
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
    resource_id_pad = 22
    resource_name_pad = 15
    creation_dt_pad = 19
    creator_pad = 12
    line_layout = (
        "{:<{resource_id_pad}}  {:<{resource_name_pad}}  "
        "{:<{creation_dt_pad}}  {:<{creator_pad}}"
    )
    header_line = line_layout.format("ResourceId",
                                     "ResourceName",
                                     "CreationDateTime",
                                     "Creator",
                                     resource_id_pad=resource_id_pad,
                                     resource_name_pad=resource_name_pad,
                                     creation_dt_pad=creation_dt_pad,
                                     creator_pad=creator_pad
                                     )
    formatted_lines.append(header_line)
    for resource_info in resources:
        # If Name is a tag and is not set then JMESpath returns an empty list
        # in this case set the Name to empty
        if type(resource_info['name']) is list:
            if len(resource_info['name']) == 0:
                name = ""
            else:
                name = resource_info['name'][0][:resource_name_pad]
        else:
            name = resource_info['name'][:resource_name_pad]

        # If Creator tag is not set then JMESpath returns an empty list
        # in this case set the creator to empty
        if len(resource_info['creator']) == 0:
            creator = ""
        else:
            creator = resource_info['creator'][0][:creator_pad]

        resource = resource_info['id'][:resource_id_pad]
        # Padding needs to be calculated for each resource id as slack renders
        # the link, which removes many characters on screen,
        # so need to add white space to compensate the removal of characters
        # when rendered.
        resource_pad = resource_id_pad
        if resource_info.get('url'):
            resource_url = string.Template(
                resource_info['url']
            ).substitute(resource_info)
            resource_link = '<{}|{}>'.format(resource_url, resource)
            resource_pad = (
                len(resource_link) - len(resource) + resource_id_pad
            )
            resource = resource_link

        datetime_string = resource_info['creation_datetime'].strftime(
            '%Y-%m-%d %H:%M:%S'
        )

        formatted_lines.append(
            line_layout.format(resource,
                               name,
                               datetime_string,
                               creator,
                               resource_id_pad=resource_pad,
                               resource_name_pad=resource_name_pad,
                               creation_dt_pad=creation_dt_pad,
                               creator_pad=creator_pad
            )
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
