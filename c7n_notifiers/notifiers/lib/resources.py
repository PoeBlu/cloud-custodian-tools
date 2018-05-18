from datetime import datetime
import logging
import os
import string

import jmespath
import yaml

logger = logging.getLogger('c7n_notifiers')
logger.setLevel(logging.INFO)

current_dir = os.path.dirname(os.path.abspath(__file__))
MAPPINGS_FILE_PATH = current_dir + "/resource_mappings.yaml"


def get_mappings(file_path=MAPPINGS_FILE_PATH):
    with open(file_path) as mapping_file:
        mappings = yaml.load(mapping_file.read())
    return mappings


def get_datetime(datetime_string):
    dt_obj = None
    datetime_patterns = [
        '%Y-%m-%dT%H:%M:%S+00:00',
        '%Y-%m-%dT%H:%M:%S.%f+00:00'
    ]
    for pattern in datetime_patterns:
        try:
            dt_obj = datetime.strptime(
                datetime_string,
                pattern
            )
        except ValueError:
            logger.debug(
                "datetime pattern {} did not work for datetime "
                "string {}".format(pattern, datetime_string)
            )
    if dt_obj is None:
        raise RuntimeError(
            "Unable to convert {} into dattetime object".format(
                datetime_string
            )
        )
    return dt_obj


def get_resource_info(resource_type, resource_data, region,
                      resource_mappings=None):
    # Generally the resource mapping is loaded when the Lambda starts and
    # passed when calling the function. This minimizes the times the file
    # needs to be loaded.
    if not resource_mappings:
        all_resource_mappings = get_mappings()
        resource_mappings = all_resource_mappings[resource_type]

    resource_info = {
        'region': region
    }
    # Build initial resource_info dict
    for key, path in resource_mappings['info'].items():
        resource_info[key] = jmespath.search(path, resource_data)

    for key, value in resource_info.items():
        if key == 'creation_datetime':
            resource_info['creation_datetime'] = get_datetime(value)
        elif key == 'creator' and type(value) is list:
            resource_info['creator'] = value[0]
        # If Name is a tag and is not set then JMESpath returns an empty list
        # in this case set the Name to empty, otherwise get the only item from
        # list
        elif key == 'name' and type(value) is list:
            if len(resource_info['name']) == 0:
                resource_info['name'] = ""
            elif len(resource_info['name']) == 1:
                resource_info['name'] = value[0]

    if resource_mappings.get('url'):
        resource_info['url'] = string.Template(
            resource_mappings['url']
        ).substitute(resource_info)

    logger.debug("resource_info: {}".format(resource_info))

    return resource_info
