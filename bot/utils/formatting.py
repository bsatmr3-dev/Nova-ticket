import discord
from datetime import datetime
from typing import Optional

def format_text(
    template: str,
    user: Optional[discord.User] = None,
    guild: Optional[discord.Guild] = None,
    ticket_channel: Optional[discord.TextChannel] = None,
    category_name: Optional[str] = None,
    staff: Optional[discord.User] = None
) -> str:
    if not template:
        return ""
    
    result = template
    if user:
        result = result.replace("{user}", user.mention)
        result = result.replace("{username}", user.name)
        result = result.replace("{user_id}", str(user.id))
    
    if guild:
        result = result.replace("{server}", guild.name)
        result = result.replace("{server_name}", guild.name)
        result = result.replace("{server_id}", str(guild.id))
        
    if ticket_channel:
        result = result.replace("{ticket}", ticket_channel.mention)
        result = result.replace("{ticket_channel}", ticket_channel.mention)
        result = result.replace("{ticket_name}", ticket_channel.name)
        
    if category_name:
        result = result.replace("{category}", category_name)
        
    if staff:
        result = result.replace("{staff}", staff.mention)
        result = result.replace("{staff_name}", staff.name)
    else:
        result = result.replace("{staff}", "طاقم الدعم")

    now = datetime.utcnow()
    result = result.replace("{date}", now.strftime("%Y-%m-%d"))
    result = result.replace("{time}", now.strftime("%H:%M:%S UTC"))
    return result
