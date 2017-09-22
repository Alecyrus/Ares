import logging
import logging.config
import os.path


logging.config.fileConfig('tests/logging.ini')
logger = logging.getLogger('database')