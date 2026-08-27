# MT5 AI Trader - Deployment Guide

## Overview
This guide covers deploying the MT5 AI Trader for daily production use with multiple users or continuous operation.

---

## 1. PRODUCTION SETUP

### A. Environment Configuration

Create `.env.prod` for production (never commit credentials):
```env
# Account Credentials (NEVER hardcode)
MT5_LOGIN=your_account_number
MT5_PASSWORD=your_password
MT5_SERVER=your_broker_server
MT5_TERMINAL_PATH=C:/Program Files/MetaTrader 5/terminal64.exe

# Trading Settings
DEMO_MODE=false  # Set to false for LIVE trading
TRADING_ENABLED=true

# Risk Management
RISK_PER_TRADE_PCT=0.5
MAX_DAILY_LOSS_PCT=3.0
MAX_TOTAL_DRAWDOWN_PCT=10.0

# Logging
LOG_LEVEL=INFO
LOG_DIR=/var/log/mt5_trader  # Or C:\logs\mt5_trader on Windows

# Telegram Alerts (optional)
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

### B. Directory Structure for Production
```
/opt/mt5_trader/  (or C:\mt5_trader\)
├── mt5_ai_trader/          # Main application
├── .env.prod               # Production config (chmod 600)
├── models/                 # Trained models directory
├── logs/                   # Log files
│   ├── app.log
│   ├── trades.csv
│   └── signals.csv
├── backups/                # Database/model backups
├── venv/                   # Virtual environment
├── requirements.txt
└── deploy/                 # Deployment scripts
    ├── start_bot.py
    ├── health_check.py
    ├── restart_on_crash.py
    └── backup_models.py
```

---

## 2. PRE-DEPLOYMENT CHECKLIST

### A. Train & Backtest Model
```bash
# Train the AI model
python mt5_ai_trader/main.py train --symbol EURUSD --bars 5000

# Backtest on 6 months of data
python mt5_ai_trader/main.py backtest --symbol EURUSD --bars 10000 --balance 50000

# Verify performance metrics:
# - Win Rate > 45%
# - Profit Factor > 1.5
# - Max Drawdown < 20%
# - Sharpe Ratio > 1.0
```

### B. Validate Configuration
```bash
# Test with small position sizes first
# Run on DEMO account for 1-2 weeks minimum
# Monitor for errors and edge cases
```

---

## 3. DEPLOYMENT OPTIONS

## 3A. Shared Web Dashboard with Docker

The shared web interface consists of the `api` and `dashboard` services. The
MT5 worker is separate and is enabled only with the `trader` Compose profile.
This prevents a web-only deployment from trying to run MetaTrader 5 in a
Linux web container.

From the project directory on a VPS or another Docker machine:

```bash
cp .env.example .env.prod
# Edit .env.prod and set a strong application configuration.
docker compose up -d api dashboard
```

Open `http://YOUR_SERVER_IP:8501` in a browser. For internet use, place the
dashboard behind HTTPS and a domain name, and restrict port `8000` to the
private Docker network or firewall. The SQLite database is persisted in the
`api_data` Docker volume.

To start the MT5 worker separately after installing and configuring MT5 on a
compatible host:

```bash
docker compose --profile trader up -d mt5_trader
```

The current API includes the registration and dashboard shell, but bot
start/stop endpoints are placeholders and account ownership checks are not
implemented. Do not expose this API publicly or store real trading passwords
until those controls are completed.

## Option A: Windows Service (Recommended for Windows)

### Step 1: Create Startup Script
Create `deploy/start_bot.py`:
```python
#!/usr/bin/env python
"""
Persistent bot runner with crash recovery and health checks
"""
import os
import sys
import time
import subprocess
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler(log_dir / "bot_runner.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_bot():
    """Run the bot with automatic restart on crash"""
    restart_count = 0
    max_restarts_per_hour = 5
    
    while True:
        try:
            logger.info("🚀 Starting MT5 AI Trader...")
            
            # Run the bot process
            process = subprocess.Popen(
                [sys.executable, "mt5_ai_trader/main.py", "live"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Monitor process
            while process.poll() is None:
                time.sleep(30)  # Check every 30 seconds
            
            # Process exited
            exit_code = process.returncode
            logger.error(f"❌ Bot crashed with exit code {exit_code}")
            
            if exit_code != 0:
                restart_count += 1
                if restart_count > max_restarts_per_hour:
                    logger.critical("Too many restarts. Halting.")
                    break
                
                logger.info(f"Restarting in 60 seconds (attempt {restart_count})...")
                time.sleep(60)
            else:
                logger.info("Bot stopped normally")
                break
                
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_bot()
```

