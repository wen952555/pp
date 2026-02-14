#!/bin/bash
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}正在配置 PM2 进程守护...${NC}"

# Check if PM2 is installed
if ! command -v pm2 >/dev/null 2>&1; then
    echo "PM2 未安装，正在尝试安装..."
    npm install pm2 -g
fi

# Stop existing instance if running
pm2 stop pikpak-bot >/dev/null 2>&1
pm2 delete pikpak-bot >/dev/null 2>&1

# Start Bot with Python Interpreter
echo -e "${GREEN}启动机器人...${NC}"
pm2 start bot.py --name "pikpak-bot" --interpreter python --log ./bot.log

# Save PM2 list
pm2 save

# Configure Auto-Start for Termux
# Termux doesn't have systemd, so we add 'pm2 resurrect' to .bashrc
# This ensures bot starts when you open Termux app
BASHRC="$HOME/.bashrc"
if ! grep -q "pm2 resurrect" "$BASHRC"; then
    echo -e "\n# Auto-start PM2 processes" >> "$BASHRC"
    echo "pm2 resurrect >> /dev/null 2>&1" >> "$BASHRC"
    echo -e "${GREEN}[+] 已添加到自启动 (.bashrc)${NC}"
else
    echo -e "${GREEN}[-] 自启动已配置${NC}"
fi

echo -e "\n${GREEN}====================================${NC}"
echo -e "   🤖 机器人已在后台运行！"
echo -e "${GREEN}====================================${NC}"
echo -e "常用命令:"
echo -e "• 查看日志: ${CYAN}pm2 logs pikpak-bot${NC}"
echo -e "• 停止机器人: ${CYAN}pm2 stop pikpak-bot${NC}"
echo -e "• 重启机器人: ${CYAN}pm2 restart pikpak-bot${NC}"
echo -e "• 查看状态: ${CYAN}pm2 status${NC}"
