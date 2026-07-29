import time
from typing import Dict, Tuple
from bot.config.settings import Config

class AntiSpamManager:
    def __init__(self):
        self.user_cooldowns: Dict[int, float] = {}

    def check_cooldown(self, user_id: int) -> Tuple[bool, float]:
        now = time.time()
        last_time = self.user_cooldowns.get(user_id, 0)
        cooldown = Config.COOLDOWN_SECONDS
        if now - last_time < cooldown:
            remaining = cooldown - (now - last_time)
            return False, remaining
        self.user_cooldowns[user_id] = now
        return True, 0.0

antispam = AntiSpamManager()
