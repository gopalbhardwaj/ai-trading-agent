# 🚀 Deployment Guide - AI Trading Agent

This guide covers deploying the AI Trading Agent for production use, including 24/7 operation, cloud deployment, and monitoring.

## 📋 Deployment Options

### Option 1: VPS/Cloud Server (Recommended)
- **Best for**: 24/7 trading, reliability, remote access
- **Platforms**: DigitalOcean, AWS EC2, Google Cloud, Linode, Vultr
- **Cost**: $5-20/month for basic VPS

### Option 2: Local Server/PC
- **Best for**: Testing, personal use, cost savings
- **Requirements**: Dedicated computer, stable internet
- **Considerations**: Power outages, internet issues

### Option 3: Cloud Platforms (Advanced)
- **AWS**: EC2 + RDS + CloudWatch
- **Google Cloud**: Compute Engine + Cloud SQL
- **Azure**: Virtual Machines + Azure Database

## 🖥️ VPS Deployment (Recommended)

### Step 1: Choose and Set Up VPS

#### Recommended Specifications:
- **CPU**: 1-2 cores
- **RAM**: 2-4GB
- **Storage**: 20GB SSD
- **OS**: Ubuntu 20.04/22.04 LTS
- **Bandwidth**: Unmetered or high limit

#### Popular VPS Providers:
1. **DigitalOcean**: $4-6/month, excellent documentation
2. **Linode**: $5/month, reliable performance
3. **Vultr**: $3.50-6/month, global locations
4. **AWS EC2**: Pay-as-you-go, enterprise features

### Step 2: Initial Server Setup

#### Connect to Your Server:
```bash
ssh root@your_server_ip
```

#### Update System:
```bash
apt update && apt upgrade -y
```

#### Create Non-Root User:
```bash
adduser trader
usermod -aG sudo trader
su - trader
```

#### Install Prerequisites:
```bash
sudo apt install -y python3 python3-pip python3-venv git nginx supervisor certbot
```

### Step 3: Deploy Application

#### Clone Repository:
```bash
cd /home/trader
git clone https://github.com/YOUR_USERNAME/ai-trading-agent.git
cd ai-trading-agent
```

#### Set Up Virtual Environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### Configure Environment:
```bash
cp .env.example .env
nano .env
```

Add your production configuration:
```env
# Zerodha Kite API Configuration
KITE_API_KEY=your_production_api_key
KITE_API_SECRET=your_production_api_secret

# Trading Configuration
MAX_DAILY_BUDGET=50000
RISK_PER_TRADE=0.01
MAX_POSITIONS=3

# Production Settings
DEBUG=false
LOG_LEVEL=INFO
USE_LIVE_DATA=true

# Telegram Notifications (Highly Recommended)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Database (Optional - for trade history)
DATABASE_URL=sqlite:///trades.db
```

### Step 4: Configure Process Management

#### Create Supervisor Configuration:
```bash
sudo nano /etc/supervisor/conf.d/trading-agent.conf
```

```ini
[program:trading-agent]
command=/home/trader/ai-trading-agent/venv/bin/python webapp.py
directory=/home/trader/ai-trading-agent
user=trader
autostart=true
autorestart=true
stderr_logfile=/var/log/trading-agent-error.log
stdout_logfile=/var/log/trading-agent.log
environment=PATH="/home/trader/ai-trading-agent/venv/bin"

[program:trading-engine]
command=/home/trader/ai-trading-agent/venv/bin/python main.py
directory=/home/trader/ai-trading-agent
user=trader
autostart=true
autorestart=true
stderr_logfile=/var/log/trading-engine-error.log
stdout_logfile=/var/log/trading-engine.log
environment=PATH="/home/trader/ai-trading-agent/venv/bin"
```

#### Update Supervisor:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start trading-agent
sudo supervisorctl start trading-engine
```

### Step 5: Configure Nginx (Reverse Proxy)

#### Create Nginx Configuration:
```bash
sudo nano /etc/nginx/sites-available/trading-agent
```

```nginx
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### Enable Site:
```bash
sudo ln -s /etc/nginx/sites-available/trading-agent /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Step 6: SSL Certificate (Optional but Recommended)

```bash
sudo certbot --nginx -d your-domain.com
```

### Step 7: Firewall Configuration

```bash
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

## 🐳 Docker Deployment (Alternative)

### Create Dockerfile:
```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "webapp.py"]
```

### Create docker-compose.yml:
```yaml
version: '3.8'

services:
  trading-agent:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./logs:/app/logs
      - ./.env:/app/.env
    restart: unless-stopped
    environment:
      - PYTHONUNBUFFERED=1

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - trading-agent
    restart: unless-stopped
```

### Deploy with Docker:
```bash
docker-compose up -d
```

## 📊 Monitoring and Maintenance

### Set Up Log Monitoring

#### Create Log Rotation:
```bash
sudo nano /etc/logrotate.d/trading-agent
```

```
/var/log/trading-*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 trader trader
    postrotate
        sudo supervisorctl restart trading-agent
        sudo supervisorctl restart trading-engine
    endscript
}
```

### Set Up Telegram Alerts

#### Create alert script:
```bash
nano /home/trader/alert.py
```

```python
#!/usr/bin/env python3
import requests
import sys

def send_alert(message):
    bot_token = "YOUR_BOT_TOKEN"
    chat_id = "YOUR_CHAT_ID"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": f"🚨 Trading Agent Alert: {message}",
        "parse_mode": "HTML"
    }
    
    requests.post(url, json=payload)

if __name__ == "__main__":
    send_alert(sys.argv[1] if len(sys.argv) > 1 else "System alert")
```