### Step 2: Create Windows Service
Use **NSSM** (Non-Sucking Service Manager) or **pywin32**:

**Option A: Using NSSM** (simplest):
```bash
# Download NSSM from nssm.cc
# Install as Windows service:
nssm install MT5Trader "C:\path\to\venv\Scripts\python.exe" "C:\path\to\deploy\start_bot.py"
nssm set MT5Trader AppDirectory "C:\path\to\mt5_ai_trader"
nssm set MT5Trader AppStdout "C:\path\to\logs\service.log"
nssm set MT5Trader AppStderr "C:\path\to\logs\service_error.log"

# Start service
net start MT5Trader

# Stop service
net stop MT5Trader
```

**Option B: Using Task Scheduler**:
1. Open Task Scheduler
2. Create Basic Task → "MT5 AI Trader"
3. Trigger: At startup
4. Action: Start program
   - Program: `C:\path\to\venv\Scripts\python.exe`
   - Arguments: `deploy/start_bot.py`
   - Start in: `C:\path\to\mt5_ai_trader`
5. Enable: "Run with highest privileges"
6. Enable: "Run task as soon as possible if a scheduled start is missed"

---

## Option B: Docker Containerization (Recommended for Linux)

### Step 1: Create Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wine64 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create log directory
RUN mkdir -p logs models

# Health check
HEALTHCHECK --interval=300s --timeout=30s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run bot
CMD ["python", "mt5_ai_trader/main.py", "live"]
```

### Step 2: Docker Compose
```yaml
version: '3.8'

services:
  mt5_trader:
    build: .
    container_name: mt5-ai-trader
    environment:
      - MT5_LOGIN=${MT5_LOGIN}
      - MT5_PASSWORD=${MT5_PASSWORD}
      - MT5_SERVER=${MT5_SERVER}
      - DEMO_MODE=false
    volumes:
      - ./logs:/app/logs
      - ./models:/app/models
      - ./backups:/app/backups
    restart: always
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "10"
    networks:
      - trading_network

networks:
  trading_network:
    driver: bridge
```

Deploy with:
```bash
docker-compose up -d
docker-compose logs -f mt5_trader
docker-compose stop
```

---

## Option C: Cloud Deployment (AWS EC2, DigitalOcean, etc.)

### Step 1: Launch VPS
- **AWS**: EC2 Windows instance (t3.small minimum)
- **DigitalOcean**: Windows Droplet
- **Azure**: Virtual Machine
- **Contabo**: Affordable VPS option

### Step 2: Setup Script
```bash
#!/bin/bash
# setup_vps.sh

# Install Python
apt-get update
apt-get install -y python3.11 python3-pip git

# Clone repo
git clone https://github.com/your_repo/mt5_ai_trader.git
cd mt5_ai_trader

# Setup virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create systemd service (Linux)
sudo tee /etc/systemd/system/mt5trader.service > /dev/null <<EOF
[Unit]
Description=MT5 AI Trader
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/mt5_ai_trader
EnvironmentFile=/home/ubuntu/mt5_ai_trader/.env.prod
ExecStart=/home/ubuntu/mt5_ai_trader/venv/bin/python mt5_ai_trader/main.py live
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable mt5trader
sudo systemctl start mt5trader
```

---

## 4. MONITORING & MAINTENANCE

### A. Health Check Script
Create `deploy/health_check.py`:
```python
import os
import json
import subprocess
from datetime import datetime, timedelta

