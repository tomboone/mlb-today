""" Application Logging Configuration """
import logging
from logging.handlers import TimedRotatingFileHandler
import os

import src.mlb_today.config as config

LOG_DIRECTORY = config.LOG_DIRECTORY
LOG_FILE_NAME = "application.log"
LOG_FILE_PATH = os.path.join(LOG_DIRECTORY, LOG_FILE_NAME)
LOG_LEVEL = config.LOG_LEVEL

os.makedirs(LOG_DIRECTORY, exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # Set your desired logging level
handler = TimedRotatingFileHandler(filename=LOG_FILE_PATH, when='midnight', backupCount=30, encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
