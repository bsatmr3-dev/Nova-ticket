import discord
from discord.ext import commands
from discord import app_commands
from bot.views.control_panel_view import (
    MasterControlPanelView,
    build_master_control_embed,
    check_master_permission,
    send_no_perm,
    MASTER_OWNER_ID
)

class ControlPanelCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="control_panel", description="فتح لوحة التحكم الرئيسية الشاملة بالبوت والأزرار (للمالك والمدير)")
    async def control_panel(self, interaction: discord.Interaction):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
        except Exception:
            pass

        if not interaction.guild:
            return await interaction.followup.send("❌ يرجى استخدام هذا الأمر داخل سيرفر ديسكورد وليس في الرسائل الخاصة.", ephemeral=True)

        if not check_master_permission(interaction):
            return await interaction.followup.send(f"❌ **عفواً! هذه اللوحة مخصصة فقط لمالك البوت الرئيسي (<@{MASTER_OWNER_ID}>) وإدارة السيرفر.**", ephemeral=True)

        try:
            embed = build_master_control_embed(self.bot, interaction.guild)
            view = MasterControlPanelView(self.bot)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ حدث خطأ أثناء فتح لوحة التحكم:\n```{str(e)[:500]}```", ephemeral=True)

    @app_commands.command(name="bot_owner", description="عرض معلومات مالك البوت والتحكم الرئيسي")
    async def owner_info(self, interaction: discord.Interaction):
        owner_user = await self.bot.fetch_user(MASTER_OWNER_ID) if MASTER_OWNER_ID else None
        owner_name = owner_user.name if owner_user else "Master Owner"

        embed = discord.Embed(
            title="👑 مالك البوت والتحكم الرئيسي (Bot Owner)",
            description=(
                f"• **اسم المالك:** {owner_name}\n"
                f"• **معرف ديسكورد (ID):** `{MASTER_OWNER_ID}`\n"
                f"• **المنشن:** <@{MASTER_OWNER_ID}>\n\n"
                f"يمتلك هذا الحساب صلاحيات التحكم الكاملة بالبوت والأوامر والإعدادات من داخل ديسكورد عبر الأمر `/control_panel`."
            ),
            color=0x5865F2
        )
        if owner_user and owner_user.avatar:
            embed.set_thumbnail(url=owner_user.avatar.url)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="control", aliases=["control_panel", "cpanel", "لوحة", "تحكم"])
    async def prefix_control(self, ctx: commands.Context):
        if not ctx.guild:
            return await ctx.send("❌ يرجى استخدام هذا الأمر داخل السيرفر.")
        
        from bot.utils.permissions import PermissionHandler
        is_allowed = (
            PermissionHandler.is_bot_owner(ctx.author.id) or
            ctx.author.id == ctx.guild.owner_id or
            ctx.author.guild_permissions.administrator or
            ctx.author.guild_permissions.manage_guild or
            PermissionHandler.is_staff(ctx.author)
        )
        if not is_allowed:
            return await ctx.send(f"❌ **عفواً! هذه اللوحة مخصصة فقط لمالك البوت الرئيسي (<@{MASTER_OWNER_ID}>) وإدارة السيرفر.**")

        embed = build_master_control_embed(self.bot, ctx.guild)
        view = MasterControlPanelView(self.bot)
        await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(ControlPanelCog(bot))
