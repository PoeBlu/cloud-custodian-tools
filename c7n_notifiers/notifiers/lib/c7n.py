import base64
import json
import logging
import zlib

logger = logging.getLogger('c7n_notifiers')
logger.setLevel(logging.INFO)


def decode_message(message):
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
