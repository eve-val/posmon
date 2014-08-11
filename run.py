from evelink.api import API
from evelink.cache.shelf import ShelveCache
from raven.handlers.logging import SentryHandler

import ConfigParser
import logging

from main import process


# Read config values
config = ConfigParser.RawConfigParser()
config.read('posmon.ini')
keys = [(config.getint(section, 'keyID'), config.get(section, 'vCode'))
        for section in config.sections() if section.startswith('key:')]
cache_path = config.get('posmon', 'cache')
sentry_uri = config.get('posmon', 'sentry.uri')

# Set up logging
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
sentry_handler = SentryHandler(sentry_uri)
sentry_handler.setLevel(logging.WARNING)
logging.getLogger().addHandler(sentry_handler)

# Run!
cache=ShelveCache(cache_path)
try:
    for key_id, vcode in keys:
        api_key = API(api_key=(key_id, vcode), cache=cache)
        process(api_key)
except Exception as e:
    logging.exception(str(e))
finally:
    cache.cache.close()
