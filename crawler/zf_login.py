import requests
import logging

# Constants
BASE_URL = "https://www.zfrontier.com"
MOBILE_LOGIN_URL = f"{BASE_URL}/api/login/mobile"

DEFAULT_HEADERS = {
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

def login(mobile: str, password: str) -> dict:
    """
    Login to ZFrontier using mobile number and password.
    
    Args:
        mobile (str): Mobile phone number
        password (str): Password
        
    Returns:
        dict: Cookie data from successful login
    """
    data = {"mobile": mobile, "password": password}
    response = requests.post(MOBILE_LOGIN_URL, headers=DEFAULT_HEADERS, data=data)
    logging.debug(f"Response status code: {response.status_code}")
    logging.debug(f"Response body: {response.text}")
    return response.cookies