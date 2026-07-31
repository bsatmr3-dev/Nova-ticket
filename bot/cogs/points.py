import discord
from discord.ext import commands
from discord import app_commands
from bot.database.db import db
from bot.utils.embeds import EmbedBuilder
from bot.utils.permissions import PermissionHandler
from typing import Optional

class PointsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="staff_info", description="عرض معلومات وإحصائيات عضو في طاقم الإدارة / View staff performance stats")
    @app_commands.describe(member="العضو المراد عرض إحصائياته (اتركه فارغاً لعرض إحصائياتك)")
    async def staff_info(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        target = member or interaction.user
        stats = db.get_staff_stats(interaction.guild_id, target.id)
        
        if not stats:
            return await interaction.response.send_message(f"❌ لا توجد بيانات مسجلة لـ {target.mention} في النظام.", ephemeral=True)

        points = stats.get("points", 0)
        tickets = stats.get("tickets_handled", 0)
        total_stars = stats.get("total_stars", 0)
        total_ratings = stats.get("total_ratings", 0)
        avg_rating = round(total_stars / total_ratings, 2) if total_ratings > 0 else 0

        embed = EmbedBuilder.create_embed(
            title=f"📊 إحصائيات الإداري | {target.display_name}",
            description=f"هذه هي الإحصائيات المسجلة لـ {target.mention} في نظام التذاكر.",
            color=EmbedBuilder.COLOR_PRIMARY
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        
        embed.add_field(name="💰 مجموع النقاط", value=f"**{points}** نقطة", inline=True)
        embed.add_field(name="🎫 تذاكر مستلمة", value=f"**{tickets}** تذكرة", inline=True)
        embed.add_field(name="⭐ متوسط التقييم", value=f"**{avg_rating} / 5** ({total_ratings} تقييم)", inline=True)
        
        # Rankings (optional but cool)
        all_stats = db.get_all_staff_stats(interaction.guild_id)
        rank = "غير مصنف"
        for i, s in enumerate(all_stats):
            if s["user_id"] == target.id:
                rank = f"#{i+1}"
                break
        embed.add_field(name="🏆 الترتيب", value=f"**{rank}** على مستوى الإدارة", inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="points_add", description="إضافة نقاط لعضو في طاقم الإدارة / Add points to a staff member")
    @app_commands.describe(member="العضو المراد إضافة النقاط له", points="عدد النقاط")
    async def points_add(self, interaction: discord.Interaction, member: discord.Member, points: int):
        if not PermissionHandler.is_admin(interaction.user):
            return await interaction.response.send_message("❌ هذا الأمر مخصص للإدارة العليا فقط.", ephemeral=True)
        
        db.update_staff_points(interaction.guild_id, member.id, points)
        await interaction.response.send_message(f"✅ تم إضافة **{points}** نقطة لـ {member.mention} بنجاح.")

    @app_commands.command(name="points_remove", description="خصم نقاط من عضو في طاقم الإدارة / Remove points from a staff member")
    @app_commands.describe(member="العضو المراد خصم النقاط منه", points="عدد النقاط")
    async def points_remove(self, interaction: discord.Interaction, member: discord.Member, points: int):
        if not PermissionHandler.is_admin(interaction.user):
            return await interaction.response.send_message("❌ هذا الأمر مخصص للإدارة العليا فقط.", ephemeral=True)
        
        db.update_staff_points(interaction.guild_id, member.id, -points)
        await interaction.response.send_message(f"✅ تم خصم **{points}** نقطة من {member.mention} بنجاح.")

    @app_commands.command(name="points_reset", description="تصفير نقاط عضو أو جميع طاقم الإدارة / Reset points for one or all staff")
    @app_commands.describe(member="العضو المراد تصفير نقاطه (اتركه فارغاً لتصفير نقاط الجميع)")
    async def points_reset(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        if not PermissionHandler.is_admin(interaction.user):
            return await interaction.response.send_message("❌ هذا الأمر مخصص للإدارة العليا فقط.", ephemeral=True)
        
        if member:
            db.reset_staff_points(interaction.guild_id, member.id)
            await interaction.response.send_message(f"✅ تم تصفير نقاط {member.mention} بنجاح.")
        else:
            db.reset_staff_points(interaction.guild_id)
            await interaction.response.send_message("✅ تم تصفير نقاط جميع أعضاء طاقم الإدارة بنجاح.")

    # Prefix Commands
    @commands.command(name="اضافة")
    async def prefix_add_points(self, ctx: commands.Context, member: discord.Member, points: int):
        if not PermissionHandler.is_admin(ctx.author):
            return await ctx.send("❌ هذا الأمر مخصص للإدارة العليا فقط.")
        
        db.update_staff_points(ctx.guild.id, member.id, points)
        await ctx.send(f"✅ تم إضافة **{points}** نقطة لـ {member.mention} بنجاح.")

    @commands.command(name="خصم")
    async def prefix_remove_points(self, ctx: commands.Context, member: discord.Member, points: int):
        if not PermissionHandler.is_admin(ctx.author):
            return await ctx.send("❌ هذا الأمر مخصص للإدارة العليا فقط.")
        
        db.update_staff_points(ctx.guild.id, member.id, -points)
        await ctx.send(f"✅ تم خصم **{points}** نقطة من {member.mention} بنجاح.")

async def setup(bot: commands.Bot):
    await bot.add_cog(PointsCog(bot))
