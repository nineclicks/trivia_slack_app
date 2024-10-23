import os
import json

CONFIG_FILE_PATH = os.getenv('CONFIG_FILE_PATH', 'config.json')

def load_config(filename: str=CONFIG_FILE_PATH):
    """Load a config file into environment variables

    :param filename: config json path, defaults to CONFIG_FILE_PATH or 'config.json'
    :type filename: str, optional
    """

    try:
        with open(filename, 'r') as fp:
            config = json.load(fp)
    except FileNotFoundError:
        return
    
    for k, v in config.items():
        os.environ[k] = str(v)
