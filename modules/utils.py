
import socket
import re
import os
import logging
import time

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

# Cache for base URL to avoid reading file every request
_cached_url = None
_last_url_check = 0

def get_base_url(port):
    """
    Tries to find the Cloudflare Tunnel URL first.
    If not found, falls back to Local IP.
    Cached for 60 seconds.
    """
    global _cached_url, _last_url_check
    now = time.time()
    
    # Return cache if valid (60s)
    if _cached_url and (now - _last_url_check < 60):
        return _cached_url

    log_file = "cf_tunnel.log"
    found_url = None
    
    # Try to find valid trycloudflare.com URL in logs
    if os.path.exists(log_file):
        try:
            # Optimize: Read only last 10KB
            file_size = os.path.getsize(log_file)
            read_size = 1024 * 10
            
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                if file_size > read_size:
                    f.seek(file_size - read_size)
                content = f.read()
                
                # Matches https://[random].trycloudflare.com
                matches = re.findall(r'(https://[a-zA-Z0-9-]+\.trycloudflare\.com)', content)
                if matches:
                    found_url = matches[-1]
        except Exception:
            pass
            
    if found_url:
        _cached_url = found_url
    else:
        # Fallback
        local_ip = get_local_ip()
        _cached_url = f"http://{local_ip}:{port}"
    
    _last_url_check = now
    return _cached_url

def is_rate_limited(user_data, limit=0.5):
    """Simple rate limiter to prevent spamming"""
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
