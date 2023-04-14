#!/usr/bin/env python3
from datetime import datetime
import json
import os
import logging
import traceback
import urllib.request

import jinja2

import lib.messaging
import lib.resources

logger = logging.getLogger('c7n_notifiers')
logger.setLevel(logging.DEBUG)


def send_slack_message(webhook_url, message_dict):
    if type(message_dict) is not dict:
        raise TypeError(f"Slack message must be dict, but is {type(message)}")

    footer_text = (
        f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} - All times in UTC"
    )

    color = message_dict.get('color', '#6d6c6c')

    message_body = {
        'attachments': [
            {
                'color': color,
                'footer': footer_text,
                'text': message_dict['text'],
                'title': message_dict['title']
            }
        ]
    }

    logger.debug(f"Sending message to slack webhook {webhook_url}: {message_body}")

    message_json = json.dumps(message_body)
    post_data = message_json.encode('utf8')
    req = urllib.request.Request(webhook_url,
                                 headers={'content-type': 'application/json'},
                                 data=post_data)
    response = urllib.request.urlopen(req)
    logger.debug(f"Message response: {response}")


def format_exception_message(c7n_message, exception):
    tb = ''.join(traceback.format_exception(
        etype=type(exception),
        value=exception,
        tb=exception.__traceback__)
    )

    # format JSON to something better readable in the slack message
    formatted_c7n_message = json.dumps(c7n_message, indent=4)

    slack_message_info = {
        'traceback': tb,
        'c7n_message': formatted_c7n_message
    }

    current_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = f"{current_dir}/templates"
    subject_template = 'exception.subject'
    body_template = 'exception.body'
    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_path)
    )
    slack_subject_template = jinja_env.get_template(subject_template)
    slack_subject = slack_subject_template.render(**slack_message_info)
    slack_body_template = jinja_env.get_template(body_template)
    slack_body = slack_body_template.render(**slack_message_info)

    return {'title': slack_subject, 'text': slack_body, 'color': '#000000'}


def format_slack_resource_message(message_data):
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
    formatted_lines = [header_line]
    for resource_info in message_data['resources']:
        # Padding needs to be calculated for each resource id as slack renders
        # the link, which removes many characters on screen,
        # so need to add white space to compensate the removal of characters
        # when rendered.
        resource_pad = resource_id_pad
        if resource_info.get('url'):
            resource = resource_info['id'][:resource_id_pad]
            resource_url = resource_info['url']
            resource_link = f'<{resource_url}|{resource}>'
            resource_pad = (
                len(resource_link) - len(resource) + resource_id_pad
            )
            resource = resource_link
        else:
            resource = resource_info['id'][:resource_id_pad]

        name = resource_info['name'][:resource_name_pad]

        datetime_string = resource_info['creation_datetime'].strftime(
            '%Y-%m-%d %H:%M:%S'
        )
        creator = resource_info['creator'][:creator_pad]

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

    slack_message_info = {
        'resource_type': message_data['resource_type'],
        'region': message_data['region'],
        'account_info': message_data['account_info'],
        'resources': "\n".join(formatted_lines)
    }

    current_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = f"{current_dir}/templates"
    subject_template = message_data['message_template'] + '.subject'
    body_template = message_data['message_template'] + '.body'
    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_path)
    )
    slack_subject_template = jinja_env.get_template(
        subject_template
    )
    slack_subject = slack_subject_template.render(**slack_message_info)
    slack_body_template = jinja_env.get_template(
        body_template
    )
    slack_body = slack_body_template.render(**slack_message_info)

    actions = set()
    for action_item in message_data['policy']['actions']:
        if type(action_item) is dict:
            # If there is an op sepcified add that, otherwise add the type
            action = action_item.get('op', action_item['type'])
            actions.add(action)
        else:
            actions.add(action_item)

    danger_actions = {'delete', 'terminate'}
    color = 'danger' if actions.intersection(danger_actions) else 'warning'
    return {'title': slack_subject, 'text': slack_body, 'color': color}


def lambda_handler(event, context):
    encoded_message = event['Records'][0]['Sns']['Message']
    logger.debug(
        f"Received encoded message from Cloud Custodian: {encoded_message}"
    )
    c7n_message = lib.messaging.decode_message(encoded_message)
    # Currently assume one webhook url, maybe add support for multiples in
    # the future
    if len(c7n_message['action']['to']) > 1:
        logger.warning(
            "More than one destination (i.e. 'to') has been specified, "
            "but only using the first one. "
        )
    webhook_url = c7n_message['action']['to'][0]

    # Try to get the data from the c7n_message and format a message for
    # slack If an exception is encountered, send the error to slack and
    # re-raise the exception
    try:
        message_data = lib.messaging.get_message_data(c7n_message)
        slack_message = format_slack_resource_message(message_data)
        send_slack_message(webhook_url, slack_message)
    # Yes this is broad but we want to send info on any exception to slack
    except Exception as e:
        slack_message = format_exception_message(c7n_message, e)
        send_slack_message(webhook_url, slack_message)
        raise






