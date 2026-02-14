#!/bin/bash

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}    PikPak Termux Bot - 旗舰版部署      ${NC}"
echo -e "${GREEN}=========================================${NC}"

# 1. Update packages
echo -e "\n${CYAN}[1/5] 检查系统环境...${NC}"
pkg update -y

# 2. Install Python
if ! command -v python >/dev/null 2>&1; then
    echo -e "${GREEN}[+] 安装 Python...${NC}"
    pkg install python -y
else
    echo -e "${GREEN}[-] Python 已安装${NC}"
fi

# 3. Install System Tools (Git, FFmpeg, Aria2)
echo -e "\n${CYAN}[2/5] 安装系统工具...${NC}"

if ! command -v git >/dev/null 2>&1; then
    pkg install git -y
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo -e "${GREEN}[+] 安装 FFmpeg (媒体解析)...${NC}"
    pkg install ffmpeg -y
fi

if ! command -v aria2c >/dev/null 2>&1; then
    echo -e "${GREEN}[+] 安装 Aria2 (本地高速下载)...${NC}"
    pkg install aria2 -y
else
    echo -e "${GREEN}[-] Aria2 已安装${NC}"
fi

# 4. Install Dependencies
echo -e "\n${CYAN}[3/5] 安装 Python 依赖...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# 5. Interactive Configuration
echo -e "\n${CYAN}[4/5] 配置 Bot 信息${NC}"
if [ -f ".env" ]; then
    echo -e "${YELLOW}检测到已存在配置文件 .env${NC}"
    read -p "是否重新配置? (y/n): " reconfig
    if [[ "$reconfig" != "y" ]]; then
        echo "跳过配置步骤..."
    else
        rm .env
    fi
fi

if [ ! -f ".env" ]; then
    echo -e "${YELLOW}请输入以下信息 (输入后回车):${NC}"
    
    read -p "Telegram Bot Token: " BOT_TOKEN
    read -p "Telegram Admin ID (数字ID): " ADMIN_ID
    read -p "PikPak 用户名/邮箱: " PIKPAK_USER
    read -p "PikPak 密码: " PIKPAK_PASS

    echo "BOT_TOKEN=$BOT_TOKEN" >> .env
    echo "ADMIN_ID=$ADMIN_ID" >> .env
    echo "PIKPAK_USER=$PIKPAK_USER" >> .env
    echo "PIKPAK_PASS=$PIKPAK_PASS" >> .env
    
    echo -e "${GREEN}[+] 配置文件 .env 已生成!${NC}"
fi

# 6. Set permissions
echo -e "\n${CYAN}[5/5] 设置运行权限...${NC}"
chmod +x start.sh

# Create download folder
mkdir -p downloads

echo -e "\n${GREEN}=========================================${NC}"
echo -e "${GREEN}   ✅ 部署完成!   ${NC}"
echo -e "${GREEN}=========================================${NC}"
echo -e "输入 ${CYAN}./start.sh${NC} 即可启动机器人。"
echo -e "功能: 批量离线、本地下载(Aria2)、文件管理(/ls, /rename)、直链提取。"
