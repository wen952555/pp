
#!/bin/bash
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}正在启动服务 (PM2)...${NC}"

# Check PM2
if ! command -v pm2 >/dev/null 2>&1; then npm install pm2 -g; fi

# Check & Install Proot (Crucial for unpatched binaries like cloudflared to find /etc/resolv.conf)
if ! command -v termux-chroot >/dev/null 2>&1; then
    echo -e "${YELLOW}正在安装 proot (用于解决 DNS 路径问题)...${NC}"
    pkg install proot -y
fi

# Check & Install CA Certificates (Crucial for SSL connections)
if [ ! -f "$PREFIX/etc/tls/cert.pem" ]; then
    echo -e "${YELLOW}正在安装 ca-certificates (用于解决 SSL 证书问题)...${NC}"
    pkg install ca-certificates -y
fi

# Stop existing
pm2 stop all >/dev/null 2>&1
pm2 delete all >/dev/null 2>&1

# --- DNS FIX START ---
# Force rewrite of resolv.conf to ensure we have a working resolver accessible inside proot
if [ -z "$PREFIX" ]; then PREFIX="/data/data/com.termux/files/usr"; fi
RESOLV_CONF="$PREFIX/etc/resolv.conf"

if [ -d "$(dirname "$RESOLV_CONF")" ]; then
    echo -e "${YELLOW}🔧 强制配置 DNS (8.8.8.8)...${NC}"
    # Backup if exists and not already backed up
    if [ -f "$RESOLV_CONF" ] && [ ! -f "${RESOLV_CONF}.bak" ]; then 
        cp "$RESOLV_CONF" "${RESOLV_CONF}.bak"
    fi
    # Overwrite with reliable IPv4 DNS
    echo "nameserver 8.8.8.8" > "$RESOLV_CONF"
    echo "nameserver 1.1.1.1" >> "$RESOLV_CONF"
fi
# --- DNS FIX END ---

# 1. Start Cloudflared Tunnel (if installed)
if [ -f "./cloudflared" ]; then
    echo -e "${GREEN}配置 Cloudflare Tunnel...${NC}"
    rm -f cf_tunnel.log
    touch cf_tunnel.log
    
    # Create a wrapper script
    # We uses `termux-chroot` to map $PREFIX/etc/resolv.conf to /etc/resolv.conf
    # This allows the standard linux cloudflared binary to resolve domains correctly.
    cat > run_tunnel.sh <<EOF
#!/bin/bash
echo "--- Starting Tunnel Wrapper ---"
export GODEBUG=netdns=go
# Point Cloudflared to the Termux certificate bundle (mapped to /etc/... by termux-chroot)
export SSL_CERT_FILE=/etc/tls/cert.pem

while true; do
    echo "[Wrapper] Starting cloudflared with termux-chroot..."
    # Using --protocol http2 to avoid "QUIC stream timeout" errors common on mobile networks
    
    termux-chroot ./cloudflared tunnel --url http://127.0.0.1:8080 --protocol http2 --edge-ip-version 4 --no-autoupdate --logfile ./cf_tunnel.log
    
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

# Save PM2 list
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

# Extract URL
TUNNEL_URL=""
if [ -f "cf_tunnel.log" ]; then
    # Try to find the URL in the logs
    TUNNEL_URL=$(grep -o 'https://.*\.trycloudflare\.com' cf_tunnel.log | head -n 1)
fi

echo -e "🤖 Bot 状态: ${CYAN}pm2 log pikpak-bot${NC}"
echo -e "🌐 隧道日志: ${CYAN}tail -f cf_tunnel.log${NC}"
echo -e "🗂️ AList: ${CYAN}http://127.0.0.1:5244${NC}"

if [ -n "$TUNNEL_URL" ]; then
    echo -e "\n${GREEN}✅ 隧道建立成功!${NC}"
    echo -e "🔗 公网访问地址: ${YELLOW}$TUNNEL_URL${NC}"
else
    echo -e "\n${YELLOW}⏳ 正在获取公网地址 (请稍后在 Telegram Bot 中输入 /start 查看)${NC}"
fi

echo -e "\n⚠️ 如果 Bot 无响应，请使用 'pm2 log pikpak-bot' 查看报错。"
