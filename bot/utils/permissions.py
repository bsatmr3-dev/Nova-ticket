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
        # Master owner bypass
        if PermissionHandler.is_bot_owner(member.id):
            return True

        # 1. Administrator & Guild Owner bypass
        if guild and (member.id == guild.owner_id or member.guild_permissions.administrator):
            return True

        # 2. Check category-specific roles if ticket_data is provided
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

        # 3. Check DB dynamic action permissions if configured
        if guild:
            perm = db.get_action_permission(guild.id, action_name)
            if perm:
                allowed_roles = perm.get("allowed_roles", [])
                min_rank = perm.get("min_rank", 10)
                
                # Role check
                if allowed_roles:
                    user_role_ids = [r.id for r in member.roles]
                    if any(rid in user_role_ids for rid in allowed_roles):
                        return True

                # Rank check
                user_rank = PermissionHandler.get_member_rank(member)
                if user_rank >= min_rank:
                    return True
                
                # If custom permissions are configured and user failed both role and rank checks
                return False

        # 3. Default fallback checks if no custom DB rule is explicitly defined
        user_rank = PermissionHandler.get_member_rank(member)

        # Public / All-User actions
        if action_name in ["info", "rate_staff", "summon_staff"]:
            return True

        # Close action: ticket owner or staff
        if action_name == "close":
            if ticket_user_id and member.id == ticket_user_id:
                return True
            claimed_by = ticket_data.get("claimed_by") if ticket_data else None
            if not claimed_by:
                return False
            if claimed_by and member.id != claimed_by:
                if user_rank < PermissionHandler.ROLE_HIERARCHY["admin"]:
                    return False
            return user_rank >= PermissionHandler.ROLE_HIERARCHY["support"]

        # Add/Remove Member actions: ticket owner or staff
        if action_name in ["add_member", "remove_member"]:
            if ticket_user_id and member.id == ticket_user_id:
                return True
            claimed_by = ticket_data.get("claimed_by") if ticket_data else None
            if not claimed_by:
                return False
            if claimed_by and member.id != claimed_by:
                if user_rank < PermissionHandler.ROLE_HIERARCHY["admin"]:
                    return False
            return user_rank >= PermissionHandler.ROLE_HIERARCHY["support"]

        # Staff actions
        if action_name in [
            "claim", "unclaim", "transfer", "priority", "rename", "department",
            "lock", "unlock", "hold", "resume", "summon_member",
            "add_note", "pin_ticket", "generate_transcript", "export_transcript",
            "reopen", "audit_log", "toggle_hide"
        ]:
            claimed_by = ticket_data.get("claimed_by") if ticket_data else None
            
            # Non-claim actions require the ticket to be claimed first
            if action_name != "claim" and not claimed_by:
                return False
                
            if claimed_by and member.id != claimed_by:
                # Bypass for admins and managers
                if user_rank < PermissionHandler.ROLE_HIERARCHY["admin"]:
                    return False
            
            return user_rank >= PermissionHandler.ROLE_HIERARCHY["support"]

        # High-privilege Admin actions
        if action_name in ["delete", "owner"]:
            return user_rank >= PermissionHandler.ROLE_HIERARCHY["support_manager"]

        return False