def check_bot_status():
    """Check if bot is running and trading"""
    results = {
        "timestamp": datetime.now().isoformat(),
        "bot_running": False,
        "last_trade": None,
        "trades_today": 0,
        "equity": None,
        "errors": []
    }
    
    # Check if process is running
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq python.exe"],
            capture_output=True, text=True
        )
        results["bot_running"] = "python.exe" in result.stdout
    except:
        results["errors"].append("Could not check process status")
    
    # Check recent trades
    try:
        if os.path.exists("logs/trades.csv"):
            with open("logs/trades.csv", "r") as f:
                lines = f.readlines()
                if len(lines) > 1:
                    results["trades_today"] = len([
                        l for l in lines if datetime.now().date().isoformat() in l
                    ])
                    results["last_trade"] = lines[-1].split(",")[0]
    except Exception as e:
        results["errors"].append(f"Trade log error: {str(e)}")
    
    # Check for errors in app log
    try:
        if os.path.exists("logs/app.log"):
            with open("logs/app.log", "r") as f:
                last_lines = f.readlines()[-10:]
                critical = [l for l in last_lines if "CRITICAL" in l or "ERROR" in l]
                if critical:
                    results["errors"].extend(critical)
    except:
        pass
    
    return results

if __name__ == "__main__":
    status = check_bot_status()
    print(json.dumps(status, indent=2))
    
    # Alert if bot is down
    if not status["bot_running"]:
        print("⚠️  BOT IS NOT RUNNING!")
        # Send Telegram/Email alert here
```

### B. Automated Monitoring
**crontab (Linux)**:
```bash
# Check every 5 minutes
*/5 * * * * cd /opt/mt5_trader && python deploy/health_check.py >> logs/health_check.log 2>&1

# Daily backup at 2 AM
0 2 * * * cd /opt/mt5_trader && python deploy/backup_models.py

# Restart bot if crashed
*/1 * * * * python /opt/mt5_trader/deploy/start_bot.py >> /var/log/mt5_bot.log 2>&1
```

**Windows Task Scheduler**:
- Schedule health check script
- Schedule automated backups
- Schedule log rotation

---

## 5. BACKUP & DISASTER RECOVERY

### A. Backup Strategy
```python
# deploy/backup_models.py
import shutil
from pathlib import Path
from datetime import datetime

def backup_models():
    backup_dir = Path("backups") / datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Backup trained models
    shutil.copytree("models", backup_dir / "models")
    
    # Backup logs
    shutil.copytree("logs", backup_dir / "logs")
    
    # Backup config
    shutil.copy(".env.prod", backup_dir / ".env.prod.bak")
    
    print(f"✓ Backup created: {backup_dir}")
    
    # Keep only last 30 backups
    backups = sorted(Path("backups").iterdir())
    for old_backup in backups[:-30]:
        shutil.rmtree(old_backup)

if __name__ == "__main__":
    backup_models()
```

### B. Log Rotation
Create `deploy/rotate_logs.py`:
```python
import gzip
import shutil
from pathlib import Path
from datetime import datetime, timedelta

