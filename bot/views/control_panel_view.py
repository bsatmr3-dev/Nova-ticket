import discord
from discord.ui import View, Button, Select, Modal, TextInput
import io
import time
from bot.database.db import db
from bot.database.backup import BackupManager
from bot.config.settings import Config
from bot.utils.permissions import PermissionHandler
from bot.utils.embeds import EmbedBuilder
from bot.views.panel_view import PanelView

MASTER_OWNER_ID = 1406547827865288786

def check_master_permission(interaction: discord.Interaction) -> bool:
    if not interaction.user:
        return False
    if PermissionHandler.is_bot_owner(interaction.user.id):
        return True
    if isinstance(interaction.user, discord.Member):
        if PermissionHandler.is_staff(interaction.user):
            return True
        if interaction.guild and interaction.guild.owner_id == interaction.user.id:
            return True
        perms = interaction.user.guild_permissions
        if perms.administrator or perms.manage_guild or perms.manage_channels or perms.manage_roles:
            return True
    return False

async def send_no_perm(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"❌ **عفواً! هذه اللوحة مخصصة فقط لمالك البوت الرئيسي (<@{MASTER_OWNER_ID}>) وإدارة السيرفر.**",
        ephemeral=True
    )

# --- Modals ---

class QuickSetupPanelModal(Modal):
    def __init__(self, target_channel_id: int):
        super().__init__(title="🎯 إنشاء لوحة تذاكر مخصصة")
        self.target_channel_id = target_channel_id

        self.panel_title = TextInput(
            label="عنوان اللوحة",
            default="مركز الدعم الفني والتذاكر",
            required=True,
            max_length=100
        )
        self.panel_desc = TextInput(
            label="وصف اللوحة والتعليمات",
            default="مرحباً بك! اختَر القسم المناسب من القائمة أسفله لفتح تذكرة مباشرة مع طاقم الدعم.",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )
        self.categories_input = TextInput(
            label="أقسام التذاكر (اكتب كل قسم في سطر)",
            default="💬 الدعم الفني العام\n💳 المبيعات والاشتراكات\n🚨 البلاغات والشكاوى\n🎮 الشحن والخدمات",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )
        self.questions_input = TextInput(
            label="الأسئلة التفاعلية عند فتح التذكرة (سؤال بسطر)",
            default="سبب فتح التذكرة\nتفاصيل الطلب أو المشكلة\nأي معلومات إضافية / المعرّف",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000
        )
        self.image_url = TextInput(
            label="رابط صورة الهيدر (اختياري)",
            placeholder="https://example.com/banner.png",
            required=False,
            max_length=300
        )

        self.add_item(self.panel_title)
        self.add_item(self.panel_desc)
        self.add_item(self.categories_input)
        self.add_item(self.questions_input)
        self.add_item(self.image_url)

    async def on_submit(self, interaction: discord.Interaction):
        if not check_master_permission(interaction):
            return await send_no_perm(interaction)

        channel = interaction.guild.get_channel(self.target_channel_id) or interaction.channel
        if not channel:
            return await interaction.response.send_message("❌ القناة المحددة غير صالحة.", ephemeral=True)

        # Parse questions
        raw_questions = [q.strip() for q in self.questions_input.value.strip().split("\n") if q.strip()]
        formatted_questions = []
        for idx, q_label in enumerate(raw_questions[:5]):
            style_type = "paragraph" if idx == 1 else "short"
            formatted_questions.append({
                "label": q_label[:45],
                "placeholder": "أدخل الإجابة هنا...",
                "style": style_type,
                "required": True if idx == 0 else False
            })

        # Parse categories
        raw_cats = [c.strip() for c in self.categories_input.value.strip().split("\n") if c.strip()]
        categories = []
        for idx, line in enumerate(raw_cats[:20], 1):
            # Extract potential emoji from start of line
            emoji_match = re.match(r'^([^\w\s\d]+)\s*(.*)', line, re.UNICODE)
            if emoji_match:
                cat_emoji = emoji_match.group(1).strip()
                cat_name = emoji_match.group(2).strip() or f"قسم {idx}"
            else:
                cat_emoji = "🎫"
                cat_name = line

            categories.append({
                "id": f"cat_{idx}",
                "name": cat_name,
                "emoji": cat_emoji,
                "description": f"انقر هنا لفتح تذكرة في قسم {cat_name}",
                "questions": formatted_questions
            })

        if not categories:
            categories = [{
                "id": "cat_1",
                "name": "دعم عام",
                "emoji": "💬",
                "description": "تذكرة دعم عام",
                "questions": formatted_questions
            }]

        img = self.image_url.value.strip() or None

        panel_id = db.save_panel(
            title=self.panel_title.value.strip(),
            description=self.panel_desc.value.strip(),
            color=EmbedBuilder.COLOR_PRIMARY,
            categories=categories,
            channel_id=channel.id,
            image_url=img
        )

        embed = EmbedBuilder.panel_embed(
            title=self.panel_title.value.strip(),
            description=self.panel_desc.value.strip(),
            color=EmbedBuilder.COLOR_PRIMARY,
            guild=interaction.guild,
            image_url=img,
            categories=categories
        )

        view = PanelView(categories=categories, panel_id=panel_id)
        msg = await channel.send(embed=embed, view=view)
        db.update_panel_message_id(panel_id, msg.id)

        await interaction.response.send_message(
            f"✅ **تم نشر لوحة التذاكر بنجاح مع الأسئلة التفاعلية في القناة {channel.mention}!**\n"
            f"• عدد الأقسام المجهزة: `{len(categories)}`\n"
            f"• عدد الأسئلة التفاعلية لكل قسم: `{len(formatted_questions)}`\n"
            f"• معرف اللوحة: `{panel_id}`",
            ephemeral=True
        )


