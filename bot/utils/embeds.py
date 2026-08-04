import discord
from typing import Optional
from bot.config.locales import get_text

class EmbedBuilder:
    COLOR_PRIMARY = 0x5865F2 # Discord Blurple
    COLOR_SUCCESS = 0x57F287 # Emerald
    COLOR_WARNING = 0xFEE75C # Gold
    COLOR_DANGER = 0xED4245  # Coral Red
    COLOR_INFO = 0x00B0F4    # Cyan Blue

    @staticmethod
    def create_embed(
        title: str,
        description: str = "",
        color: int = COLOR_PRIMARY,
        thumbnail_url: Optional[str] = None,
        image_url: Optional[str] = None,
        footer_text: Optional[str] = "Discord Advanced Ticket System",
        footer_icon: Optional[str] = None
    ) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=color)
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        if image_url:
            embed.set_image(url=image_url)
        if footer_text:
            embed.set_footer(text=footer_text, icon_url=footer_icon)
        return embed

    @staticmethod
    def panel_embed(
        title: str,
        description: str,
        color: int = COLOR_PRIMARY,
        guild: Optional[discord.Guild] = None,
        image_url: Optional[str] = None,
        footer_text: Optional[str] = None,
        categories: Optional[list] = None
    ) -> discord.Embed:
        embed_title = title if ("🎫" in title or "📌" in title) else f"🎫 {title}"
        embed = discord.Embed(title=embed_title, description=description, color=color)

        server_icon = guild.icon.url if (guild and guild.icon) else None

        # Set server icon as thumbnail
        if server_icon:
            embed.set_thumbnail(url=server_icon)

        # Optional banner image
        if image_url:
            embed.set_image(url=image_url)

        # Show categories summary in embed if provided
        if categories:
            cat_lines = []
            for cat in categories:
                emoji = cat.get('emoji', '📌')
                name = cat.get('name', 'قسم')
                desc = cat.get('description', '')
                cat_lines.append(f"{emoji} **{name}**\n↳ {desc}")
            if cat_lines:
                embed.add_field(
                    name="📂 الأقسام المتاحة / Available Categories:",
                    value="\n\n".join(cat_lines),
                    inline=False
                )

        footer = footer_text or (f"🏰 {guild.name} • نظام التذاكر المتقدم" if guild else "نظام التذاكر المتقدم")
        embed.set_footer(text=footer, icon_url=server_icon)
        embed.timestamp = discord.utils.utcnow()
        return embed

    @staticmethod
    def ticket_welcome_embed(user: discord.Member, category_name: str, lang: str = "ar", guild: Optional[discord.Guild] = None) -> discord.Embed:
        server_name = guild.name if guild else "Discord Server"
        server_icon = guild.icon.url if (guild and guild.icon) else None

        embed = discord.Embed(
            title=f"🎫 مرحباً بك في تذكرة الدعم الفني - {category_name}",
            description=(
                f"أهلاً بك {user.mention} 👋 في مركز الدعم الفني الخاص بـ **{server_name}**.\n\n"
                f"يرجى توضيح تفاصيل طلبك أو مشكلتك بالتفصيل وسيقوم أحد أعضاء طاقم الدعم المساعد بتقديم الخدمة لك بأسرع وقت."
            ),
            color=EmbedBuilder.COLOR_PRIMARY
        )
        
        if server_icon:
            embed.set_author(name=f"🏰 {server_name}", icon_url=server_icon)
        else:
            embed.set_author(name=f"👤 صاحب التذكرة: {user.display_name}")

        embed.set_thumbnail(url=user.display_avatar.url)
        
        embed.add_field(name="👤 صاحب التذكرة / Owner", value=f"{user.mention}\n`({user.id})`", inline=True)
        embed.add_field(name="🏷️ قسم التذكرة / Category", value=f"`{category_name}`", inline=True)
        embed.add_field(name="📌 الأولوية / Priority", value="`عادية 🟢`", inline=True)
        embed.add_field(
            name="📷 إرسال المرفقات والأدلة",
            value="يمكنك إرفاق أية صور أو فيديوهات أو ملفات مباشرة هنا في القناة ليتم حفظها كدليل في التذكرة.",
            inline=False
        )

        footer_text = f"🏰 {server_name} • نظام التذاكر المتقدم"
        embed.set_footer(text=footer_text, icon_url=server_icon or user.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()
        return embed

    @staticmethod
    def log_embed(title: str, description: str, fields: dict = None, color: int = COLOR_INFO) -> discord.Embed:
        embed = discord.Embed(title=f"📋 [LOG] {title}", description=description, color=color)
        if fields:
            for k, v in fields.items():
                embed.add_field(name=k, value=str(v), inline=True)
        embed.timestamp = discord.utils.utcnow()
        return embed
