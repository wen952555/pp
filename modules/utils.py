
import socket
import re
import os
import logging
import time

logger = logging.getLogger("Utils")

# Try importing yt_dlp
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False

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
    Tries to find the Cloudflare Tunnel URL first.
    If not found, falls back to Local IP.
    """
    log_file = "cf_tunnel.log"
    
    # Try to find valid trycloudflare.com URL in logs
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                # Matches https://[random].trycloudflare.com
                matches = re.findall(r'(https://[a-zA-Z0-9-]+\.trycloudflare\.com)', content)
                
                if matches:
                    url = matches[-1] # Get the latest one
                    # logger.info(f"Found Cloudflare Tunnel: {url}")
                    return url
        except Exception as e:
            logger.error(f"Error reading tunnel log: {e}")
            pass
            
    # Fallback to local IP
    local_ip = get_local_ip()
    # logger.info(f"Using Local IP: {local_ip}")
    return f"http://{local_ip}:{port}"

def is_rate_limited(user_data, limit=0.8):
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

def extract_direct_url_with_ytdlp(url):
    """Extract real video URL from TikTok/Twitter/YouTube"""
    if not YTDLP_AVAILABLE: return None
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'simulate': True,
        'skip_download': True
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get('url', None)
    except:
        return None
