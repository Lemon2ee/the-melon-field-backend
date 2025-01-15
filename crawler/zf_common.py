import hashlib
import requests
import logging
import argparse
import time
from typing import TypedDict, List
from dataclasses import dataclass
import csv
import os
import logging.handlers
from zf_login import login, DEFAULT_HEADERS

# Constants
BASE_URL = "https://www.zfrontier.com"
RATE_LIMIT_WAIT_TIME = 600  # 10 minutes in seconds
REQUEST_TOO_OFTEN_RESP_MSG = "操作太频繁了"

@dataclass
class User:
    nickname: str
    hash_id: str
    view_url: str

def setup_argument_parser(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--mobile', required=True, help='Mobile number for login')
    parser.add_argument('--password', required=True, help='Password for login')
    parser.add_argument('--log-level', default='INFO', 
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Set the logging level (default: INFO)')
    return parser.parse_args()

def setup_logging(log_level):
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    file_handler = logging.FileHandler('debug.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    root_logger = logging.getLogger('')
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

def initialize_csv(csv_file, csv_headers):
    file_exists = os.path.exists(csv_file)
    file_is_empty = file_exists and os.path.getsize(csv_file) == 0

    if not file_exists or file_is_empty:
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=csv_headers)
            writer.writeheader()
    return csv_headers

def get_request_parameters():
    current_time = str(int(time.time())-1000)
    x_csrf_token = str(int(time.time() * 1000))
    t = hashlib.md5((current_time + x_csrf_token).encode()).hexdigest()
    return current_time, x_csrf_token, t

def handle_response(response):
    if response.status_code != 200:
        logging.error(f"Request failed with status code: {response.status_code}")
        return False
    return True

def is_valid_response(json_data):
    if json_data.get("ok") != 0 or "data" not in json_data:
        logging.error("Invalid response format")
        logging.debug(f"Full response: {json_data}")
        
        if json_data.get("ok") == 20001 and json_data.get("msg") == REQUEST_TOO_OFTEN_RESP_MSG:
            logging.info(f"Rate limited. Waiting for {RATE_LIMIT_WAIT_TIME} seconds before retrying...")
            time.sleep(RATE_LIMIT_WAIT_TIME)
            return False
            
        return False
    return True

def rename_file_with_date(file_path, base_name):
    """Rename the file to include the current date."""
    date_str = time.strftime("%Y%m%d")
    new_filename = f"{date_str}_{base_name}"
    try:
        os.rename(file_path, new_filename)
        logging.info(f"Renamed {file_path} to {new_filename}")
    except OSError as e:
        logging.error(f"Failed to rename file: {e}")