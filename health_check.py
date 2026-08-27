#!/usr/bin/env python
"""
Health Check - Monitor bot status, trades, and system resources
"""
import os
import json
import subprocess
import psutil
from datetime import datetime, timedelta
from pathlib import Path

class BotHealthCheck:
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "status": "unknown",
            "bot_running": False,
            "trades_today": 0,
            "last_trade_time": None,
            "daily_pnl": 0.0,
            "system_cpu_percent": 0,
            "system_memory_percent": 0,
            "disk_free_gb": 0,
            "errors": [],
            "warnings": []
        }
    
    def check_bot_running(self):
        """Check if bot process is running"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if proc.name() == 'python.exe' or proc.name() == 'python':
                    if proc.cmdline() and 'main.py' in ' '.join(proc.cmdline()):
                        self.results["bot_running"] = True
                        return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        
        self.results["bot_running"] = False
        return False
    
    def check_trades(self):
        """Analyze recent trades"""
        try:
            trade_log = Path("logs/trades.csv")
            if not trade_log.exists():
                self.results["warnings"].append("Trade log not found")
                return
            
            with open(trade_log, 'r') as f:
                lines = f.readlines()
            
            if len(lines) < 2:  # Header only
                return
            
            today = datetime.now().date().isoformat()
            today_trades = []
            
            for line in lines[1:]:  # Skip header
                try:
                    parts = line.strip().split(',')
                    if len(parts) > 0 and today in parts[0]:
                        today_trades.append(line)
                        self.results["last_trade_time"] = parts[0]
                except:
                    continue
            
            self.results["trades_today"] = len(today_trades)
            
            # Calculate daily P&L
            total_pnl = 0
            for line in today_trades:
                try:
                    parts = line.strip().split(',')
                    if len(parts) > 7:  # Assuming PnL is in column 8
                        total_pnl += float(parts[7])
                except:
                    continue
            
            self.results["daily_pnl"] = round(total_pnl, 2)
            
        except Exception as e:
            self.results["errors"].append(f"Trade check error: {str(e)}")
    
    def check_system_resources(self):
        """Check CPU, memory, and disk"""
        try:
            # CPU usage
            self.results["system_cpu_percent"] = psutil.cpu_percent(interval=1)
            
            # Memory usage
            self.results["system_memory_percent"] = psutil.virtual_memory().percent
            
            # Disk space (root or current drive)
            disk = psutil.disk_usage('/')
            self.results["disk_free_gb"] = round(disk.free / (1024**3), 2)
            
            # Warnings
            if self.results["system_cpu_percent"] > 80:
                self.results["warnings"].append(f"High CPU: {self.results['system_cpu_percent']}%")
            
            if self.results["system_memory_percent"] > 85:
                self.results["warnings"].append(f"High Memory: {self.results['system_memory_percent']}%")
            
            if self.results["disk_free_gb"] < 5:
                self.results["warnings"].append(f"Low disk space: {self.results['disk_free_gb']}GB")
                
        except Exception as e:
            self.results["errors"].append(f"System check error: {str(e)}")
    
    def check_recent_errors(self):
        """Check app log for recent errors"""
        try:
            app_log = Path("logs/app.log")
            if not app_log.exists():
                return
            
            with open(app_log, 'r', errors='ignore') as f:
                lines = f.readlines()
            
            # Get last 50 lines
            recent_lines = lines[-50:]
            
            for line in recent_lines:
                if "CRITICAL" in line or "ERROR" in line:
                    self.results["errors"].append(line.strip()[:100])
                elif "WARNING" in line:
                    self.results["warnings"].append(line.strip()[:100])
                    
        except Exception as e:
            self.results["errors"].append(f"Log check error: {str(e)}")
    
    def determine_status(self):
        """Determine overall health status"""
        if self.results["errors"]:
            self.results["status"] = "ERROR"
        elif not self.results["bot_running"]:
            self.results["status"] = "OFFLINE"
        elif self.results["warnings"]:
            self.results["status"] = "WARNING"
        else:
            self.results["status"] = "HEALTHY"
    
    def run(self):
        """Run all checks"""
        self.check_bot_running()
        self.check_trades()
        self.check_system_resources()
        self.check_recent_errors()
        self.determine_status()
        return self.results
    
    def print_summary(self):
        """Print human-readable summary"""
        status_emoji = {
            "HEALTHY": "✅",
            "WARNING": "⚠️",
            "OFFLINE": "🔴",
            "ERROR": "❌"
        }
        
        emoji = status_emoji.get(self.results["status"], "❓")
        
        print("\n" + "=" * 70)
        print(f"{emoji} BOT HEALTH CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print(f"Status:              {self.results['status']}")
        print(f"Bot Running:         {'Yes' if self.results['bot_running'] else 'No'}")
        print(f"Trades Today:        {self.results['trades_today']}")
        print(f"Daily P&L:           ${self.results['daily_pnl']:,.2f}")
        print(f"Last Trade:          {self.results['last_trade_time'] or 'None'}")
        print(f"\nSystem Resources:")
        print(f"  CPU:               {self.results['system_cpu_percent']}%")
        print(f"  Memory:            {self.results['system_memory_percent']}%")
        print(f"  Disk Free:         {self.results['disk_free_gb']} GB")
        
        if self.results["warnings"]:
            print(f"\n⚠️  Warnings ({len(self.results['warnings'])}):")
            for warning in self.results["warnings"][:5]:  # Show top 5
                print(f"  - {warning}")
        
        if self.results["errors"]:
            print(f"\n❌ Errors ({len(self.results['errors'])}):")
            for error in self.results["errors"][:5]:  # Show top 5
                print(f"  - {error}")
        
        print("=" * 70 + "\n")

def main():
    checker = BotHealthCheck()
    results = checker.run()
    
    # Print summary
    checker.print_summary()
    
    # Save to JSON
    with open("logs/health_check_latest.json", "w") as f:
        json.dump(results, f, indent=2)
    
    # Exit with appropriate code
    if results["status"] == "ERROR":
        exit(1)
    elif results["status"] == "OFFLINE":
        exit(2)
    else:
        exit(0)

if __name__ == "__main__":
    main()
