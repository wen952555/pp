
#!/bin/bash
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}正在启动服务 (PM2)...${NC}"

# Check PM2
if ! command -v pm2 >/dev/null 2>&1; then npm install pm2 -g; fi

# Check & Install Proot
if ! command -v termux-chroot >/dev/null 2>&1; then
    echo -e "${YELLOW}正在安装 proot (用于解决 DNS 路径问题)...${NC}"
    pkg install proot -y
fi

# Check & Install CA Certificates
if [ ! -f "$PREFIX/etc/tls/cert.pem" ]; then
    echo -e "${YELLOW}正在安装 ca-certificates (用于解决 SSL 证书问题)...${NC}"
    pkg install ca-certificates -y
fi

# Ensure Dependencies
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt >/dev/null 2>&1
fi

# Stop existing
pm2 stop all >/dev/null 2>&1
pm2 delete all >/dev/null 2>&1

# --- DNS FIX START ---
if [ -z "$PREFIX" ]; then PREFIX="/data/data/com.termux/files/usr"; fi
RESOLV_CONF="$PREFIX/etc/resolv.conf"

if [ -d "$(dirname "$RESOLV_CONF")" ]; then
    echo -e "${YELLOW}🔧 强制配置 DNS (8.8.8.8)...${NC}"
    if [ -f "$RESOLV_CONF" ] && [ ! -f "${RESOLV_CONF}.bak" ]; then 
        cp "$RESOLV_CONF" "${RESOLV_CONF}.bak"
    fi
    echo "nameserver 8.8.8.8" > "$RESOLV_CONF"
    echo "nameserver 1.1.1.1" >> "$RESOLV_CONF"
fi
# --- DNS FIX END ---

# 1. Start AList
if [ -f "./alist" ]; then
    echo -e "${GREEN}启动 AList Server...${NC}"
    pm2 start ./alist --name "alist" -- server
else
    echo -e "${YELLOW}⚠️ 未找到 AList 可执行文件${NC}"
fi

# 2. Start Bot
echo -e "${GREEN}启动 Telegram Bot...${NC}"
pm2 start bot.py --name "alist-bot" --interpreter python --log ./bot.log

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

echo -e "🤖 Bot 状态: ${CYAN}pm2 log alist-bot${NC}"
echo -e "🗂️ AList: ${CYAN}http://127.0.0.1:5244${NC}"
echo -e "${YELLOW}⚠️ 已移除隧道，Web 播放仅支持局域网访问。${NC}"