### Create Health Check Script:
```bash
nano /home/trader/health_check.sh
```

```bash
#!/bin/bash

# Check if webapp is running
if ! curl -f http://localhost:5000/health > /dev/null 2>&1; then
    echo "Webapp is down, restarting..."
    sudo supervisorctl restart trading-agent
    python3 /home/trader/alert.py "Webapp restarted due to health check failure"
fi

# Check if trading engine is running
if ! pgrep -f "main.py" > /dev/null; then
    echo "Trading engine is down, restarting..."
    sudo supervisorctl restart trading-engine
    python3 /home/trader/alert.py "Trading engine restarted due to health check failure"
fi
```

#### Set Up Cron Job:
```bash
crontab -e
```

Add:
```cron
# Health check every 5 minutes
*/5 * * * * /home/trader/health_check.sh

# Daily restart at 3 AM (optional)
0 3 * * * sudo supervisorctl restart trading-agent trading-engine

# Weekly server maintenance
0 4 * * 0 /home/trader/maintenance.sh
```

## 🔒 Security Best Practices

### 1. SSH Security:
```bash
# Disable password authentication
sudo nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no
# Set: PubkeyAuthentication yes

sudo systemctl restart ssh
```

### 2. Fail2Ban:
```bash
sudo apt install fail2ban
sudo systemctl enable fail2ban
```

### 3. Environment Security:
- Never commit `.env` files
- Use strong passwords
- Regularly rotate API keys
- Monitor access logs

### 4. Application Security:
- Run with non-root user
- Limit file permissions: `chmod 600 .env`
- Use HTTPS in production
- Implement rate limiting

## 📈 Performance Optimization

### 1. System Optimization:
```bash
# Increase file limits
echo "trader soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "trader hard nofile 65536" | sudo tee -a /etc/security/limits.conf

# Optimize TCP settings
sudo nano /etc/sysctl.conf
# Add: net.core.somaxconn = 65535
# Add: net.ipv4.tcp_max_syn_backlog = 65535

sudo sysctl -p
```

### 2. Database Optimization (if using):
```bash
# For PostgreSQL
sudo nano /etc/postgresql/*/main/postgresql.conf
# Adjust: shared_buffers, effective_cache_size, work_mem
```

### 3. Application Optimization:
- Use Redis for caching (optional)
- Implement connection pooling
- Optimize technical analysis calculations
- Use async operations where possible

## 🚨 Disaster Recovery

### 1. Backup Strategy:
```bash
# Create backup script
nano /home/trader/backup.sh
```

```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/trader/backups"

mkdir -p $BACKUP_DIR

# Backup configuration
cp .env $BACKUP_DIR/env_$DATE

# Backup trading data
cp -r data/ $BACKUP_DIR/data_$DATE

# Backup logs
cp -r logs/ $BACKUP_DIR/logs_$DATE

# Upload to cloud storage (optional)
# aws s3 sync $BACKUP_DIR s3://your-backup-bucket/
```

### 2. Recovery Procedures:
1. **Quick Recovery**: Restart services using supervisor
2. **Application Recovery**: Redeploy from Git repository
3. **Full Recovery**: Restore from backups and reconfigure

## 📊 Monitoring Dashboard

### Recommended Monitoring Tools:
1. **Grafana + Prometheus**: Comprehensive monitoring
2. **Uptime Robot**: External monitoring
3. **New Relic**: Application performance monitoring
4. **CloudWatch** (AWS): Cloud-native monitoring

### Custom Monitoring Script:
```python
# monitor.py
import psutil
import requests
import time

def check_system_health():
    cpu_usage = psutil.cpu_percent()
    memory_usage = psutil.virtual_memory().percent
    disk_usage = psutil.disk_usage('/').percent
    
    if cpu_usage > 80 or memory_usage > 80 or disk_usage > 90:
        send_alert(f"High resource usage: CPU {cpu_usage}%, RAM {memory_usage}%, Disk {disk_usage}%")

def check_trading_status():
    try:
        response = requests.get('http://localhost:5000/api/status')
        if response.status_code != 200:
            send_alert("Trading API not responding")
    except:
        send_alert("Unable to connect to trading application")

if __name__ == "__main__":
    while True:
        check_system_health()
        check_trading_status()
        time.sleep(300)  # Check every 5 minutes
```

## 🆘 Emergency Procedures

### Emergency Stop Trading:
```bash
# Stop all trading immediately
sudo supervisorctl stop trading-engine

# Send emergency alert
python3 /home/trader/alert.py "EMERGENCY: Trading stopped manually"
```

### Emergency Access:
- Keep backup access methods (secondary SSH key, console access)
- Document all recovery procedures
- Maintain emergency contact information

## 📝 Production Checklist

Before going live:

- [ ] Tested with small amounts
- [ ] Configured proper risk limits
- [ ] Set up monitoring and alerts
- [ ] Configured backups
- [ ] Tested disaster recovery
- [ ] Documented all procedures
- [ ] Set up emergency stops
- [ ] Configured SSL certificates
- [ ] Implemented security measures
- [ ] Tested during market hours

---

**⚠️ Important**: Always test thoroughly in a paper trading environment before deploying with real money. Trading involves risk of loss. 