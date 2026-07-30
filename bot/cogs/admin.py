import discord
from discord.ext import commands
from discord import app_commands
from bot.database.db import db
from bot.database.backup import BackupManager
from bot.utils.permissions import PermissionHandler

class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="blacklist_add", description="Blacklist user from tickets / حظر شخص من التذاكر")
    async def blacklist_add(self, interaction: discord.Interaction, user: discord.User, reason: str = "Violation of ticket rules"):
        if not PermissionHandler.is_staff(interaction.user):
            return await interaction.response.send_message("❌ Admin privileges required.", ephemeral=True)

        db.blacklist_user(user.id, reason, interaction.user.id)
        await interaction.response.send_message(f"🚫 User {user.mention} has been blacklisted from tickets.\nReason: {reason}")

    @app_commands.command(name="blacklist_remove", description="Remove user from blacklist / إلغاء حظر التذاكر")
    async def blacklist_remove(self, interaction: discord.Interaction, user: discord.User):
        if not PermissionHandler.is_staff(interaction.user):
            return await interaction.response.send_message("❌ Admin privileges required.", ephemeral=True)

        db.unblacklist_user(user.id)
        await interaction.response.send_message(f"✅ User {user.mention} removed from blacklist.")

    @app_commands.command(name="backup_db", description="Create PostgreSQL JSON backup / إنشاء نسخة احتياطية من قاعدة البيانات")
    async def backup_db(self, interaction: discord.Interaction):
        if not PermissionHandler.is_staff(interaction.user):
            return await interaction.response.send_message("❌ Admin privileges required.", ephemeral=True)

        try:
            backup_file = BackupManager.create_backup()
            await interaction.response.send_message(f"💾 Database backup created: `{backup_file}`", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Backup failed: {e}", ephemeral=True)

    @app_commands.command(name="set_log_channel", description="تعيين قناة سجلات العمليات (Logs) / Set action logs channel")
    async def set_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ تحتاج إلى صلاحيات المسؤول لتنفيذ هذا الأمر.", ephemeral=True)

        db.set_guild_setting(interaction.guild_id, "log_channel_id", channel.id)
        await interaction.response.send_message(f"✅ تم تعيين قناة **سجلات العمليات** بنجاح إلى: {channel.mention}", ephemeral=True)

    @app_commands.command(name="set_transcript_channel", description="تعيين قناة سجلات المحادثات (Transcripts) / Set transcripts channel")
    async def set_transcript_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ تحتاج إلى صلاحيات المسؤول لتنفيذ هذا الأمر.", ephemeral=True)

        db.set_guild_setting(interaction.guild_id, "transcript_channel_id", channel.id)
        await interaction.response.send_message(f"✅ تم تعيين قناة **سجلات المحادثات (Scripts)** بنجاح إلى: {channel.mention}", ephemeral=True)

    @app_commands.command(name="set_action_perm", description="Configure action permissions / تخصيص صلاحيات الإجراءات")
    @app_commands.choices(action_name=[
        app_commands.Choice(name="📌 استلام التذكرة (claim)", value="claim"),
        app_commands.Choice(name="🔒 إغلاق التذكرة (close)", value="close"),
        app_commands.Choice(name="🗑️ حذف التذكرة (delete)", value="delete"),
        app_commands.Choice(name="🔄 نقل التذكرة (transfer)", value="transfer"),
        app_commands.Choice(name="⚡ أولوية التذكرة (priority)", value="priority"),
        app_commands.Choice(name="✏️ تغيير الاسم (rename)", value="rename"),
        app_commands.Choice(name="🏢 تغيير القسم (department)", value="department"),
        app_commands.Choice(name="👤 مالك التذكرة (owner)", value="owner"),
        app_commands.Choice(name="➕ إضافة عضو (add_member)", value="add_member"),
        app_commands.Choice(name="➖ إزالة عضو (remove_member)", value="remove_member"),
        app_commands.Choice(name="🔐 قفل التذكرة (lock)", value="lock"),
        app_commands.Choice(name="📝 ملاحظات داخلية (add_note)", value="add_note"),
        app_commands.Choice(name="📄 Transcript", value="generate_transcript"),
    ])
    @app_commands.choices(min_rank=[
        app_commands.Choice(name="الجميع (Everyone - 0)", value=0),
        app_commands.Choice(name="الدعم الفني (Support Staff - 10)", value=10),
        app_commands.Choice(name="سينيور دعم (Senior Support - 20)", value=20),
        app_commands.Choice(name="مدير الدعم (Support Manager - 30)", value=30),
        app_commands.Choice(name="المدير العام (Admin - 40)", value=40),
    ])
    async def set_action_perm(
        self,
        interaction: discord.Interaction,
        action_name: str,
        min_rank: int,
        role: discord.Role = None
    ):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Administrator permission required.", ephemeral=True)

        allowed_roles = [role.id] if role else []
        db.set_action_permission(interaction.guild_id, action_name, min_rank=min_rank, allowed_roles=allowed_roles)

        role_str = role.mention if role else "غير محدد"
        await interaction.response.send_message(
            f"⚙️ **تم تحديث صلاحية الإجراء `{action_name}`:**\n"
            f"• الحد الأدنى للمستوى: `{min_rank}`\n"
            f"• الرتبة المحددة: {role_str}",
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
