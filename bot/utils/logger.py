import discord
from typing import Optional, Dict, Any
from bot.database.db import db
from bot.utils.embeds import EmbedBuilder

class TicketLogger:
    @staticmethod
    async def log_action(
        guild: discord.Guild,
        ticket: Dict[str, Any],
        action_name: str,
        executor: discord.User,
        details: Optional[str] = None,
        color: int = EmbedBuilder.COLOR_INFO,
        file: Optional[discord.File] = None
    ):
        if not guild or not ticket:
            return

        ticket_id = ticket.get("id", 0)

        # 1. Store in Database Audit Log
        db.log_audit_event(
            ticket_id=ticket_id,
            action=action_name,
            executor_id=executor.id,
            details=details
        )

        # 2. Get Log Channel from Guild Settings
        settings = db.get_guild_settings(guild.id)
        if not settings or not settings.get("log_channel_id"):
            return

        log_channel_id = settings["log_channel_id"]
        log_channel = guild.get_channel(log_channel_id)
        if not log_channel:
            return

        # 3. Create Embed Log
        embed = EmbedBuilder.create_embed(
            title=f"📋 [سجل التذاكر] {action_name}",
            description=f"تم تنفيذ إجراء جديد على التذكرة **#{ticket_id}**",
            color=color
        )
        embed.add_field(name="🎫 التذكرة", value=f"<#{ticket.get('channel_id')}>", inline=True)
        embed.add_field(name="👤 المنفذ", value=executor.mention, inline=True)
        embed.add_field(name="📂 القسم", value=ticket.get("category_id", "عام"), inline=True)
        
        if details:
            embed.add_field(name="📝 التفاصيل", value=details, inline=False)

        embed.timestamp = discord.utils.utcnow()

        try:
            await log_channel.send(embed=embed, file=file)
        except Exception:
            pass
