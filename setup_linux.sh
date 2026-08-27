#!/bin/bash
# MT5 AI Trader - Linux/VPS Setup Script
# Install and configure bot as systemd service on Linux

set -e  # Exit on error

echo "=========================================="
echo "MT5 AI Trader - Linux Setup"
echo "=========================================="
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (sudo)"
   exit 1
fi

# Configuration
BOT_USER="mt5trader"
BOT_HOME="/opt/mt5_trader"
BOT_REPO="${BOT_REPO:-https://github.com/your_repo/mt5_ai_trader.git}"
SERVICE_NAME="mt5trader"

echo "Configuration:"
echo "  Bot User: $BOT_USER"
echo "  Bot Home: $BOT_HOME"
echo "  Repository: $BOT_REPO"
echo ""

# Step 1: Install system dependencies
echo "Installing system dependencies..."
apt-get update
apt-get install -y \
    python3.11 \
    python3-pip \
    python3.11-venv \
    git \
    curl \
    supervisor \
    logrotate \
    htop

echo "✓ Dependencies installed"
echo ""

# Step 2: Create bot user
echo "Creating bot user..."
if ! id "$BOT_USER" &>/dev/null; then
    useradd -m -s /bin/bash "$BOT_USER"
    echo "✓ User '$BOT_USER' created"
else
    echo "✓ User '$BOT_USER' already exists"
fi

mkdir -p "$BOT_HOME"
chown "$BOT_USER:$BOT_USER" "$BOT_HOME"

echo ""

# Step 3: Clone/update repository
echo "Setting up repository..."
if [ -d "$BOT_HOME/.git" ]; then
    echo "Repository already exists, pulling latest..."
    cd "$BOT_HOME"
    sudo -u "$BOT_USER" git pull origin main
else
    echo "Cloning repository..."
    sudo -u "$BOT_USER" git clone "$BOT_REPO" "$BOT_HOME"
fi

echo "✓ Repository ready"
echo ""

# Step 4: Setup Python virtual environment
echo "Setting up Python virtual environment..."
cd "$BOT_HOME"
sudo -u "$BOT_USER" python3.11 -m venv venv
sudo -u "$BOT_USER" venv/bin/pip install --upgrade pip setuptools wheel
sudo -u "$BOT_USER" venv/bin/pip install -r requirements.txt

echo "✓ Virtual environment ready"
echo ""

# Step 5: Setup directories
echo "Creating directories..."
mkdir -p "$BOT_HOME"/{logs,models,backups}
chown "$BOT_USER:$BOT_USER" "$BOT_HOME"/{logs,models,backups}
chmod 755 "$BOT_HOME"/{logs,models,backups}

mkdir -p "/var/log/mt5_trader"
chown "$BOT_USER:$BOT_USER" "/var/log/mt5_trader"

echo "✓ Directories created"
echo ""

# Step 6: Create systemd service
echo "Creating systemd service..."
cat > "/etc/systemd/system/${SERVICE_NAME}.service" << 'EOF'
[Unit]
Description=MT5 AI Trading Bot
After=network.target
Wants=mt5trader-monitor.timer

[Service]
Type=simple
User=mt5trader
Group=mt5trader
WorkingDirectory=/opt/mt5_trader
EnvironmentFile=/opt/mt5_trader/.env.prod

# Python interpreter from venv
ExecStart=/opt/mt5_trader/venv/bin/python deploy/start_bot.py

# Restart policy
Restart=always
RestartSec=60
StartLimitInterval=3600
StartLimitBurst=5

# Resource limits
MemoryLimit=1G
CPUQuota=80%

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=mt5trader

[Install]
WantedBy=multi-user.target
EOF

chmod 644 "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload

echo "✓ Service file created"
echo ""

# Step 7: Create health check timer
echo "Creating health check timer..."
cat > "/etc/systemd/system/mt5trader-monitor.timer" << 'EOF'
[Unit]
Description=MT5 Trader Health Check
Requires=mt5trader-monitor.service

