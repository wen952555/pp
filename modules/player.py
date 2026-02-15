
from aiohttp import web
from .config import WEB_PORT, logger
from .accounts import account_mgr
from .utils import get_local_ip, get_base_url

async def handle_player(request):
    file_id = request.query.get('id')
    user_id = request.query.get('user')
    
    if not file_id or not user_id:
        return web.Response(text="Missing parameters", status=400)

    client = await account_mgr.get_client(user_id)
    if not client:
        return web.Response(text="Bot not logged in", status=500)

    try:
        data = await client.get_download_url(file_id)
        video_url = data.get('url')
        filename = data.get('name', 'Video')
        
        if not video_url:
            return web.Response(text="Could not get link (File might be processing)", status=404)

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{filename}</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ margin: 0; background: #0d1117; color: #c9d1d9; font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; }}
                video {{ width: 100%; max-width: 1024px; max-height: 80vh; box-shadow: 0 0 20px rgba(0,0,0,0.5); }}
                .info {{ padding: 20px; text-align: center; }}
                a {{ color: #58a6ff; text-decoration: none; border: 1px solid #30363d; padding: 8px 16px; border-radius: 6px; background: #21262d; }}
                a:hover {{ background: #30363d; }}
            </style>
        </head>
        <body>
            <video controls autoplay playsinline>
                <source src="{video_url}" type="video/mp4">
                <source src="{video_url}" type="video/mkv">
                Your browser does not support the video tag.
            </video>
            <div class="info">
                <h3>{filename}</h3>
                <p><a href="{video_url}">💾 下载直链 / 调用外部播放器</a></p>
            </div>
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
