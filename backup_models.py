#!/usr/bin/env python
"""
Backup Manager - Backup models, logs, and configs
Automatically maintains retention policy
"""
import shutil
import json
from pathlib import Path
from datetime import datetime, timedelta
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)
logger = logging.getLogger(__name__)

class BackupManager:
    def __init__(self, backup_dir="backups", retention_days=30, max_backups=50):
        self.backup_dir = Path(backup_dir)
        self.retention_days = retention_days
        self.max_backups = max_backups
        self.backup_dir.mkdir(exist_ok=True)
    
    def create_backup(self):
        """Create timestamped backup"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / timestamp
        backup_path.mkdir(exist_ok=True)
        
        try:
            # Backup models
            models_src = Path("models")
            if models_src.exists():
                shutil.copytree(
                    models_src,
                    backup_path / "models",
                    dirs_exist_ok=True
                )
                logger.info(f"✓ Backed up models to {backup_path / 'models'}")
            
            # Backup config
            env_file = Path(".env.prod")
            if env_file.exists():
                shutil.copy(env_file, backup_path / ".env.prod.bak")
                logger.info(f"✓ Backed up config")
            
            # Backup config.py
            config_file = Path("mt5_ai_trader/config.py")
            if config_file.exists():
                shutil.copy(config_file, backup_path / "config.py")
                logger.info(f"✓ Backed up configuration")
            
            # Create metadata
            metadata = {
                "timestamp": datetime.now().isoformat(),
                "backup_size_mb": self._get_dir_size(backup_path) / (1024*1024),
                "status": "success"
            }
            
            with open(backup_path / "metadata.json", "w") as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"✅ Backup created: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")
            if backup_path.exists():
                shutil.rmtree(backup_path)
            return None
    
    def cleanup_old_backups(self):
        """Remove backups older than retention period"""
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        removed_count = 0
        
        for backup in sorted(self.backup_dir.iterdir()):
            if not backup.is_dir():
                continue
            
            try:
                backup_time = datetime.strptime(backup.name, "%Y%m%d_%H%M%S")
                
                if backup_time < cutoff_date:
                    shutil.rmtree(backup)
                    logger.info(f"🗑️  Removed old backup: {backup.name}")
                    removed_count += 1
            except:
                continue
        
        if removed_count > 0:
            logger.info(f"✓ Cleaned up {removed_count} old backups")
    
    def enforce_max_backups(self):
        """Keep only the latest N backups"""
        backups = sorted(
            [b for b in self.backup_dir.iterdir() if b.is_dir()],
            reverse=True
        )
        
        if len(backups) > self.max_backups:
            for old_backup in backups[self.max_backups:]:
                shutil.rmtree(old_backup)
                logger.info(f"🗑️  Removed backup (exceeds max): {old_backup.name}")
    
    def list_backups(self, limit=10):
        """List recent backups"""
        backups = sorted(
            [b for b in self.backup_dir.iterdir() if b.is_dir()],
            reverse=True
        )[:limit]
        
        print("\nRecent Backups:")
        print("=" * 70)
        for backup in backups:
            size_mb = self._get_dir_size(backup) / (1024*1024)
            timestamp = backup.name
            print(f"  {timestamp}  ({size_mb:.1f} MB)")
        print("=" * 70 + "\n")
    
    @staticmethod
    def _get_dir_size(path):
        """Get total size of directory"""
        total = 0
        for item in Path(path).rglob('*'):
            if item.is_file():
                total += item.stat().st_size
        return total

def main():
    manager = BackupManager(retention_days=30, max_backups=50)
    
    logger.info("Starting backup process...")
    
    # Create backup
    backup_path = manager.create_backup()
    
    if backup_path:
        # Cleanup old backups
        manager.cleanup_old_backups()
        manager.enforce_max_backups()
        
        # List recent backups
        manager.list_backups()
        
        logger.info("✅ Backup process completed successfully")
        exit(0)
    else:
        logger.error("❌ Backup process failed")
        exit(1)

if __name__ == "__main__":
    main()