[Timer]
OnBootSec=5min
OnUnitActiveSec=5min
Persistent=true

[Install]
WantedBy=timers.target
EOF

cat > "/etc/systemd/system/mt5trader-monitor.service" << 'EOF'
[Unit]
Description=MT5 Trader Health Check Script
After=network.target

[Service]
Type=oneshot
User=mt5trader
WorkingDirectory=/opt/mt5_trader
ExecStart=/opt/mt5_trader/venv/bin/python deploy/health_check.py

StandardOutput=journal
StandardError=journal
SyslogIdentifier=mt5trader-monitor
EOF

systemctl daemon-reload
systemctl enable mt5trader-monitor.timer

echo "✓ Monitor timer created"
echo ""

# Step 8: Setup log rotation
echo "Creating log rotation config..."
cat > "/etc/logrotate.d/mt5trader" << 'EOF'
/opt/mt5_trader/logs/*.log
/opt/mt5_trader/logs/*.csv
{
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 mt5trader mt5trader
    sharedscripts
    postrotate
        systemctl reload mt5trader > /dev/null 2>&1 || true
    endscript
}

/var/log/mt5_trader/*.log
{
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 mt5trader mt5trader
}
EOF

echo "✓ Log rotation configured"
echo ""

# Step 9: Setup backup cron
echo "Creating backup schedule..."
cat > "/etc/cron.d/mt5trader-backup" << 'EOF'
# MT5 Trader Backups
# Daily backup at 2 AM UTC
0 2 * * * mt5trader cd /opt/mt5_trader && ./venv/bin/python deploy/backup_models.py >> logs/cron_backup.log 2>&1

# Hourly health check
0 * * * * mt5trader cd /opt/mt5_trader && ./venv/bin/python deploy/health_check.py >> /var/log/mt5_trader/health_check.log 2>&1
EOF

chmod 644 "/etc/cron.d/mt5trader-backup"

echo "✓ Backup schedule created"
echo ""

# Step 10: Check .env.prod
echo "Checking environment configuration..."
if [ ! -f "$BOT_HOME/.env.prod" ]; then
    echo "⚠️  .env.prod not found!"
    echo "   Please create .env.prod with your MT5 credentials"
    echo "   Template: cat $BOT_HOME/.env.example > $BOT_HOME/.env.prod"
    echo "   Then edit: nano $BOT_HOME/.env.prod"
else
    chown "$BOT_USER:$BOT_USER" "$BOT_HOME/.env.prod"
    chmod 600 "$BOT_HOME/.env.prod"
    echo "✓ .env.prod found (permissions set)"
fi

echo ""

# Final steps
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "Next Steps:"
echo ""
echo "1. Configure credentials:"
echo "   sudo nano /opt/mt5_trader/.env.prod"
echo ""
echo "2. Start the service:"
echo "   sudo systemctl start ${SERVICE_NAME}"
echo ""
echo "3. Check status:"
echo "   sudo systemctl status ${SERVICE_NAME}"
echo ""
echo "4. View logs:"
echo "   sudo journalctl -u ${SERVICE_NAME} -f"
echo ""
echo "5. Enable auto-start:"
echo "   sudo systemctl enable ${SERVICE_NAME}"
echo ""
echo "Useful Commands:"
echo "   sudo systemctl stop ${SERVICE_NAME}        # Stop the bot"
echo "   sudo systemctl restart ${SERVICE_NAME}     # Restart the bot"
echo "   sudo systemctl status ${SERVICE_NAME}      # Check status"
echo "   sudo journalctl -u ${SERVICE_NAME} -f      # Follow logs"
echo "   sudo systemctl status mt5trader-monitor    # Check health monitor"
echo ""
echo "Log Files:"
echo "   Bot: /var/log/journal/ or journalctl"
echo "   Health Checks: /var/log/mt5_trader/health_check.log"
echo "   Backups: /opt/mt5_trader/logs/cron_backup.log"
echo ""