class BlacklistModal(Modal):
    def __init__(self, action: str = "add"):
        title_str = "🚫 إضافة عضو إلى قائمة الحظر" if action == "add" else "✅ إلغاء حظر عضو"
        super().__init__(title=title_str)
        self.action = action

        self.user_input = TextInput(
            label="معرف العضو (ID أو @Mention)",
            placeholder="مثال: 1406547827865288786",
            required=True,
            max_length=100
        )
        self.add_item(self.user_input)

        if action == "add":
            self.reason_input = TextInput(
                label="سبب الحظر",
                default="مخالفة شروط استخدام التذاكر",
                required=False,
                max_length=200
            )
            self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not check_master_permission(interaction):
            return await send_no_perm(interaction)

        val = self.user_input.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        try:
            target_id = int(val)
        except ValueError:
            return await interaction.response.send_message("❌ معرف العضو غير صحيح.", ephemeral=True)

        if self.action == "add":
            reason = self.reason_input.value.strip() or "بدون سبب موضح"
            db.blacklist_user(target_id, reason, interaction.user.id)
            await interaction.response.send_message(
                f"🚫 **تم حظر العضو <@{target_id}> من استخدام نظام التذاكر.**\nالسبب: {reason}",
                ephemeral=True
            )
        else:
            db.unblacklist_user(target_id)
            await interaction.response.send_message(
                f"✅ **تم إلغاء حظر العضو <@{target_id}> بنجاح.**",
                ephemeral=True
            )


class SettingsModal(Modal):
    def __init__(self, current_max: int):
        super().__init__(title="⚙️ تعديل إعدادات التذاكر")

        self.max_tickets = TextInput(
            label="الحد الأقصى للتذاكر المفتوحة لكل عضو",
            default=str(current_max),
            required=True,
            max_length=2
        )
        self.add_item(self.max_tickets)

    async def on_submit(self, interaction: discord.Interaction):
        if not check_master_permission(interaction):
            return await send_no_perm(interaction)

        try:
            val = int(self.max_tickets.value.strip())
            if val < 1:
                val = 1
        except ValueError:
            val = 1

        db.set_guild_setting(interaction.guild_id, "max_open_tickets", val)
        await interaction.response.send_message(
            f"⚙️ **تم تحديث الحد الأقصى للتذاكر المفتوحة إلى:** `{val}` تذكرة لكل عضو.",
            ephemeral=True
        )


# --- Select Menus ---

