#!/usr/bin/env python
"""
Bot Runner - Persistent bot execution with automatic restart on crash
Windows & Linux compatible
"""
import os
import sys
import time
import subprocess
import logging
from pathlib import Path
from datetime import datetime, timedelta
import platform

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

class BotRunner:
    def __init__(self, max_restarts_per_hour=5, restart_delay=60):
        self.max_restarts_per_hour = max_restarts_per_hour
        self.restart_delay = restart_delay
        self.restart_times = []
        self.process = None
    
    def cleanup_old_restarts(self):
        """Remove restart attempts older than 1 hour"""
        cutoff = datetime.now() - timedelta(hours=1)
        self.restart_times = [t for t in self.restart_times if t > cutoff]
    
    def can_restart(self):
        """Check if we haven't exceeded max restarts"""
        self.cleanup_old_restarts()
        return len(self.restart_times) < self.max_restarts_per_hour
    
    def record_restart(self):
        """Record a restart attempt"""
        self.restart_times.append(datetime.now())
    
    def run(self):
        """Main bot runner loop"""
        while True:
            try:
                logger.info("=" * 60)
                logger.info("🚀 Starting MT5 AI Trader Bot...")
                logger.info("=" * 60)
                
                # Run bot process
                cmd = [sys.executable, "mt5_ai_trader/main.py", "live"]
                
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )
                
                # Monitor process output
                while self.process.poll() is None:
                    time.sleep(30)
                    # Optional: Write to log every 30 seconds
                    logger.debug("Bot process still running...")
                
                # Process exited
                exit_code = self.process.returncode
                logger.warning(f"❌ Bot process exited with code: {exit_code}")
                
                # Check if we should restart
                if exit_code != 0:
                    if self.can_restart():
                        self.record_restart()
                        remaining = self.max_restarts_per_hour - len(self.restart_times)
                        logger.warning(
                            f"⏳ Restarting in {self.restart_delay}s "
                            f"(attempt {len(self.restart_times)}/{self.max_restarts_per_hour})"
                        )
                        time.sleep(self.restart_delay)
                    else:
                        logger.critical(
                            f"🛑 MAX RESTART LIMIT EXCEEDED ({self.max_restarts_per_hour} in 1 hour). "
                            "Bot halted. Check logs for root cause."
                        )
                        self.send_alert("MAX_RESTARTS_EXCEEDED")
                        break
                else:
                    logger.info("✓ Bot stopped normally")
                    break
                    
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt. Shutting down...")
                if self.process:
                    self.process.terminate()
                break
            except Exception as e:
                logger.exception(f"Unexpected error in bot runner: {e}")
                self.send_alert(f"BOT_RUNNER_ERROR: {str(e)}")
                time.sleep(self.restart_delay)
    
    def send_alert(self, alert_type):
        """Send alert via Telegram or email"""
        try:
            # Optional: Integrate with alerts
            pass
        except:
            pass

if __name__ == "__main__":
    logger.info(f"Python: {sys.version}")
    logger.info(f"Platform: {platform.platform()}")
    logger.info(f"CWD: {os.getcwd()}")
    
    runner = BotRunner(max_restarts_per_hour=5, restart_delay=60)
    runner.run()
