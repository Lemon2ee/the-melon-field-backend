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

base_url = "https://www.zfrontier.com"

mobile_login_url = f"{base_url}/api/login/mobile"

headers = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://www.zfrontier.com",
    "Referer": "https://www.zfrontier.com/app/circle/1",
    "X-Client-Locale": "zh-CN",
    "X-Csrf-Token": "1",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Accept-Encoding": "gzip, deflate, br"
}

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

# Setup logging first
parser = argparse.ArgumentParser(description='ZFrontier crawler')
parser.add_argument('--mobile', required=True, help='Mobile number for login')
parser.add_argument('--password', required=True, help='Password for login')
parser.add_argument('--log-level', default='INFO', 
                    choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                    help='Set the logging level (default: INFO)')
args = parser.parse_args()

# Configure logging based on argument
console_handler = logging.StreamHandler()
console_handler.setLevel(getattr(logging, args.log_level.upper()))
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

file_handler = logging.FileHandler('debug.log')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Root logger configuration
logging.getLogger('').setLevel(logging.DEBUG)
logging.getLogger('').addHandler(console_handler)
logging.getLogger('').addHandler(file_handler)

data = {
    "mobile": args.mobile,
    "password": args.password
}

response = requests.post(mobile_login_url, headers=headers, data=data)
logging.debug(f"Response status code: {response.status_code}")
logging.debug(f"Response body: {response.text}")

# Extract and print cookies
cookies = response.cookies
logging.debug(f"Cookie names: {', '.join(cookie.name for cookie in cookies)}")
for cookie in cookies:
    logging.debug(f"Cookie: {cookie.name} = {cookie.value}")


x_csrf_token = "1"
current_time = str(int(time.time()))
logging.debug(f"CSRF Token being used: {x_csrf_token}")
logging.debug(f"Current time being used: {current_time}")

# Let's log the exact string we're hashing
pre_hash_string = current_time + x_csrf_token
logging.debug(f"String being hashed: {pre_hash_string}")

t = hashlib.md5((current_time + x_csrf_token).encode()).hexdigest()
logging.debug(f"Generated t value: {t}")

# Prepare payload for flow list
flow_list_url = f"{base_url}/v2/flow/list"

logging.debug(f"Request Cookies: {dict(cookies)}")

csv_file = "flow_items.csv"
csv_headers = ["id", "hash_id", "view_url", "title", "user_nickname", "user_hash_id", "user_view_url"]

# Check if file exists and is empty
file_exists = os.path.exists(csv_file)
file_is_empty = False
if file_exists:
    file_is_empty = os.path.getsize(csv_file) == 0

# Only create new file with headers if file doesn't exist or is empty
if not file_exists or file_is_empty:
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=csv_headers)
        writer.writeheader()

# Initialize pagination variables
current_offset = ""
min_offset = 1000  # Stop when offset is less than this

while True:
    current_time = str(int(time.time())-1000)
    x_csrf_token = str(int(time.time() * 1000))  # Use millisecond timestamp as random token
    logging.debug(f"Current time: {current_time}")
    logging.debug(f"X-Csrf-Token: {x_csrf_token}")
    # Update payload with current offset
    flow_payload = {
        "time": current_time,
        "t": hashlib.md5((current_time + x_csrf_token).encode()).hexdigest(),
        "offset": current_offset,
        "cid": "1",
        "sortBy": "new",
        "tagIds[0]": "3023"
    }
    
    list_headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://www.zfrontier.com",
        "Referer": "https://www.zfrontier.com/app/circle/1",
        "X-Client-Locale": "zh-CN",
        "X-Csrf-Token": x_csrf_token,
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Accept-Encoding": "gzip, deflate, br"
    }
    
    logging.info(f"Fetching data with offset: {current_offset}")
    flow_response = requests.post(flow_list_url, headers=list_headers, data=flow_payload, cookies=cookies)
    
    if flow_response.status_code != 200:
        logging.error(f"Request failed with status code: {flow_response.status_code}")
        break
        
    json_data = flow_response.json()
    if json_data.get("ok") != 0 or "data" not in json_data:
        logging.error("Invalid response format")
        logging.debug(f"Full response: {json_data}")
        
        # Check for rate limiting message
        if json_data.get("ok") == 20001 and json_data.get("msg") == "操作太频繁了":
            logging.info("Rate limited. Waiting for 5 minutes before retrying...")
            time.sleep(300)  # Wait for 5 minutes (300 seconds)
            continue  # Retry with the same offset
        
        break  # Break for other types of errors
        
    # Get new offset for next iteration
    new_offset = json_data["data"].get("offset")
    logging.info(f"Next page offset: {new_offset}")
    
    # Save items to CSV
    with open(csv_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=csv_headers)
        for item in json_data["data"]["list"]:
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
    
    # Break conditions
    if not new_offset or int(new_offset) < min_offset:
        logging.info("Reached target offset, stopping")
        break
        
    # Update offset for next iteration
    current_offset = new_offset
    
    # Add a small delay to be nice to the server
    time.sleep(2)

logging.info("Finished fetching all data")