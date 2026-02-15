
from aiohttp import web
from .config import WEB_PORT, logger
from .accounts import account_mgr
from .utils import get_local_ip, get_base_url
import urllib.parse

async def handle_player(request):
    file_id = request.query.get('id')
    user_id = request.query.get('user')
    
    if not file_id or not user_id:
        return web.Response(text="Missing parameters", status=400)

    client = await account_mgr.get_client(user_id)
    if not client:
        return web.Response(text="Bot not logged in. Please restart bot or login.", status=500)

    try:
        data = await client.get_download_url(file_id)
        video_url = data.get('url')
        filename = data.get('name', 'Video')
        
        if not video_url:
            return web.Response(text="Could not get link (File might be processing or token expired).", status=404)

        # URL Encode for intent links
        encoded_url = urllib.parse.quote(video_url)
        encoded_name = urllib.parse.quote(filename)

        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{filename}</title>
            <style>
                :root {{ --primary: #007AFF; --bg: #000; --surface: #1C1C1E; --text: #FFF; }}
                body {{ margin: 0; background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; display: flex; flex-direction: column; align-items: center; min-height: 100vh; }}
                
                .video-container {{ width: 100%; max-width: 1200px; background: #000; position: sticky; top: 0; z-index: 10; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }}
                video {{ width: 100%; aspect-ratio: 16/9; display: block; }}
                
                .content {{ padding: 20px; width: 100%; max-width: 800px; box-sizing: border-box; }}
                h1 {{ font-size: 1.2rem; margin: 0 0 15px 0; font-weight: 600; line-height: 1.4; word-break: break-all; }}
                
                .btn-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }}
                .btn {{ background: var(--surface); color: var(--text); border: none; padding: 12px; border-radius: 10px; font-size: 14px; font-weight: 500; cursor: pointer; text-decoration: none; text-align: center; display: flex; align-items: center; justify-content: center; gap: 8px; transition: 0.2s; }}
                .btn:active {{ transform: scale(0.98); opacity: 0.8; }}
                .btn.primary {{ background: var(--primary); }}
                
                .section-title {{ font-size: 0.8rem; text-transform: uppercase; color: #888; margin-bottom: 10px; letter-spacing: 1px; }}
                
                .toast {{ position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(255,255,255,0.9); color: #000; padding: 10px 20px; border-radius: 20px; font-size: 14px; opacity: 0; transition: 0.3s; pointer-events: none; }}
                .toast.show {{ opacity: 1; bottom: 30px; }}

                /* Icons */
                .icon {{ width: 18px; height: 18px; fill: currentColor; }}
            </style>
        </head>
        <body>
            <div class="video-container">
                <video controls autoplay playsinline preload="metadata">
                    <source src="{video_url}" type="video/mp4">
                    <source src="{video_url}" type="video/mkv">
                    <source src="{video_url}" type="video/webm">
                    Your browser does not support HTML5 video.
                </video>
            </div>

            <div class="content">
                <h1>{filename}</h1>

                <div class="section-title">Actions</div>
                <div class="btn-grid">
                    <a href="{video_url}" class="btn primary" download>
                        💾 Download
                    </a>
                    <button class="btn" onclick="copyLink()">
                        📋 Copy Link
                    </button>
                </div>

                <div class="section-title">Open in Player</div>
                <div class="btn-grid">
                    <a href="vlc://{video_url}" class="btn">🧡 VLC</a>
                    <a href="nplayer-{video_url}" class="btn">▶️ nPlayer</a>
                    <a href="intent:{video_url}#Intent;package=com.mxtech.videoplayer.ad;S.title={encoded_name};end" class="btn">💙 MX Player</a>
                    <a href="potplayer://{video_url}" class="btn">💛 PotPlayer</a>
                    <a href="iina://weblink?url={encoded_url}" class="btn">🌀 IINA</a>
                    <a href="infuse://x-callback-url/play?url={encoded_url}" class="btn">🧡 Infuse</a>
                </div>
            </div>

            <div id="toast" class="toast">Link Copied!</div>

            <script>
                function copyLink() {{
                    const url = "{video_url}";
                    navigator.clipboard.writeText(url).then(() => {{
                        showToast();
                    }}).catch(err => {{
                        // Fallback
                        const input = document.createElement('textarea');
                        input.value = url;
                        document.body.appendChild(input);
                        input.select();
                        document.execCommand('copy');
                        document.body.removeChild(input);
                        showToast();
                    }});
                }}

                function showToast() {{
                    const t = document.getElementById('toast');
                    t.classList.add('show');
                    setTimeout(() => t.classList.remove('show'), 2000);
                }}
            </script>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html')
    except Exception as e:
        return web.Response(text=f"Server Error: {e}", status=500)

async def start_web_server():
    app = web.Application()
    app.router.add_get('/play', handle_player)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', WEB_PORT)
    await site.start()
    
    # Try to identify URL immediately for logs
    base_url = get_base_url(WEB_PORT)
    logger.info(f"Web Player Server started. Access at: {base_url}/play?id=... (Check cf_tunnel.log for public URL if different)")
