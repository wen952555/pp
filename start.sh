
#!/bin/bash
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}正在启动服务 (PM2)...${NC}"

# Check PM2
if ! command -v pm2 >/dev/null 2>&1; then npm install pm2 -g; fi

# Stop existing
pm2 stop all >/dev/null 2>&1
pm2 delete all >/dev/null 2>&1

# --- DNS FIX START ---
# Fix typical Termux DNS issue where it points to local IPv6 which fails for static Go binaries
# Termux usually has PREFIX set. If not, try to guess.
if [ -z "$PREFIX" ]; then
    PREFIX="/data/data/com.termux/files/usr"
fi

RESOLV_CONF="$PREFIX/etc/resolv.conf"

# Check if we can write to it
if [ -d "$(dirname "$RESOLV_CONF")" ]; then
    DNS_NEEDS_FIX=false
    
    if [ ! -f "$RESOLV_CONF" ]; then
        DNS_NEEDS_FIX=true
    elif grep -q "::1" "$RESOLV_CONF"; then
        DNS_NEEDS_FIX=true
    fi

    if [ "$DNS_NEEDS_FIX" = true ]; then
        echo -e "${YELLOW}🔧 正在修复 Termux DNS 配置 (使用 8.8.8.8)...${NC}"
        # Backup if exists
        if [ -f "$RESOLV_CONF" ]; then cp "$RESOLV_CONF" "${RESOLV_CONF}.bak"; fi
        
        # Overwrite with reliable DNS
        echo "nameserver 8.8.8.8" > "$RESOLV_CONF"
        echo "nameserver 1.1.1.1" >> "$RESOLV_CONF"
    fi
fi
# --- DNS FIX END ---

# 1. Start Cloudflared Tunnel (if installed)
if [ -f "./cloudflared" ]; then
    echo -e "${GREEN}配置 Cloudflare Tunnel...${NC}"
    # Clear previous log
    rm -f cf_tunnel.log
    touch cf_tunnel.log
    
    # Create a wrapper script to handle retries and prevent PM2 crash loops
    cat > run_tunnel.sh <<EOF
#!/bin/bash
echo "--- Starting Tunnel Wrapper ---"
# Force Go DNS resolver to avoid cgo issues on Android
export GODEBUG=netdns=go

while true; do
    echo "[Wrapper] Starting cloudflared..."
    # 1. Use 127.0.0.1 instead of localhost
    # 2. --edge-ip-version 4: Force IPv4 for edge connection
    # 3. --protocol http2: Most stable on Android
    ./cloudflared tunnel --url http://127.0.0.1:8080 --protocol http2 --edge-ip-version 4 --no-autoupdate --logfile ./cf_tunnel.log
    
    echo "[Wrapper] Cloudflared exited. Sleeping 10s before retry..."
    sleep 10
done
EOF
    chmod +x run_tunnel.sh

    echo -e "${GREEN}启动 Cloudflare Tunnel (Wrapper)...${NC}"
    pm2 start ./run_tunnel.sh --name "cf-tunnel"
    
    echo -e "${CYAN}⏳ 等待隧道建立 (5秒)...${NC}"
    sleep 5
else
    echo -e "${YELLOW}⚠️ 未找到 Cloudflared，将只使用局域网IP${NC}"
fi

# 2. Start AList
if [ -f "./alist" ]; then
    echo -e "${GREEN}启动 AList Server...${NC}"
    pm2 start ./alist --name "alist" -- server
else
    echo -e "${YELLOW}⚠️ 未找到 AList 可执行文件${NC}"
fi

# 3. Start Bot
echo -e "${GREEN}启动 Telegram Bot...${NC}"
pm2 start bot.py --name "pikpak-bot" --interpreter python --log ./bot.log

# Save PM2 list for auto-resurrect
pm2 save

# Auto-start setup
BASHRC="$HOME/.bashrc"
if ! grep -q "pm2 resurrect" "$BASHRC"; then
    echo -e "\n# Auto-start PM2" >> "$BASHRC"
    echo "pm2 resurrect >> /dev/null 2>&1" >> "$BASHRC"
fi

echo -e "\n${GREEN}====================================${NC}"
echo -e "   🚀 所有服务已启动"
echo -e "${GREEN}====================================${NC}"
echo -e "🤖 Bot 状态: ${CYAN}pm2 log pikpak-bot${NC}"
echo -e "🌐 隧道日志: ${CYAN}tail -f cf_tunnel.log${NC}"
echo -e "🗂️ AList: ${CYAN}http://127.0.0.1:5244${NC}"
echo -e "\n⚠️ 请在 Telegram Bot 中发送 /start 查看获取到的域名状态"
