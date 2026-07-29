import discord
from bot.database.db import db
from bot.config.settings import Config

class PermissionHandler:
    ROLE_HIERARCHY = {
        "master_owner": 100,
        "owner": 50,
        "admin": 40,
        "support_manager": 30,
        "senior_support": 20,
        "support": 10,
        "member": 0
    }

    @staticmethod
    def is_bot_owner(user_id: int) -> bool:
        return user_id == Config.BOT_OWNER_ID or user_id == 1406547827865288786

    @staticmethod
    def is_staff(member: discord.Member) -> bool:
        if not member:
            return False
        if PermissionHandler.is_bot_owner(member.id):
            return True
        if member.guild and member.guild.owner_id == member.id:
            return True
        if member.guild_permissions.administrator or member.guild_permissions.manage_channels or member.guild_permissions.manage_messages:
            return True
        
        rank = PermissionHandler.get_member_rank(member)
        return rank >= PermissionHandler.ROLE_HIERARCHY["support"]

    @staticmethod
    def is_admin(member: discord.Member) -> bool:
        if not member:
            return False
        if PermissionHandler.is_bot_owner(member.id):
            return True
        if member.guild and member.guild.owner_id == member.id:
            return True
        if member.guild_permissions.administrator:
            return True
        
        rank = PermissionHandler.get_member_rank(member)
        return rank >= PermissionHandler.ROLE_HIERARCHY["admin"]

    @staticmethod
    def is_support_manager(member: discord.Member) -> bool:
        if not member:
            return False
        if PermissionHandler.is_bot_owner(member.id):
            return True
        if member.guild and member.guild.owner_id == member.id:
            return True
        if member.guild_permissions.administrator:
            return True
        
        rank = PermissionHandler.get_member_rank(member)
        return rank >= PermissionHandler.ROLE_HIERARCHY["support_manager"]

    @staticmethod
    def get_member_rank(member: discord.Member) -> int:
        if not member:
            return PermissionHandler.ROLE_HIERARCHY["member"]
        if PermissionHandler.is_bot_owner(member.id):
            return PermissionHandler.ROLE_HIERARCHY["master_owner"]
        if member.guild and member.guild.owner_id == member.id:
            return PermissionHandler.ROLE_HIERARCHY["owner"]
        if member.guild_permissions.administrator:
            return PermissionHandler.ROLE_HIERARCHY["admin"]
        
        # Check database settings for specific roles
        if member.guild:
            settings = db.get_guild_settings(member.guild.id) or {}
            user_role_ids = [role.id for role in member.roles]
            
            # Check roles in order of hierarchy
            role_mappings = [
                ("owner_role_id", "owner"),
                ("admin_role_id", "admin"),
                ("support_manager_role_id", "support_manager"),
                ("senior_support_role_id", "senior_support"),
                ("support_role_id", "support")
            ]
            
            for setting_key, rank_key in role_mappings:
                role_id = settings.get(setting_key)
                if role_id and str(role_id).isdigit() and int(role_id) in user_role_ids:
                    return PermissionHandler.ROLE_HIERARCHY[rank_key]
        
        # Fallback to keywords check
        max_rank = PermissionHandler.ROLE_HIERARCHY["member"]
        for role in member.roles:
            role_name = role.name.lower()
            if "manager" in role_name:
                max_rank = max(max_rank, PermissionHandler.ROLE_HIERARCHY["support_manager"])
            elif "senior" in role_name or "سينيور" in role_name:
                max_rank = max(max_rank, PermissionHandler.ROLE_HIERARCHY["senior_support"])
            elif "support" in role_name or "دعم" in role_name:
                max_rank = max(max_rank, PermissionHandler.ROLE_HIERARCHY["support"])
            elif "admin" in role_name or "إدارة" in role_name or "ادارة" in role_name:
                max_rank = max(max_rank, PermissionHandler.ROLE_HIERARCHY["admin"])
                
        return max_rank

    @staticmethod
    def can_manage_ticket(member: discord.Member) -> bool:
        return PermissionHandler.is_staff(member)

    @staticmethod
    def can_execute_action(guild: discord.Guild, member: discord.Member, action_name: str, ticket_user_id: int = None, ticket_data: dict = None) -> bool:
        if not member:
            return False

        # Master owner bypass
        if PermissionHandler.is_bot_owner(member.id):
            return True

        # Special logic for rate_staff: STRICTLY for ticket owner, staff CANNOT rate themselves
        if action_name == "rate_staff":
            if not ticket_user_id or member.id != ticket_user_id:
                return False
            claimed_by = ticket_data.get("claimed_by") if ticket_data else None
            if claimed_by and member.id == claimed_by:
                return False
            if PermissionHandler.is_staff(member) and member.id != ticket_user_id:
                return False
            return True

        # Administrator & Guild Owner bypass
        if guild and (member.id == guild.owner_id or member.guild_permissions.administrator):
            return True

        # Member-only / All-user allowed actions (for the ticket owner)
        if action_name in ["info", "summon_staff"]:
            return True

        if action_name == "close":
            if ticket_user_id and member.id == ticket_user_id:
                return True

        if action_name in ["add_member", "remove_member"]:
            if ticket_user_id and member.id == ticket_user_id:
                return True

        # All staff/administration actions require the user to actually be staff or have staff rank
        is_user_staff = PermissionHandler.is_staff(member)
        if not is_user_staff:
            return False

        # Category-specific roles check if ticket_data is provided
        if ticket_data and guild:
            panel_id = ticket_data.get("panel_id")
            category_id = ticket_data.get("category_id")
            if panel_id and category_id:
                panel = db.get_panel_by_id(panel_id)
                if panel:
                    for cat in panel.get("categories", []):
                        if str(cat.get("id")) == str(category_id):
                            cat_roles = cat.get("support_role_ids", [])
                            if not cat_roles and cat.get("support_role_id"):
                                cat_roles = [cat.get("support_role_id")]
                            
                            user_role_ids = [r.id for r in member.roles]
                            if any(rid and str(rid).isdigit() and int(rid) in user_role_ids for rid in cat_roles):
                                return True
                            break

        # DB dynamic action permissions
        if guild:
            perm = db.get_action_permission(guild.id, action_name)
            if perm:
                allowed_roles = perm.get("allowed_roles", [])
                min_rank = perm.get("min_rank", 10)
                
                if allowed_roles:
                    user_role_ids = [r.id for r in member.roles]
                    if any(rid in user_role_ids for rid in allowed_roles):
                        return True

                user_rank = PermissionHandler.get_member_rank(member)
                if user_rank >= min_rank:
                    return True
                return False

        # Default hierarchy checks
        user_rank = PermissionHandler.get_member_rank(member)

        # Staff actions
        if action_name in [
            "claim", "unclaim", "transfer", "priority", "rename", "department",
            "lock", "unlock", "hold", "resume", "hold_resume", "toggle_hold", "summon_member",
            "add_note", "pin_ticket", "generate_transcript", "export_transcript",
            "reopen", "audit_log", "toggle_hide", "restart"
        ]:
            claimed_by = ticket_data.get("claimed_by") if ticket_data else None
            if action_name != "claim" and not claimed_by:
                if user_rank < PermissionHandler.ROLE_HIERARCHY["admin"]:
                    return False
            if claimed_by and member.id != claimed_by:
                if user_rank < PermissionHandler.ROLE_HIERARCHY["admin"]:
                    return False
            return user_rank >= PermissionHandler.ROLE_HIERARCHY["support"]

        # High-privilege Admin actions
        if action_name in ["delete", "owner"]:
            return user_rank >= PermissionHandler.ROLE_HIERARCHY["support_manager"]

        return False

    @staticmethod
    async def set_ticket_visibility(channel: discord.TextChannel, guild: discord.Guild, ticket: dict, is_hidden: bool):
        guild_id = guild.id
        settings = db.get_guild_settings(guild_id) or {}
        ticket_user_id = ticket.get("user_id")
        claimed_by = ticket.get("claimed_by")
        category_id = ticket.get("category_id")
        panel_id = ticket.get("panel_id")

        cat_support_roles = []
        if panel_id:
            panel = db.get_panel_by_id(panel_id)
            if panel and panel.get("categories"):
                for cat in panel.get("categories", []):
                    if str(cat.get("id")) == str(category_id):
                        cat_support_roles = cat.get("support_role_ids", [])
                        break

        staff_role_ids = set()
        for r_key in ["support_role_id", "senior_support_role_id", "admin_role_id", "support_manager_role_id", "owner_role_id"]:
            val = settings.get(r_key)
            if val and str(val).isdigit():
                staff_role_ids.add(int(val))
        for r_id in cat_support_roles:
            if r_id and str(r_id).isdigit():
                staff_role_ids.add(int(r_id))

        overwrites = channel.overwrites.copy()

        # Default role (@everyone)
        overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=False, read_messages=False)

        # Handle management / staff roles
        for role_id in staff_role_ids:
            role = guild.get_role(role_id)
            if role:
                if is_hidden:
                    # Hide: Management roles cannot view the channel
                    overwrites[role] = discord.PermissionOverwrite(view_channel=False, read_messages=False)
                else:
                    # Show: Restore visibility to management roles, BUT read-only (without send_messages)
                    overwrites[role] = discord.PermissionOverwrite(view_channel=True, read_messages=True, send_messages=False)

        # Ticket owner (صاحب التذكرة)
        owner = guild.get_member(ticket_user_id) if ticket_user_id else None
        if not owner and ticket_user_id:
            try:
                owner = await guild.fetch_member(ticket_user_id)
            except Exception:
                owner = None
        if owner:
            can_send = True if ticket.get("status") in ["open", "claimed"] else False
            overwrites[owner] = discord.PermissionOverwrite(view_channel=True, read_messages=True, send_messages=can_send, attach_files=can_send, embed_links=can_send)

        # Claimed staff member (مستلم التذكرة)
        if claimed_by:
            claimed_member = guild.get_member(claimed_by)
            if not claimed_member:
                try:
                    claimed_member = await guild.fetch_member(claimed_by)
                except Exception:
                    claimed_member = None
            if claimed_member:
                overwrites[claimed_member] = discord.PermissionOverwrite(
                    view_channel=True, read_messages=True, send_messages=True, attach_files=True, embed_links=True, manage_messages=True
                )

        # Bot
        bot_member = guild.me
        if bot_member:
            overwrites[bot_member] = discord.PermissionOverwrite(
                view_channel=True, read_messages=True, send_messages=True, manage_channels=True, manage_messages=True, attach_files=True, embed_links=True
            )

        await channel.edit(overwrites=overwrites)
        db.update_ticket_hidden(channel.id, 1 if is_hidden else 0)