def rotate_logs():
    log_dir = Path("logs")
    
    # Compress logs older than 7 days
    for log_file in log_dir.glob("*.log"):
        age = datetime.now() - datetime.fromtimestamp(log_file.stat().st_mtime)
        
        if age > timedelta(days=7):
            with open(log_file, 'rb') as f_in:
                with gzip.open(f"{log_file}.gz", 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            log_file.unlink()
            print(f"✓ Compressed: {log_file}")

if __name__ == "__main__":
    rotate_logs()
```

---

## 6. MULTI-USER MANAGEMENT

### A. User Accounts
```python
# users.json - Store multiple trading accounts
{
  "users": [
    {
      "user_id": "user_001",
      "account_login": 123456,
      "account_password": "${ENCRYPTED_PASSWORD}",
      "risk_per_trade": 0.5,
      "max_daily_loss": 3.0,
      "active": true,
      "telegram_id": "123456789"
    }
  ]
}
```

### B. Multi-Account Bot
Modify `main.py` to support multiple accounts:
```python
def run_multi_account():
    """Run bot for multiple accounts concurrently"""
    import json
    import threading
    
    with open("users.json") as f:
        users_config = json.load(f)
    
    threads = []
    for user in users_config["users"]:
        if not user["active"]:
            continue
        
        thread = threading.Thread(
            target=run_account_bot,
            args=(user,),
            daemon=False
        )
        thread.start()
        threads.append(thread)
    
    # Wait for all threads
    for thread in threads:
        thread.join()
```

---

## 7. SECURITY BEST PRACTICES

### A. Credentials Management
```bash
# Never commit .env files
echo ".env*" >> .gitignore
echo "*.key" >> .gitignore
echo "models/" >> .gitignore

# Use restricted permissions
chmod 600 .env.prod
chmod 700 deploy/
```

### B. Firewall Rules
- Allow outbound: Port 443 (HTTPS for market data)
- Allow outbound: Port 25/587 (Email alerts, optional)
- Restrict SSH/RDP to your IP only
- Disable unnecessary services

### C. API Key Rotation
- Rotate MT5 passwords quarterly
- Rotate Telegram tokens if compromised
- Audit access logs weekly

---

## 8. PERFORMANCE OPTIMIZATION

### A. Resource Requirements
- **CPU**: 1 core minimum (bot is I/O-bound)
- **Memory**: 512 MB minimum (1 GB recommended)
- **Disk**: 50 GB (for logs and backups)
- **Network**: 1 Mbps minimum

### B. Optimization Tips
```python
# In config.py
POLL_SECONDS = 60  # Check for new bars every 60 seconds
RETRAIN_EVERY_N_BARS = 500  # Don't retrain too often
LOOKBACK_BARS = 1500  # Balance between accuracy and speed
```

---

## 9. DAILY CHECKLIST

**Morning (Before Market Open)**:
- [ ] Verify bot is running: `systemctl status mt5trader`
- [ ] Check previous day's trades: `tail -f logs/trades.csv`
- [ ] Monitor equity: Check account balance in MT5
- [ ] Review any error logs: `tail logs/app.log`

**During Trading Hours**:
- [ ] Monitor for excessive losses (daily loss limit)
- [ ] Check system resources (CPU, Memory, Disk)
- [ ] Ensure stable internet connection

**End of Day**:
- [ ] Archive today's trades
- [ ] Back up models
- [ ] Review performance metrics
- [ ] Plan next day's adjustments

---

## 10. TROUBLESHOOTING

### Bot Won't Start
```bash
# Check Python installation
python --version

# Check dependencies
pip list | grep -E "pandas|numpy|xgboost"

# Test MT5 connection
python -c "import MetaTrader5; print(MetaTrader5.__version__)"
```

### High Memory Usage
```bash
# Check running processes
ps aux | grep python

# Kill zombie processes
pkill -f "main.py"

# Restart service
systemctl restart mt5trader
```

### Missing Trades / No Signals
```bash
# Check signal generation
python -c "from engine.signal_generator import SignalGenerator; print('OK')"

# Verify model exists
ls -la models/

# Check for errors
grep ERROR logs/app.log | tail -20
```

---

## 11. SCALING FOR PRODUCTION

**Phase 1**: Single account on local Windows machine (current)
**Phase 2**: Multiple accounts on VPS with monitoring
**Phase 3**: Kubernetes cluster with load balancing
**Phase 4**: Enterprise setup with redundancy & failover

---

## Quick Start Commands

```bash
# Initial setup
git clone <repo>
cd mt5_ai_trader
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows
pip install -r requirements.txt

# Train model
python mt5_ai_trader/main.py train --symbol EURUSD --bars 5000

# Deploy (Windows Service)
nssm install MT5Trader "python" "deploy/start_bot.py"
net start MT5Trader

# Deploy (Linux/Docker)
docker-compose up -d

# Monitor
python deploy/health_check.py
tail -f logs/app.log

# Stop
systemctl stop mt5trader  # or: net stop MT5Trader
docker-compose down
```

---

**Last Updated**: 2026-08-27
**Status**: Production Ready ✅
