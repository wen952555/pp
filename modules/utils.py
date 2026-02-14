
import netifaces
import re

# Try importing yt_dlp
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False

def get_local_ip():
    try:
        gws = netifaces.gateways()
        default_iface = gws['default'][netifaces.AF_INET][1]
        ip_info = netifaces.ifaddresses(default_iface)[netifaces.AF_INET][0]
        return ip_info['addr']
    except:
        return "127.0.0.1"

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
