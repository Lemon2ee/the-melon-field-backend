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
FLOW_LIST_URL = f"{BASE_URL}/v2/flow/list"
RATE_LIMIT_WAIT_TIME = 600  # 10 minutes in seconds
REQUEST_TOO_OFTEN_RESP_MSG = "操作太频繁了"
CSV_FILE_BASE_NAME = "flow_items.csv"

@dataclass
class User:
    nickname: str
    hash_id: str
    view_url: str

@dataclass
class FlowItem:
    id: int
    hash_id: str
    view_url: str
    title: str
    user: User

def setup_argument_parser():
    parser = argparse.ArgumentParser(description='ZFrontier crawler')
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

def initialize_csv(csv_file):
    csv_headers = ["id", "hash_id", "view_url", "title", "user_nickname", "user_hash_id", "user_view_url"]
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
    return current_time, x_csrf_token

def save_items_to_csv(items, csv_file, csv_headers):
    with open(csv_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=csv_headers)
        for item in items:
            flow_item = FlowItem(
                id=item["id"],
                hash_id=item["hash_id"],
                view_url=item["view_url"],
                title=item.get("title", ""),
                user=User(
                    nickname=item["user"]["nickname"],
                    hash_id=item["user"]["hash_id"],
                    view_url=item["user"]["view_url"]
                )
            )
            writer.writerow({
                "id": flow_item.id,
                "hash_id": flow_item.hash_id,
                "view_url": flow_item.view_url,
                "title": flow_item.title,
                "user_nickname": flow_item.user.nickname,
                "user_hash_id": flow_item.user.hash_id,
                "user_view_url": flow_item.user.view_url
            })

def fetch_flow_data(cookies, current_offset="", min_offset=1000):
    while True:
        current_time, x_csrf_token = get_request_parameters()
        flow_payload = {
            "time": current_time,
            "t": hashlib.md5((current_time + x_csrf_token).encode()).hexdigest(),
            "offset": current_offset,
            "cid": "1",
            "sortBy": "new",
            "tagIds[0]": "3023"
        }
        
        list_headers = DEFAULT_HEADERS.copy()
        list_headers["X-Csrf-Token"] = x_csrf_token
        
        logging.info(f"Fetching data with offset: {current_offset}")
        flow_response = requests.post(FLOW_LIST_URL, headers=list_headers, data=flow_payload, cookies=cookies)
        
        if not handle_response(flow_response):
            break
            
        json_data = flow_response.json()
        if not is_valid_response(json_data):
            continue
            
        yield json_data["data"]
        
        new_offset = json_data["data"].get("offset")
        logging.info(f"Next page offset: {new_offset}")
        
        if not new_offset or int(new_offset) < min_offset:
            logging.info("Reached target offset, stopping")
            break
            
        current_offset = new_offset
        time.sleep(2)

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

def rename_csv_with_date(csv_file):
    """Rename the CSV file to include the current date."""
    date_str = time.strftime("%Y%m%d")
    new_filename = f"{date_str}_{CSV_FILE_BASE_NAME}"
    try:
        os.rename(csv_file, new_filename)
        logging.info(f"Renamed {csv_file} to {new_filename}")
    except OSError as e:
        logging.error(f"Failed to rename CSV file: {e}")

def main():
    args = setup_argument_parser()
    setup_logging(args.log_level)
    
    cookies = login(args.mobile, args.password)
    csv_headers = initialize_csv(CSV_FILE_BASE_NAME)
    
    for data in fetch_flow_data(cookies):
        save_items_to_csv(data["list"], CSV_FILE_BASE_NAME, csv_headers)
    
    logging.info("Finished fetching all data")
    rename_csv_with_date(CSV_FILE_BASE_NAME)

if __name__ == "__main__":
    main()