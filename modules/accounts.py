
import requests
import logging
import json
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
        return {"Authorization": self.token, "Content-Type": "application/json"}

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
        url = f"{self.host}/api/fs/get"
        payload = {"path": path, "password": ""}
        try:
            r = requests.post(url, json=payload, headers=self.get_headers(), timeout=15)
            return r.json()
        except Exception as e:
            return None

    # --- File Management APIs ---

    def fs_mkdir(self, path):
        """Create directory"""
        url = f"{self.host}/api/fs/mkdir"
        payload = {"path": path}
        try:
            r = requests.post(url, json=payload, headers=self.get_headers())
            return r.json()
        except Exception as e: return {"code": 500, "message": str(e)}

    def fs_rename(self, path, name):
        """Rename file/folder"""
        url = f"{self.host}/api/fs/rename"
        payload = {"path": path, "name": name}
        try:
            r = requests.post(url, json=payload, headers=self.get_headers())
            return r.json()
        except Exception as e: return {"code": 500, "message": str(e)}

    def fs_remove(self, names: list, dir_path: str):
        """Delete files/folders"""
        url = f"{self.host}/api/fs/remove"
        payload = {"names": names, "dir": dir_path}
        try:
            r = requests.post(url, json=payload, headers=self.get_headers())
            return r.json()
        except Exception as e: return {"code": 500, "message": str(e)}

    def fs_move_copy(self, src_dir, dst_dir, names: list, action="move"):
        """Action: 'move' or 'copy'"""
        url = f"{self.host}/api/fs/{action}"
        payload = {"src_dir": src_dir, "dst_dir": dst_dir, "names": names}
        try:
            r = requests.post(url, json=payload, headers=self.get_headers())
            return r.json()
        except Exception as e: return {"code": 500, "message": str(e)}

    # --- Storage & Offline ---

    def admin_storage_list(self):
        url = f"{self.host}/api/admin/storage/list"
        try:
            r = requests.get(url, headers=self.get_headers())
            return r.json()
        except: return None

    def add_offline_download(self, url, path):
        """Add offline download task"""
        # Note: API format depends on AList version, trying standard
        api_url = f"{self.host}/api/fs/add_offline_download"
        # Often requires tool config (aria2/qbit). Simple implementation:
        payload = {
            "url": url,
            "path": path
        }
        try:
            r = requests.post(api_url, json=payload, headers=self.get_headers())
            return r.json()
        except Exception as e: return {"code": 500, "message": str(e)}
        
    def list_offline_tasks(self, status="downloading"):
         # This usually requires admin access to specific tools, 
         # generic task list endpoint might not be exposed easily in standard API 
         # without knowing the specific tool (aria2 etc). 
         # Skipping complex task list for now to avoid errors.
         return None

# Singleton
alist_mgr = AListManager()
