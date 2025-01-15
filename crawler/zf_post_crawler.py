from zf_common import (
    BASE_URL, User, setup_argument_parser, setup_logging,
    initialize_csv, get_request_parameters, handle_response,
    is_valid_response, rename_file_with_date
)
from zf_login import login, DEFAULT_HEADERS
from dataclasses import dataclass
import logging
import time
import hashlib
import csv
import requests

# Constants specific to post crawler
FLOW_LIST_URL = f"{BASE_URL}/v2/flow/list"
CSV_FILE_BASE_NAME = "flow_items.csv"

@dataclass
class FlowItem:
    id: int
    hash_id: str
    view_url: str
    title: str
    user: User

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
        current_time, x_csrf_token, t = get_request_parameters()
        flow_payload = {
            "time": current_time,
            "t": t,
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

def main():
    args = setup_argument_parser('ZFrontier post crawler')
    setup_logging(args.log_level)
    
    cookies = login(args.mobile, args.password)
    csv_headers = ["id", "hash_id", "view_url", "title", "user_nickname", "user_hash_id", "user_view_url"]
    initialize_csv(CSV_FILE_BASE_NAME, csv_headers)
    
    for data in fetch_flow_data(cookies):
        save_items_to_csv(data["list"], CSV_FILE_BASE_NAME, csv_headers)
    
    logging.info("Finished fetching all data")
    rename_file_with_date(CSV_FILE_BASE_NAME, CSV_FILE_BASE_NAME)

if __name__ == "__main__":
    main()