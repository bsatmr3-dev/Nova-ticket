import discord
from discord.ext import commands
from discord import app_commands
from bot.utils.embeds import EmbedBuilder

class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="bot_help", description="Show detailed bot help / عرض تعليمات البوت بالتفصيل")
    async def show_help(self, interaction: discord.Interaction):
        embed = EmbedBuilder.create_embed(
            title="📖 دليل أوامر بوت التذاكر المتطور",
            description="إليك قائمة شاملة بجميع الأوامر المتاحة في البوت مع شرح لكل منها:",
            color=EmbedBuilder.COLOR_INFO
        )

        # Basic Commands
        embed.add_field(
            name="🛠️ أوامر الإعداد (Staff/Admin)",
            value=(
                "• `/setup_panel`: إنشاء لوحة تذاكر جديدة (Embed + Buttons).\n"
                "• `/manage_panels`: إدارة اللوحات الحالية (تعديل/حذف).\n"
                "• `/settings`: لوحة التحكم الشاملة في إعدادات البوت والأدوار."
            ),
            inline=False
        )

        # Ticket Commands
        embed.add_field(
            name="🎫 أوامر إدارة التذاكر",
            value=(
                "• `/ticket_stats`: عرض إحصائيات الأداء والتذاكر.\n"
                "• `/blacklist`: إضافة أو إزالة عضو من قائمة الحظر.\n"
                "• `/view_ratings`: عرض تقييمات الموظفين.\n"
                "• `/audit_log`: عرض سجل العمليات لتذكرة معينة."
            ),
            inline=False
        )

        # Detailed Explanation for Menu Options
        embed.add_field(
            name="💡 شرح قائمة التحكم (داخل التذكرة)",
            value=(
                "**1. استلام التذكرة:** يجعل التذكرة خاصة بك ويمنع الموظفين الآخرين من الكتابة.\n"
                "**2. إخفاء التذكرة:** يخفي القناة عن جميع الموظفين ماعدا المستلم وصاحب التذكرة.\n"
                "**3. استدعاء العضو:** يرسل تنبيهاً خاصاً (DM) للعضو ليقوم بالرد.\n"
                "**4. قفل التذكرة:** يمنع العضو من الكتابة مؤقتاً.\n"
                "**5. الحذف النهائي:** يولد Transcript ويرسل نسخة للمالك والموظف ثم يحذف القناة."
            ),
            inline=False
        )

        embed.add_field(
            name="📝 أمثلة الاستخدام",
            value=(
                "• لتغيير أولوية تذكرة: اختر 'تغيير الأولوية' من القائمة المنسدلة.\n"
                "• لمسح تقييمات موظف: `/clear_ratings @Staff`.\n"
                "• لرؤية أداء البوت: `/ticket_stats`."
            ),
            inline=False
        )

        embed.set_footer(text="Discord Advanced Ticket System")
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