class ChannelSelectDropdown(Select):
    def __init__(self, channels):
        options = [
            discord.SelectOption(
                label=f"#{c.name}",
                value=str(c.id),
                description=f"ID: {c.id}",
                emoji="💬"
            ) for c in channels[:25]
        ]
        super().__init__(
            placeholder="📋 اختر قناة لتعيينها كقناة السجلات (Log Channel)",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="master_log_channel_select"
        )

    async def callback(self, interaction: discord.Interaction):
        if not check_master_permission(interaction):
            return await send_no_perm(interaction)

        channel_id = int(self.values[0])
        db.set_guild_setting(interaction.guild_id, "log_channel_id", channel_id)
        await interaction.response.send_message(
            f"📋 **تم تعيين قناة السجلات بنجاح إلى:** <#{channel_id}>",
            ephemeral=True
        )


class MasterMenuDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="🎯 إنشاء لوحة تذاكر في القناة الحالية",
                value="setup_panel_here",
                description="افتح نموذج إنشاء وتصميم لوحة التذاكر فوراً",
                emoji="🎯"
            ),
            discord.SelectOption(
                label="📋 تعيين قناة السجلات",
                value="set_log_channel",
                description="اختر القناة التي يتم فيها تسجيل إغلاق التذاكر والـ Log",
                emoji="📋"
            ),
            discord.SelectOption(
                label="🚫 إضافة عضو إلى الحظر (Blacklist)",
                value="blacklist_add",
                description="منع مستخدم من فتح تذاكر جديدة",
                emoji="🚫"
            ),
            discord.SelectOption(
                label="✅ إلغاء حظر عضو",
                value="blacklist_remove",
                description="السماح لمستخدم محظور بفتح تذاكر مجدداً",
                emoji="✅"
            ),
            discord.SelectOption(
                label="📊 عرض إحصائيات التذاكر التفصيلية",
                value="view_full_stats",
                description="تقارير الأداء وسرعة الاستجابة وعدد التذاكر",
                emoji="📊"
            ),
            discord.SelectOption(
                label="💾 إنشاء نسخة احتياطية من القاعدة",
                value="backup_db",
                description="تحميل ملف SQLite الخاص بقاعدة البيانات فوراً",
                emoji="💾"
            ),
        ]
        super().__init__(
            placeholder="⚡ اختر إجراء سريع من القائمة الرئيسية...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="master_control_menu"
        )

    async def callback(self, interaction: discord.Interaction):
        if not check_master_permission(interaction):
            return await send_no_perm(interaction)

        val = self.values[0]

        if val == "setup_panel_here":
            await interaction.response.send_modal(QuickSetupPanelModal(target_channel_id=interaction.channel_id))

        elif val == "set_log_channel":
            text_channels = [c for c in interaction.guild.channels if isinstance(c, discord.TextChannel)]
            if not text_channels:
                return await interaction.response.send_message("❌ لا توجد قنوات كتابية في هذا السيرفر.", ephemeral=True)
            v = View()
            v.add_item(ChannelSelectDropdown(text_channels))
            await interaction.response.send_message("📋 **اختر قناة السجلات من القائمة المنسدلة أسفله:**", view=v, ephemeral=True)

        elif val == "blacklist_add":
            await interaction.response.send_modal(BlacklistModal(action="add"))

        elif val == "blacklist_remove":
            await interaction.response.send_modal(BlacklistModal(action="remove"))

        elif val == "view_full_stats":
            all_t = db.get_all_tickets() or []
            open_t = [t for t in all_t if t.get("status") == "open"]
            closed_t = [t for t in all_t if t.get("status") in ["closed", "deleted"]]
            bl_t = db.get_blacklisted_users() or []

            embed = discord.Embed(
                title="📊 تقرير إحصائيات التذاكر الشامل",
                color=EmbedBuilder.COLOR_PRIMARY
            )
            embed.add_field(name="🎫 إجمالي التذاكر", value=f"`{len(all_t)}` تذكرة", inline=True)
            embed.add_field(name="🔓 التذاكر المفتوحة", value=f"`{len(open_t)}` تذكرة", inline=True)
            embed.add_field(name="🔒 التذاكر المغلقة", value=f"`{len(closed_t)}` تذكرة", inline=True)
            embed.add_field(name="🚫 المحظورين", value=f"`{len(bl_t)}` مستخدم", inline=True)
            embed.add_field(name="👑 مالك البوت", value=f"<@{MASTER_OWNER_ID}>", inline=True)
            embed.set_footer(text="لوحة تحكم Discord Bot Master Control")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        elif val == "backup_db":
            try:
                backup_path = BackupManager.create_backup()
                with open(backup_path, "rb") as f:
                    discord_file = discord.File(f, filename="tickets_backup.sqlite")
                    await interaction.response.send_message(
                        f"💾 **تم إنشاء وتصدير النسخة الاحتياطية بنجاح!**\n• تاريخ الإنشاء: <t:{int(time.time())}:F>",
                        file=discord_file,
                        ephemeral=True
                    )
            except Exception as e:
                await interaction.response.send_message(f"❌ فشل إنشاء النسخة الاحتياطية: {e}", ephemeral=True)


