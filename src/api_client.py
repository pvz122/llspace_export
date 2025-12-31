import requests
import logging
from .config import API_BASE_URL
from .utils import generate_headers

class LLSpaceClient:
    def __init__(self):
        self.token = None
        self.user_info = {}

    def login(self, account, password):
        url = f"{API_BASE_URL}/api/1/users/sign_in"
        headers = generate_headers()
        data = {
            "account": account,
            "password": password
        }
        
        try:
            resp = requests.post(url, headers=headers, data=data, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            
            if result.get("code") == 0:
                self.token = result["user"]["authentication_token"]
                self.user_info = result["user"]
                return True, None
            else:
                return False, result.get("message", "未知错误")
        except Exception as e:
            logging.error(f"登录错误: {e}")
            return False, str(e)

    def get_packages(self):
        url = f"{API_BASE_URL}/api/1/pg/list"
        headers = generate_headers(self.token)
        
        try:
            resp = requests.post(url, headers=headers, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            
            if result.get("code") == 0:
                return result.get("pg", [])
            else:
                logging.error(f"获取卡包列表错误: {result.get('message')}")
                return []
        except Exception as e:
            logging.error(f"获取卡包列表异常: {e}")
            return []

    def get_directory(self, pg_id):
        url = f"{API_BASE_URL}/api/1/pg/directoryList"
        headers = generate_headers(self.token)
        data = {"pg_id": pg_id}
        
        try:
            resp = requests.post(url, headers=headers, data=data, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            
            if result.get("code") == 0:
                return result.get("cards", [])
            else:
                logging.error(f"获取目录错误: {result.get('message')}")
                return []
        except Exception as e:
            logging.error(f"获取目录异常: {e}")
            return []

    def get_card_detail(self, card_id, pg_id):
        url = f"{API_BASE_URL}/api/1/cards/detail"
        headers = generate_headers(self.token)
        data = {"card_id": card_id, "from_pg_id": pg_id}
        
        try:
            resp = requests.post(url, headers=headers, data=data, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            
            if result.get("code") == 0:
                return result.get("card", {})
            else:
                logging.error(f"获取卡片详情错误: {result.get('message')}")
                return None
        except Exception as e:
            logging.error(f"获取卡片详情异常: {e}")
            return None
