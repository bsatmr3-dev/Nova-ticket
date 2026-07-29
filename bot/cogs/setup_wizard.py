import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import json
import io
from bot.database.db import db
from bot.utils.embeds import EmbedBuilder
from bot.views.panel_view import PanelView
from bot.utils.permissions import PermissionHandler
from bot.views.setup_wizard_views import (
    PanelCreationState,
    PanelBasicInfoModal,
    InAppSettingsDashboardView,
    InteractivePanelEditorView,
    DeploymentSummaryView,
    ImportJsonModal,
    build_in_app_settings_embed,
    wizard_sessions,
    check_perm_or_deny,
    MASTER_OWNER_ID
)

class PanelGroup(app_commands.Group):
    def __init__(self, bot: commands.Bot):
        super().__init__(name="panel", description="إدارة وإنشاء وتعديل لوحات التذاكر بالكامل من داخل ديسكورد")
        self.bot = bot

    @app_commands.command(name="create", description="بدء معالج الإعداد التفاعلي خطوة بخطوة لإنشاء وتصميم لوحة تذاكر جديدة")
    async def panel_create(self, interaction: discord.Interaction):
        if not await check_perm_or_deny(interaction):
            return

        session = PanelCreationState(interaction.user.id, interaction.guild_id)
        wizard_sessions[interaction.user.id] = session
        session.auto_save()

        await interaction.response.send_modal(PanelBasicInfoModal(session))

    @app_commands.command(name="edit", description="تعديل تفاعلي شامل للوحة قائمة بكل تفاصيلها وأقسامها")
    @app_commands.describe(panel_id="معرف اللوحة المراد تعديلها (Panel ID)")
    async def panel_edit(self, interaction: discord.Interaction, panel_id: int):
        if not await check_perm_or_deny(interaction):
            return

        panel = db.get_panel_by_id(panel_id)
        if not panel:
            return await interaction.response.send_message(f"❌ لم يتم العثور على لوحة بالمعرف `{panel_id}`.", ephemeral=True)

        editor_view = InteractivePanelEditorView(self.bot, panel)
        embed = editor_view.build_editor_embed(interaction.guild)

        await interaction.response.send_message(embed=embed, view=editor_view, ephemeral=True)

    @app_commands.command(name="resume", description="استئناف معالج الإعداد خطوة بخطوة من آخر خطوة توقفت عندها (Setup Resume)")
    async def panel_resume(self, interaction: discord.Interaction):
        if not await check_perm_or_deny(interaction):
            return

        saved_data = db.get_wizard_session(interaction.user.id)
        if not saved_data:
            return await interaction.response.send_message("❌ لا توجد جلسة إعداد سابقة محفوظة لاستئنافها. يمكنك بدء معالج جديد عبر `/panel create`.", ephemeral=True)

        session = PanelCreationState.from_dict(saved_data)
        wizard_sessions[interaction.user.id] = session

        embed = discord.Embed(
            title="🔄 تم استئناف جلسة الإعداد التفاعلية بنجاح!",
            description=(
                f"• **عنوان اللوحة:** {session.panel_title}\n"
                f"• **عدد الأقسام المجهزة:** `{len(session.categories)}` من `{session.num_categories}`\n\n"
                f"📌 **يمكنك الاستمرار بنشر اللوحة أو مراجعة ملخص الإعداد:**"
            ),
            color=EmbedBuilder.COLOR_PRIMARY
        )

        view = DeploymentSummaryView(session)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="list", description="عرض جميع لوحات التذاكر المنشأة في هذا السيرفر مع التفاصيل والمعرفات")
    async def panel_list(self, interaction: discord.Interaction):
        if not await check_perm_or_deny(interaction):
            return

        panels = db.get_panels() or []
        if not panels:
            return await interaction.response.send_message("❌ لا توجد لوحات تذاكر منشأة حالياً في هذا السيرفر.", ephemeral=True)

        embed = discord.Embed(
            title="🎯 قائمة لوحات التذاكر المنشأة في السيرفر",
            description=f"إجمالي اللوحات: `{len(panels)}`",
            color=EmbedBuilder.COLOR_PRIMARY
        )

        for p in panels:
            ch_str = f"<#{p.get('channel_id')}>" if p.get("channel_id") else "غير مفعّلة"
            cats = p.get("categories", [])
            cat_names = ", ".join([f"{c.get('emoji', '🎫')} {c.get('name', 'قسم')}" for c in cats]) or "لا توجد أقسام"

            embed.add_field(
                name=f"• اللوحة #{p['id']}: {p['title']}",
                value=(
                    f"• **القناة:** {ch_str}\n"
                    f"• **معرف الرسالة:** `{p.get('message_id', 'غير محدد')}`\n"
                    f"• **الأقسام ({len(cats)}):** {cat_names}"
                ),
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="delete", description="حذف لوحة تذاكر معينة بواسطة المعرف (ID)")
    @app_commands.describe(panel_id="معرف اللوحة (Panel ID)")
    async def panel_delete(self, interaction: discord.Interaction, panel_id: int):
        if not await check_perm_or_deny(interaction):
            return

        panel = db.get_panel_by_id(panel_id)
        if not panel:
            return await interaction.response.send_message(f"❌ لم يتم العثور على لوحة بالمعرف `{panel_id}`.", ephemeral=True)

        db.delete_panel(panel_id)
        db.log_settings_change(interaction.guild_id, interaction.user.id, "DELETE_PANEL", f"Deleted panel #{panel_id}")
        await interaction.response.send_message(f"✅ **تم حذف اللوحة #{panel_id} ({panel['title']}) بنجاح.**", ephemeral=True)

    @app_commands.command(name="send", description="إعادة إرسال أو نقل لوحة تذاكر موجودة إلى قناة محددة")
    @app_commands.describe(panel_id="معرف اللوحة", channel="القناة المراد إرسال اللوحة إليها")
    async def panel_send(self, interaction: discord.Interaction, panel_id: int, channel: discord.TextChannel):
        if not await check_perm_or_deny(interaction):
            return

        panel = db.get_panel_by_id(panel_id)
        if not panel:
            return await interaction.response.send_message(f"❌ لم يتم العثور على لوحة بالمعرف `{panel_id}`.", ephemeral=True)

        categories = panel.get("categories", [])
        panel_embed = EmbedBuilder.panel_embed(
            title=panel["title"],
            description=panel["description"],
            color=panel.get("color", EmbedBuilder.COLOR_PRIMARY),
            guild=interaction.guild,
            image_url=panel.get("image_url"),
            categories=categories
        )

        panel_view = PanelView(categories=categories, panel_id=panel_id)

        msg = await channel.send(embed=panel_embed, view=panel_view)
        db.update_panel_message_id(panel_id, msg.id)

        await interaction.response.send_message(
            f"✅ **تم إرسال اللوحة #{panel_id} بنجاح إلى القناة {channel.mention}!**",
            ephemeral=True
        )