# --- Master Control Panel View ---

class MasterControlPanelView(View):
    def __init__(self, bot: discord.Client):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(MasterMenuDropdown())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not check_master_permission(interaction):
            await send_no_perm(interaction)
            return False
        return True

    @discord.ui.button(label="🎯 إنشاء لوحة تذاكر", style=discord.ButtonStyle.primary, emoji="🎯", custom_id="mcp_setup_panel", row=1)
    async def btn_setup_panel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(QuickSetupPanelModal(target_channel_id=interaction.channel_id))

    @discord.ui.button(label="📋 قناة السجلات", style=discord.ButtonStyle.secondary, emoji="📋", custom_id="mcp_log_channel", row=1)
    async def btn_log_channel(self, interaction: discord.Interaction, button: Button):
        text_channels = [c for c in interaction.guild.channels if isinstance(c, discord.TextChannel)]
        if not text_channels:
            return await interaction.response.send_message("❌ لا توجد قنوات كتابية.", ephemeral=True)
        v = View()
        v.add_item(ChannelSelectDropdown(text_channels))
        await interaction.response.send_message("📋 **اختر قناة السجلات:**", view=v, ephemeral=True)

    @discord.ui.button(label="🚫 قائمة الحظر", style=discord.ButtonStyle.danger, emoji="🚫", custom_id="mcp_blacklist", row=1)
    async def btn_blacklist(self, interaction: discord.Interaction, button: Button):
        bl_users = db.get_blacklisted_users() or []
        bl_text = "\n".join([f"• <@{u['user_id']}> (السبب: {u.get('reason', 'غير محدد')})" for u in bl_users[:10]]) if bl_users else "لا يوجد مستخدمون محظورون حالياً."

        embed = discord.Embed(
            title="🚫 إدارة قائمة الحظر (Blacklist)",
            description=f"**عدد المحظورين:** `{len(bl_users)}`\n\n**أحدث المحظورين:**\n{bl_text}",
            color=EmbedBuilder.COLOR_DANGER
        )

        v = View()
        b_add = Button(label="إضافة حظر", style=discord.ButtonStyle.danger, emoji="➕")
        b_rem = Button(label="إلغاء حظر", style=discord.ButtonStyle.success, emoji="➖")

        async def add_cb(i: discord.Interaction):
            await i.response.send_modal(BlacklistModal("add"))
        async def rem_cb(i: discord.Interaction):
            await i.response.send_modal(BlacklistModal("remove"))

        b_add.callback = add_cb
        b_rem.callback = rem_cb
        v.add_item(b_add)
        v.add_item(b_rem)

        await interaction.response.send_message(embed=embed, view=v, ephemeral=True)

    @discord.ui.button(label="⚙️ إعدادات التذاكر", style=discord.ButtonStyle.secondary, emoji="⚙️", custom_id="mcp_settings", row=1)
    async def btn_settings(self, interaction: discord.Interaction, button: Button):
        curr_max = db.get_guild_setting(interaction.guild_id, "max_open_tickets", 1)
        await interaction.response.send_modal(SettingsModal(current_max=curr_max))

    @discord.ui.button(label="🔄 تحديث اللوحة", style=discord.ButtonStyle.success, emoji="🔄", custom_id="mcp_refresh", row=2)
    async def btn_refresh(self, interaction: discord.Interaction, button: Button):
        embed = build_master_control_embed(self.bot, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🖼️ مزامنة صورة البوت", style=discord.ButtonStyle.primary, emoji="🖼️", custom_id="mcp_sync_avatar", row=2)
    async def btn_sync_avatar(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild or not interaction.guild.icon:
            return await interaction.followup.send("❌ هذا السيرفر لا يحتوي على أيقونة/شعار مخصص لمزامنته مع صورة البوت.", ephemeral=True)

        try:
            icon_bytes = await interaction.guild.icon.read()
            await self.bot.user.edit(avatar=icon_bytes)
            await interaction.followup.send(
                f"✅ **تم تغيير صورة البوت بنجاح لتماثل شعار سيرفر '{interaction.guild.name}'!** 🖼️",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"⚠️ تعذر تغيير صورة البوت حالياً:\n```{str(e)}```\n*(ملاحظة: تفرض ديسكورد حداً أقصى لتغيير صورة البوت مرتين في الساعة)*",
                ephemeral=True
            )


def build_master_control_embed(bot: discord.Client, guild: discord.Guild) -> discord.Embed:
    all_tickets = db.get_all_tickets() or []
    open_tickets = [t for t in all_tickets if t.get("status") == "open"]
    closed_tickets = [t for t in all_tickets if t.get("status") in ["closed", "deleted"]]
    blacklisted = db.get_blacklisted_users() or []

    log_ch_id = db.get_guild_setting(guild.id, "log_channel_id") if guild else None
    log_ch_str = f"<#{log_ch_id}>" if log_ch_id else "غير محددة ❌"

    max_tickets_per_user = db.get_guild_setting(guild.id, "max_open_tickets", 1) if guild else 1

    latency_ms = round(bot.latency * 1000) if bot.latency else 0

    embed = discord.Embed(
        title="🎛️ لوحة التحكم الرئيسية الشاملة بالبوت (Discord Bot Control Center)",
        description=(
            f"أهلاً بك يا مالك البوت <@{MASTER_OWNER_ID}>!\n"
            f"يمكنك التحكم الكامل في جميع إعدادات البوت والتذاكر والسيرفر مباشرة من هذه اللوحة التفاعلية."
        ),
        color=0x5865F2
    )

    if guild and guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    elif bot.user:
        if getattr(bot.user, "display_avatar", None):
            embed.set_thumbnail(url=bot.user.display_avatar.url)
        elif getattr(bot.user, "avatar", None):
            embed.set_thumbnail(url=bot.user.avatar.url)

    embed.add_field(
        name="👑 مالك البوت والتحكم الكامل",
        value=f"<@{MASTER_OWNER_ID}>\n(ID: `{MASTER_OWNER_ID}`)",
        inline=True
    )

    embed.add_field(
        name="⚡ حالة الاتصال والسرعة",
        value=f"🟢 متصل أونلاين\n⏱️ الاستجابة: `{latency_ms} ms`",
        inline=True
    )

    embed.add_field(
        name="🏢 السيرفر الحالي",
        value=f"**{guild.name if guild else 'غير محدد'}**\nID: `{guild.id if guild else 0}`",
        inline=True
    )

    embed.add_field(
        name="📊 إحصائيات التذاكر",
        value=(
            f"• 🎫 الإجمالي: `{len(all_tickets)}`\n"
            f"• 🔓 المفتوحة: `{len(open_tickets)}`\n"
            f"• 🔒 المغلقة: `{len(closed_tickets)}`"
        ),
        inline=True
    )

    embed.add_field(
        name="⚙️ الإعدادات الحالية",
        value=(
            f"• 📋 قناة السجلات: {log_ch_str}\n"
            f"• 🎫 حد التذاكر/عضو: `{max_tickets_per_user}`\n"
            f"• 🚫 المحظورين: `{len(blacklisted)}` عضو"
        ),
        inline=True
    )

    embed.set_footer(
        text=f"Ticket Bot Master Control • {guild.name if guild else 'Discord'}",
        icon_url=guild.icon.url if (guild and guild.icon) else None
    )

    return embed
