from datetime import datetime
import logging
import os

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


def get_resource_info(resource_type, resource_data, resource_mappings=None):
    # Generally the resource mapping is loaded when the Lambda starts and
    # passed when calling the function. This minimizes the times the file
    # needs to be loaded.
    if not resource_mappings:
        all_resource_mappings = get_mappings()
        resource_mappings = all_resource_mappings[resource_type]

    resource_info = {}
    for name, path in resource_mappings.items():
        resource_info[name] = jmespath.search(path, resource_data)
        if name == 'CreationDateTime':
            resource_info[name] = datetime.strptime(resource_info[name],
                                                    '%Y-%m-%dT%H:%M:%S+00:00')
    return resource_info
