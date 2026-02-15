
import socket
import os
import logging

logger = logging.getLogger("Utils")

def get_local_ip():
    """Get local IP using socket which is more robust on Android/Termux"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Connect to a public DNS server (doesn't actually send data)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def get_base_url(port):
    """
    Returns the Local IP URL.
    Tunnel logic has been removed.
    """
    local_ip = get_local_ip()
    return f"http://{local_ip}:{port}"

def is_rate_limited(user_data, limit=0.5):
    """Simple rate limiter to prevent spamming"""
    import time
    now = time.time()
    last = user_data.get('last_interaction', 0)
    if now - last < limit:
        return True
    user_data['last_interaction'] = now
    return False

def format_bytes(size):
    if not size: return "0 B"
    try: size = int(size)
    except: return "0 B"
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"
