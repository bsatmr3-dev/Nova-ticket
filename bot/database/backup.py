import os
import shutil
from datetime import datetime
from bot.config.settings import Config

class BackupManager:
    @staticmethod
    def create_backup(backup_dir: str = "database/backups") -> str:
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"tickets_backup_{timestamp}.db")
        if os.path.exists(Config.DATABASE_PATH):
            shutil.copy2(Config.DATABASE_PATH, backup_file)
            return backup_file
        raise FileNotFoundError("Database file does not exist to back up.")

    @staticmethod
    def list_backups(backup_dir: str = "database/backups") -> list:
        if not os.path.exists(backup_dir):
            return []
        return sorted([os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.endswith(".db")], reverse=True)

    @staticmethod
    def restore_backup(backup_file_path: str):
        if os.path.exists(backup_file_path):
            shutil.copy2(backup_file_path, Config.DATABASE_PATH)
            return True
        return False
