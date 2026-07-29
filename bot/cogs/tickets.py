import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from bot.database.db import db
from bot.views.panel_view import PanelView
from bot.utils.embeds import EmbedBuilder
from bot.utils.permissions import PermissionHandler

class TicketsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup_panel", description="إنشاء لوحة تذاكر بايمبد مخصص وصورة السيرفر / Post custom ticket panel embed")
    @app_commands.describe(
        title="عنوان اللوحة (مثال: مركز الدعم الفني والتذاكر)",
        description="وصف اللوحة والتعليمات الخاصة بالعملاء",
        color_hex="رمز اللون بالتنسيق السداسي عشر (مثال: 5865F2 أو 10b981)",
        image_url="رابط صورة الهيدر أو البانل الكبير (اختياري)",
        footer_text="نص الهامش السفلي المخصص (اختياري)",
        category1_name="اسم القسم 1 (مثال: الدعم الفني)",
        category1_emoji="إيموجي القسم 1 (مثال: 💬)",
        category1_desc="وصف قصير للقسم 1",
        category2_name="اسم القسم 2 (مثال: الشكاوى والمبيعات)",
        category2_emoji="إيموجي القسم 2 (مثال: 💳)",
        category2_desc="وصف قصير للقسم 2",
        category3_name="اسم القسم 3 (اختياري)",
        category3_emoji="إيموجي القسم 3",
        category3_desc="وصف قصير للقسم 3",
        category4_name="اسم القسم 4 (اختياري)",
        category4_emoji="إيموجي القسم 4",
        category4_desc="وصف قصير للقسم 4",
        category5_name="اسم القسم 5 (اختياري)",
        category5_emoji="إيموجي القسم 5",
        category5_desc="وصف قصير للقسم 5"
    )
    async def setup_panel(
        self,
        interaction: discord.Interaction,
        title: str = "مركز الدعم الفني والتذاكر",
        description: str = "أهلاً بك! يرجى اختيار القسم المناسب من القائمة المنسدلة أسفله لفتح تذكرة مباشرة مع طاقم الدعم.",
        color_hex: str = "5865F2",
        image_url: Optional[str] = None,
        footer_text: Optional[str] = None,
        category1_name: str = "دعم عام / General Support",
        category1_emoji: str = "💬",
        category1_desc: str = "انقر لفتح تذكرة للمساعدة العامة والاستفسارات",
        category1_points: int = 5,
        category2_name: str = "المبيعات والاشتراكات / Billing & Sales",
        category2_emoji: str = "💳",
        category2_desc: str = "انقر لفتح تذكرة بخصوص المبيعات والدفع",
        category2_points: int = 10,
        category3_name: Optional[str] = None,
        category3_emoji: Optional[str] = "⚙️",
        category3_desc: Optional[str] = None,
        category3_points: int = 5,
        category4_name: Optional[str] = None,
        category4_emoji: Optional[str] = "🛠️",
        category4_desc: Optional[str] = None,
        category4_points: int = 5,
        category5_name: Optional[str] = None,
        category5_emoji: Optional[str] = "⭐",
        category5_desc: Optional[str] = None,
        category5_points: int = 5
    ):
        if not PermissionHandler.is_staff(interaction.user):
            return await interaction.response.send_message("❌ تحتاج إلى صلاحيات الإدارة لاستخدام هذا الأمر.", ephemeral=True)

        try:
            clean_color = color_hex.replace("#", "").strip()
            color_int = int(clean_color, 16)
        except ValueError:
            color_int = EmbedBuilder.COLOR_PRIMARY

        # Construct categories list
        categories = []
        raw_cats = [
            (category1_name, category1_emoji, category1_desc, "cat_1", category1_points),
            (category2_name, category2_emoji, category2_desc, "cat_2", category2_points),
            (category3_name, category3_emoji, category3_desc, "cat_3", category3_points),
            (category4_name, category4_emoji, category4_desc, "cat_4", category4_points),
            (category5_name, category5_emoji, category5_desc, "cat_5", category5_points),
        ]

        for name, emoji, desc, cat_id, points in raw_cats:
            if name and name.strip():
                categories.append({
                    "id": cat_id,
                    "name": name.strip(),
                    "emoji": emoji.strip() if emoji else "🎫",
                    "description": desc.strip() if desc else "انقر لفتح تذكرة جديدة",
                    "points": points
                })

        if not categories:
            categories = [
                {"id": "cat_1", "name": "دعم عام", "emoji": "💬", "description": "تذكرة دعم عام"},
                {"id": "cat_2", "name": "المبيعات", "emoji": "💳", "description": "تذكرة مبيعات"}
            ]

        # 1. Save Panel to SQLite Database
        panel_id = db.save_panel(
            title=title,
            description=description,
            color=color_int,
            categories=categories,
            channel_id=interaction.channel_id,
            image_url=image_url,
            footer_text=footer_text
        )

        # 2. Construct Embed featuring Server Icon (صورة السيرفر) as thumbnail & footer icon
        embed = EmbedBuilder.panel_embed(
            title=title,
            description=description,
            color=color_int,
            guild=interaction.guild,
            image_url=image_url,
            footer_text=footer_text,
            categories=categories
        )

        # 3. Attach Panel View with Interactive Dropdown Select Menu
        view = PanelView(categories=categories, panel_id=panel_id)
        msg = await interaction.channel.send(embed=embed, view=view)

        # Update database with message_id
        db.update_panel_message_id(panel_id, msg.id)

        server_icon_status = "موجودة وتم تضمينها في الايمبد 🖼️" if (interaction.guild and interaction.guild.icon) else "غير محددة في السيرفر"

        await interaction.response.send_message(
            f"✅ **تم إنشاء ونشر لوحة التذاكر المخصصة بنجاح!**\n"
            f"• **معرف اللوحة:** `{panel_id}`\n"
            f"• **عدد الأقسام:** `{len(categories)}` قسم\n"
            f"• **صورة السيرفر:** {server_icon_status}\n"
            f"• **القناة:** {interaction.channel.mention}",
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketsCog(bot))
