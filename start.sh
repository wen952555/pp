
#!/bin/bash
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}正在启动服务 (PM2)...${NC}"

# Check PM2
if ! command -v pm2 >/dev/null 2>&1; then npm install pm2 -g; fi

# Stop existing
pm2 stop all >/dev/null 2>&1
pm2 delete all >/dev/null 2>&1

# 1. Start Cloudflared Tunnel (if installed)
if [ -f "./cloudflared" ]; then
    echo -e "${GREEN}启动 Cloudflare Tunnel...${NC}"
    # Reset log file
    echo "" > cf_tunnel.log
    # Run cloudflared, exposing port 8080 (Bot Web Server)
    # We use 'script' to trick cloudflared line buffering if needed, or just standard redirection
    pm2 start "./cloudflared tunnel --url http://localhost:8080 --logfile ./cf_tunnel.log" --name "cf-tunnel"
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

# Save
pm2 save

# Auto-start
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
