from zf_common import (
    setup_argument_parser, setup_logging,
    get_request_parameters, handle_response,
    is_valid_response, BASE_URL
)
from zf_login import login, DEFAULT_HEADERS
import logging
import json
import csv
import os
import glob
import requests
import time

# Constants specific to comment crawler
COMMENT_URL = f"{BASE_URL}/api/circle/flowReplyList"
COMMENTS_DIR = "./comments"

def get_latest_flow_items_file():
    """Find the most recent flow_items CSV file."""
    files = glob.glob("*_flow_items.csv")
    if not files:
        raise FileNotFoundError("No flow_items CSV file found")
    return max(files)  # Returns the most recent file based on date prefix

def load_post_ids(csv_file):
    """Extract post IDs from the flow items CSV file."""
    post_ids = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            post_ids.append(row['id'])
    return post_ids

def fetch_comments(post_id, cookies):
    """Fetch all comments for a specific post."""
    all_comments = []
    page = 1
    
    while True:
        current_time, x_csrf_token, t = get_request_parameters()
        
        payload = {
            "time": current_time,
            "t": t,
            "snap": "0",
            "id": post_id,
            "sortBy": "ctime_asc",
            "unfold": "0",
            "page": str(page)
        }
        
        headers = DEFAULT_HEADERS.copy()
        headers["X-Csrf-Token"] = x_csrf_token
        
        logging.info(f"Fetching comments for post ID: {post_id}, page: {page}")
        response = requests.post(COMMENT_URL, headers=headers, data=payload, cookies=cookies)
        
        if not handle_response(response):
            return None
            
        json_data = response.json()
        if not is_valid_response(json_data):
            return None
        
        comments_list = json_data["data"]["list"]
        if not comments_list:  # Empty list means no more comments
            break
            
        all_comments.extend(comments_list)
        page += 1
        time.sleep(2)  # Rate limiting between pages
    
    logging.info(f"Fetched total {len(all_comments)} comments for post {post_id}")
    return {
        "ok": 0,
        "msg": "",
        "data": {
            "list": all_comments,
            "authorZan": [],
            "foldCnt": None
        }
    }

def save_comments(post_id, comments_data):
    """Save comments data to JSON file."""
    os.makedirs(COMMENTS_DIR, exist_ok=True)
    output_file = os.path.join(COMMENTS_DIR, f"{post_id}.json")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(comments_data, f, ensure_ascii=False, indent=2)
    logging.info(f"Saved comments for post {post_id}")

def main():
    args = setup_argument_parser('ZFrontier comment crawler')
    setup_logging(args.log_level)
    
    # Login to get cookies
    cookies = login(args.mobile, args.password)
    
    try:
        # Get the latest flow items file
        flow_items_file = get_latest_flow_items_file()
        logging.info(f"Using flow items file: {flow_items_file}")
        
        # Load post IDs
        post_ids = load_post_ids(flow_items_file)
        logging.info(f"Found {len(post_ids)} posts to process")
        
        # Fetch and save comments for each post
        for post_id in post_ids:
            comments_data = fetch_comments(post_id, cookies)
            if comments_data:
                save_comments(post_id, comments_data)
            time.sleep(2)  # Rate limiting
            
        logging.info("Finished fetching all comments")
        
    except FileNotFoundError as e:
        logging.error(f"Error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()