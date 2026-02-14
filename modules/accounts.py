
import os
import json
from .config import ACCOUNTS_FILE, logger

PIKPAK_AVAILABLE = True
try:
    from pikpakapi import PikPakApi
except ImportError:
    PIKPAK_AVAILABLE = False
    logger.warning("pikpakapi library not found.")

class AccountManager:
    def __init__(self):
        self.accounts = {}  # {username: password}
        self.clients = {}   # {username: PikPakApi}
        self.active_user_map = {} # {tg_user_id: username}
        self.load_accounts()
        
        # Load from Env
        env_user = os.getenv("PIKPAK_USER")
        env_pass = os.getenv("PIKPAK_PASS")
        if env_user and env_pass:
            self.add_account_credentials(env_user, env_pass)

    def load_accounts(self):
        if os.path.exists(ACCOUNTS_FILE):
            try:
                with open(ACCOUNTS_FILE, 'r') as f:
                    self.accounts = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load accounts: {e}")

    def save_accounts(self):
        try:
            with open(ACCOUNTS_FILE, 'w') as f:
                json.dump(self.accounts, f)
        except Exception as e:
            logger.error(f"Failed to save accounts: {e}")

    def add_account_credentials(self, u, p):
        self.accounts[u] = p
        self.save_accounts()

    def remove_account(self, u):
        if u in self.accounts:
            del self.accounts[u]
            if u in self.clients:
                del self.clients[u]
            # Reset active user map
            for uid, user in list(self.active_user_map.items()):
                if user == u:
                    del self.active_user_map[uid]
            self.save_accounts()
            return True
        return False

    def get_accounts_list(self):
        return list(self.accounts.keys())

    async def get_client(self, tg_user_id, specific_username=None, force_refresh=False):
        """
        Get or create authenticated client.
        :param force_refresh: If True, forces a re-login (useful for expired tokens)
        """
        if not PIKPAK_AVAILABLE: 
            logger.error("PikPak API library not installed.")
            return None
        
        username = specific_username
        if not username:
            # Determine active username
            username = self.active_user_map.get(str(tg_user_id))
            if not username:
                if self.accounts:
                    username = list(self.accounts.keys())[0]
                    self.active_user_map[str(tg_user_id)] = username
                else:
                    return None
        
        # Check cache unless forcing refresh
        if not force_refresh and username in self.clients:
            return self.clients[username]
        
        # Login new session
        password = self.accounts.get(username)
        if not password: return None

        try:
            logger.info(f"Logging in for {username} (Refresh: {force_refresh})...")
            client = PikPakApi(username=username, password=password)
            await client.login()
            self.clients[username] = client
            return client
        except Exception as e:
            logger.error(f"Login failed for {username}: {e}")
            return None

    async def switch_account(self, tg_user_id, target_username):
        if target_username in self.accounts:
            self.active_user_map[str(tg_user_id)] = target_username
            # Warm up connection with force refresh to ensure it works
            client = await self.get_client(tg_user_id, force_refresh=True)
            return client is not None
        return False

# Singleton Instance
account_mgr = AccountManager()
