import os
import json
from datetime import datetime
from bot.database.db import db

class BackupManager:
    @staticmethod
    def create_backup(backup_dir: str = "database/backups") -> str:
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"postgres_backup_{timestamp}.json")
        
        data = {
            "version": "2.0",
            "backed_up_at": datetime.utcnow().isoformat(),
            "panels": db.get_panels() or [],
            "tickets": db.get_all_tickets() or [],
            "ratings": db.get_all_ratings(1000) or [],
            "blacklist": db.get_blacklisted_users() or []
        }
        
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        return backup_file

    @staticmethod
    def list_backups(backup_dir: str = "database/backups") -> list:
        if not os.path.exists(backup_dir):
            return []
        return sorted([os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.endswith(".json")], reverse=True)