class SettingsGroup(app_commands.Group):
    def __init__(self, bot: commands.Bot):
        super().__init__(name="settings", description="إدارة وتعديل واستيراد وتصدير إعدادات البوت والسجلات")
        self.bot = bot

    @app_commands.command(name="dashboard", description="فتح شاشة التحكم الرئيسية بالكامل لإعدادات البوت")
    async def settings_dash(self, interaction: discord.Interaction):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
        except Exception:
            pass

        if not await check_perm_or_deny(interaction):
            return

        embed = build_in_app_settings_embed(self.bot, interaction.guild)
        view = InAppSettingsDashboardView(self.bot, interaction.guild)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="export", description="تصدير جميع إعدادات ولوحات البوت إلى ملف JSON للنسخ الاحتياطي أو النقل")
    async def settings_export(self, interaction: discord.Interaction):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
        except Exception:
            pass

        if not await check_perm_or_deny(interaction):
            return

        config_data = db.export_guild_config(interaction.guild_id)
        json_bytes = json.dumps(config_data, indent=2, ensure_ascii=False).encode("utf-8")
        file = discord.File(io.BytesIO(json_bytes), filename=f"ticket_bot_config_{interaction.guild_id}.json")

        await interaction.followup.send(
            "📤 **تم تصدير إعدادات السيرفر ولوحات التذاكر بنجاح! احتفظ بهذا الملف للاستيراد في سيرفر آخر:**",
            file=file,
            ephemeral=True
        )

    @app_commands.command(name="import", description="استيراد إعدادات ولوحات البوت مباشرة من ملف أو كود JSON")
    async def settings_import(self, interaction: discord.Interaction, file: Optional[discord.Attachment] = None):
        if not await check_perm_or_deny(interaction):
            return

        if file:
            try:
                content = await file.read()
                data = json.loads(content.decode("utf-8"))
                db.import_guild_config(interaction.guild_id, data, interaction.user.id)
                await interaction.response.send_message("✅ **تم استيراد كافة الإعدادات واللوحات بنجاح من الملف المرفق!**", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ فشل استيراد ملف JSON: {e}", ephemeral=True)
        else:
            await interaction.response.send_modal(ImportJsonModal())

    @app_commands.command(name="logs", description="عرض سجل تغييرات وتعديلات الإعدادات (Audit Log)")
    async def settings_logs(self, interaction: discord.Interaction):
        if not await check_perm_or_deny(interaction):
            return

        logs = db.get_settings_audit_logs(interaction.guild_id, limit=15)
        if not logs:
            log_text = "لا توجد تغييرات مسجلة بعد."
        else:
            log_text = "\n".join([
                f"• **{l['action']}** بواسطة <@{l['executor_id']}> ({l['created_at'][:19]}): {l.get('details', '')}"
                for l in logs
            ])

        embed = discord.Embed(
            title="📜 سجل تغييرات الإعدادات (Audit Log)",
            description=log_text,
            color=EmbedBuilder.COLOR_PRIMARY
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="language", description="تغيير لغة البوت داخل السيرفر (العربية / English)")
    async def settings_language(self, interaction: discord.Interaction):
        if not await check_perm_or_deny(interaction):
            return

        curr_lang = db.get_guild_setting(interaction.guild_id, "language", "ar")
        new_lang = "en" if curr_lang == "ar" else "ar"
        db.set_guild_setting(interaction.guild_id, "language", new_lang)
        db.log_settings_change(interaction.guild_id, interaction.user.id, "CHANGE_LANGUAGE", f"Language set to {new_lang}")

        await interaction.response.send_message(
            f"🌐 **تم تغيير لغة البوت إلى:** `{'العربية 🇸🇦' if new_lang == 'ar' else 'English 🇬🇧'}`",
            ephemeral=True
        )


class SetupWizardCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Register slash groups
        self.bot.tree.add_command(PanelGroup(bot))
        self.bot.tree.add_command(SettingsGroup(bot))

    async def cog_unload(self):
        self.bot.tree.remove_command("panel")
        self.bot.tree.remove_command("settings")

    @app_commands.command(name="setup", description="معالج الإعداد التفاعلي الشامل للبوت واللوحات بدون موقع خارجي")
    async def setup_command(self, interaction: discord.Interaction):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
        except Exception:
            pass

        if not await check_perm_or_deny(interaction):
            return

        embed = build_in_app_settings_embed(self.bot, interaction.guild)
        view = InAppSettingsDashboardView(self.bot, interaction.guild)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupWizardCog(bot))
