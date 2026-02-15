
import requests
import logging
from .config import ALIST_HOST, ALIST_USER, ALIST_PASS

logger = logging.getLogger("AList")

class AListManager:
    def __init__(self):
        self.host = ALIST_HOST.rstrip('/')
        self.username = ALIST_USER
        self.password = ALIST_PASS
        self.token = None

    def login(self):
        """Get Token from AList"""
        try:
            url = f"{self.host}/api/auth/login"
            payload = {"username": self.username, "password": self.password}
            r = requests.post(url, json=payload, timeout=10)
            data = r.json()
            if data.get('code') == 200:
                self.token = data['data']['token']
                return True
            else:
                logger.error(f"AList Login Failed: {data}")
                return False
        except Exception as e:
            logger.error(f"AList Connection Error: {e}")
            return False

    def get_headers(self):
        if not self.token:
            self.login()
        return {"Authorization": self.token}

    def list_files(self, path="/", page=1, per_page=20):
        if not path: path = "/"
        url = f"{self.host}/api/fs/list"
        payload = {
            "path": path,
            "password": "",
            "page": page,
            "per_page": per_page,
            "refresh": False
        }
        try:
            r = requests.post(url, json=payload, headers=self.get_headers(), timeout=15)
            if r.status_code == 401: # Token expired
                self.login()
                r = requests.post(url, json=payload, headers=self.get_headers(), timeout=15)
            
            return r.json()
        except Exception as e:
            logger.error(f"List files error: {e}")
            return None

    def get_file_info(self, path):
        """Get detail (especially direct link)"""
        url = f"{self.host}/api/fs/get"
        payload = {"path": path, "password": ""}
        try:
            r = requests.post(url, json=payload, headers=self.get_headers(), timeout=15)
            return r.json()
        except Exception as e:
            return None

    def admin_storage_list(self):
        url = f"{self.host}/api/admin/storage/list"
        try:
            r = requests.get(url, headers=self.get_headers())
            return r.json()
        except: return None

# Singleton
alist_mgr = AListManager()
