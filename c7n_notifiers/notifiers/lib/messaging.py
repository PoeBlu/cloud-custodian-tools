import base64
import json
from operator import itemgetter
import logging
import zlib

import lib.resources

logger = logging.getLogger('c7n_notifiers')
logger.setLevel(logging.INFO)


def decode_message(message):
    try:
        decoded = base64.b64decode(message)
        decompressed = zlib.decompress(decoded)
        message_dict = json.loads(decompressed.decode('utf8'))
    except Exception:
        logger.error(
            "Unable to decode message for Cloud Custodian. Message received "
            "was: {}".format(message)
        )
        raise
    logger.debug(
        "Decoded message from Cloud Custodian: {}".format(message_dict)
    )
    return message_dict


def get_message_data(c7n_message):
    if c7n_message['account'] != '':
        account_info = "{} ({})".format(
            c7n_message['account_id'],
            c7n_message['account']
        )
    else:
        account_info = c7n_message['account_id']

    resource_type = c7n_message['policy']['resource']
    region = c7n_message['region']
    resources = []
    for resource_info in c7n_message['resources']:
        resource_info = lib.resources.get_resource_info(
            c7n_message['policy']['resource'],
            resource_info,
            region
        )
        resources.append(resource_info)

    # Sort resources by CreationDateTime
    resources.sort(key=itemgetter('creation_datetime'), reverse=True)

    message_data = {
        'message_template': c7n_message['action']['template'],
        'resource_type': resource_type,
        'region': region,
        'resources': resources,
        'account_info': account_info,
        'policy': c7n_message['policy']
    }

    logger.debug("message_data: {}".format(message_data))

    return message_data
