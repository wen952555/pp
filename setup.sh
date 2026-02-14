#!/bin/bash

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}    PikPak Termux Bot - 部署脚本        ${NC}"
echo -e "${GREEN}=========================================${NC}"

# Define Config Path (Parent Directory)
ENV_FILE="../.env"

# 1. Update packages
echo -e "\n${CYAN}[1/6] 检查系统环境...${NC}"
# Attempt to fix repo issues automatically if update fails
pkg update -y || termux-change-repo

# 2. Install Python & Node.js (for PM2)
echo -e "\n${CYAN}[2/6] 安装运行环境 (Python & Node.js)...${NC}"
if ! command -v python >/dev/null 2>&1; then
    pkg install python -y
fi
if ! command -v node >/dev/null 2>&1; then
    echo -e "${GREEN}[+] 安装 Node.js (用于 PM2 管理)...${NC}"
    pkg install nodejs -y
fi

# 3. Install System Tools (Git, FFmpeg, Aria2, PM2)
echo -e "\n${CYAN}[3/6] 安装系统工具...${NC}"

if ! command -v git >/dev/null 2>&1; then
    pkg install git -y
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo -e "${GREEN}[+] 安装 FFmpeg...${NC}"
    pkg install ffmpeg -y
fi

if ! command -v aria2c >/dev/null 2>&1; then
    echo -e "${GREEN}[+] 安装 Aria2...${NC}"
    pkg install aria2 -y
fi

if ! command -v pm2 >/dev/null 2>&1; then
    echo -e "${GREEN}[+] 安装 PM2 进程管理器...${NC}"
    npm install pm2 -g
else
    echo -e "${GREEN}[-] PM2 已安装${NC}"
fi

# 4. Install Python Dependencies
echo -e "\n${CYAN}[4/6] 安装 Python 依赖...${NC}"
echo -e "${YELLOW}正在清理缓存并安装依赖，请耐心等待...${NC}"
# Note: Use --no-cache-dir to avoid using cached git refs from failed attempts
pip install --no-cache-dir -r requirements.txt

if [ $? -ne 0 ]; then
    echo -e "\n${RED}❌ 依赖安装失败！${NC}"
    echo -e "${YELLOW}可能原因：${NC}"
    echo -e "1. GitHub 仓库连接失败 (网络问题或仓库不存在)"
    echo -e "2. Python 环境问题"
    echo -e "\n${CYAN}尝试解决方案：${NC}"
    echo -e "• 编辑 requirements.txt 更换 git 仓库地址"
    echo -e "• 手动运行: pip install -r requirements.txt"
    exit 1
fi

# 5. Interactive Configuration
echo -e "\n${CYAN}[5/6] 配置 Bot 信息${NC}"
echo -e "配置文件路径: ${YELLOW}$ENV_FILE${NC}"

if [ -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}检测到已有配置文件。${NC}"
    read -p "是否重新配置? (y/n): " reconfig
    if [[ "$reconfig" == "y" ]]; then
        rm "$ENV_FILE"
    else
        echo "跳过配置..."
    fi
fi

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}请输入以下信息:${NC}"
    
    read -p "Telegram Bot Token: " BOT_TOKEN
    read -p "Telegram Admin ID (数字ID): " ADMIN_ID
    read -p "PikPak 用户名/邮箱: " PIKPAK_USER
    read -p "PikPak 密码: " PIKPAK_PASS

    echo "BOT_TOKEN=$BOT_TOKEN" >> "$ENV_FILE"
    echo "ADMIN_ID=$ADMIN_ID" >> "$ENV_FILE"
    echo "PIKPAK_USER=$PIKPAK_USER" >> "$ENV_FILE"
    echo "PIKPAK_PASS=$PIKPAK_PASS" >> "$ENV_FILE"
    
    echo -e "${GREEN}[+] 配置文件已生成${NC}"
fi

# 6. Finalize
echo -e "\n${CYAN}[6/6] 设置完成${NC}"
chmod +x start.sh
mkdir -p downloads

echo -e "\n${GREEN}=========================================${NC}"
echo -e "${GREEN}   ✅ 部署成功!   ${NC}"
echo -e "${GREEN}=========================================${NC}"
echo -e "请运行 ${CYAN}./start.sh${NC} 启动机器人 (包含自动后台运行配置)。"
