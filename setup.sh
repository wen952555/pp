
#!/bin/bash

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}    AList Termux Bot + Streaming 部署    ${NC}"
echo -e "${GREEN}=========================================${NC}"

# Define Config Path
ENV_FILE="../.env"

# 1. Update packages
echo -e "\n${CYAN}[1/7] 检查系统环境...${NC}"
pkg update -y || termux-change-repo

# 2. Install Python & Node.js
echo -e "\n${CYAN}[2/7] 安装运行环境...${NC}"
if ! command -v python >/dev/null 2>&1; then pkg install python -y; fi
if ! command -v node >/dev/null 2>&1; then pkg install nodejs -y; fi

# 3. Install System Tools (Ensure FFmpeg is installed for streaming)
echo -e "\n${CYAN}[3/7] 安装系统工具...${NC}"
for pkg in git ffmpeg aria2 wget tar proot ca-certificates; do
    if ! command -v $pkg >/dev/null 2>&1 && [ "$pkg" != "ca-certificates" ]; then
        echo -e "${GREEN}[+] 安装 $pkg...${NC}"
        pkg install $pkg -y
    elif [ "$pkg" == "ca-certificates" ] && [ ! -f "$PREFIX/etc/tls/cert.pem" ]; then
        echo -e "${GREEN}[+] 安装 $pkg...${NC}"
        pkg install $pkg -y
    fi
done

if ! command -v pm2 >/dev/null 2>&1; then
    echo -e "${GREEN}[+] 安装 PM2...${NC}"
    npm install pm2 -g
fi

# 4. Install AList
echo -e "\n${CYAN}[4/7] 安装 AList...${NC}"
if [ -f "alist" ]; then
    echo -e "${GREEN}[-] AList 已安装${NC}"
else
    echo -e "${YELLOW}正在下载 AList (Android/Arm64)...${NC}"
    wget https://github.com/alist-org/alist/releases/latest/download/alist-android-arm64.tar.gz -O alist.tar.gz
    if [ $? -eq 0 ]; then
        tar -zxvf alist.tar.gz
        rm alist.tar.gz
        chmod +x alist
        echo -e "${GREEN}[+] AList 安装成功${NC}"
    else
        echo -e "${RED}❌ AList 下载失败，请检查网络 (Github连接)${NC}"
    fi
fi

# 5. Install Cloudflared
echo -e "\n${CYAN}[5/7] 安装 Cloudflare Tunnel...${NC}"
if [ -f "cloudflared" ]; then
    echo -e "${GREEN}[-] Cloudflared 已安装${NC}"
else
    echo -e "${YELLOW}正在下载 Cloudflared (Linux/Arm64)...${NC}"
    wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64 -O cloudflared
    if [ $? -eq 0 ]; then
        chmod +x cloudflared
        echo -e "${GREEN}[+] Cloudflared 安装成功${NC}"
    else
        echo -e "${RED}❌ Cloudflared 下载失败，请手动下载。${NC}"
    fi
fi

# 6. Install Python Dependencies
echo -e "\n${CYAN}[6/7] 安装 Python 依赖...${NC}"
pip install -r requirements.txt

# 7. Configuration
echo -e "\n${CYAN}[7/7] 配置 Bot 信息${NC}"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}请输入以下信息:${NC}"
    read -p "Telegram Bot Token: " BOT_TOKEN
    read -p "Telegram Admin ID (数字ID): " ADMIN_ID
    
    # Defaults for AList
    echo "BOT_TOKEN=$BOT_TOKEN" >> "$ENV_FILE"
    echo "ADMIN_ID=$ADMIN_ID" >> "$ENV_FILE"
    echo "ALIST_HOST=http://127.0.0.1:5244" >> "$ENV_FILE"
    echo "ALIST_USER=admin" >> "$ENV_FILE"
    echo "ALIST_PASS=123456" >> "$ENV_FILE"
fi

# Finalize
echo -e "\n${CYAN}设置完成${NC}"
chmod +x start.sh
mkdir -p downloads

# Generate AList password once
if [ -f "alist" ]; then
    echo -e "${YELLOW}正在初始化 AList 密码...${NC}"
    ./alist admin set 123456 >/dev/null 2>&1
    echo -e "${GREEN}✅ AList 初始密码已重置为: 123456${NC}"
    echo -e "${GREEN}   (默认用户: admin, 默认密码: 123456)${NC}"
fi

echo -e "\n${GREEN}=========================================${NC}"
echo -e "${GREEN}   ✅ 部署成功!   ${NC}"
echo -e "请运行 ${CYAN}./start.sh${NC} 启动所有服务。"
