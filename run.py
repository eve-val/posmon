from evelink.api import API
from evelink.cache.shelf import ShelveCache

import ConfigParser
import json
import logging
import sys

from main import process


# Read config values
config = ConfigParser.RawConfigParser()
config.read('posmon.ini')
keys = [(config.getint(section, 'keyID'), config.get(section, 'vCode'))
        for section in config.sections() if section.startswith('key:')]
cache_path = config.get('posmon', 'cache')
try:
    sentry_uri = config.get('posmon', 'sentry.uri')
except ConfigParser.NoOptionError:
    sentry_uri = None

# Set up logging
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
if sentry_uri:
    from raven.handlers.logging import SentryHandler
    sentry_handler = SentryHandler(sentry_uri)
    sentry_handler.setLevel(logging.WARNING)
    logging.getLogger().addHandler(sentry_handler)

# Run!
cache=ShelveCache(cache_path)
fmt = sys.argv[1] if len(sys.argv) > 1 else 'text'
try:
    for key_id, vcode in keys:
        api_key = API(api_key=(key_id, vcode), cache=cache)
        try:
            process(api_key, format=fmt)
        except Exception as e:
            if fmt == 'text':
                print "error processing key: %s" % (str(e),)
            else:
                print json.dumps({'error': str(e)})
            logging.exception(str(e))
finally:
    cache.cache.close()
