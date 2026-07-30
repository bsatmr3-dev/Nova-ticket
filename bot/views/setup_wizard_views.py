import discord
from discord.ui import View, Button, Select, Modal, TextInput, ChannelSelect, RoleSelect
from typing import Dict, Any, List, Optional
import json
from bot.database.db import db
from bot.utils.embeds import EmbedBuilder
from bot.views.panel_view import PanelView
from bot.utils.permissions import PermissionHandler

MASTER_OWNER_ID = 1406547827865288786

def is_admin_or_owner(interaction: discord.Interaction) -> bool:
    if PermissionHandler.is_bot_owner(interaction.user.id):
        return True
    if interaction.guild:
        if interaction.user.id == interaction.guild.owner_id or interaction.user.guild_permissions.administrator:
            return True
        if PermissionHandler.is_admin(interaction.user):
            return True
    return False

async def check_perm_or_deny(interaction: discord.Interaction) -> bool:
    if not is_admin_or_owner(interaction):
        msg = f"❌ **عفواً! هذه اللوحة مخصصة لمالك البوت (<@{MASTER_OWNER_ID}>) ولإدارة السيرفر فقط.**"
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return False
    return True

# --- Wizard Session State ---
class PanelCreationState:
    def __init__(self, user_id: int, guild_id: int):
        self.user_id = user_id
        self.guild_id = guild_id
        self.panel_title: str = "مركز الدعم الفني والتذاكر"
        self.panel_desc: str = "مرحباً بك! اختر القسم المناسب لفتح تذكرة مباشرة مع طاقم الدعم."
        self.banner_url: Optional[str] = None
        self.target_channel_id: Optional[int] = None
        self.num_categories: int = 1
        self.current_cat_index: int = 0
        self.categories: List[Dict[str, Any]] = []

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "guild_id": self.guild_id,
            "panel_title": self.panel_title,
            "panel_desc": self.panel_desc,
            "banner_url": self.banner_url,
            "target_channel_id": self.target_channel_id,
            "num_categories": self.num_categories,
            "current_cat_index": self.current_cat_index,
            "categories": self.categories
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PanelCreationState":
        s = cls(data["user_id"], data["guild_id"])
        s.panel_title = data.get("panel_title", "مركز الدعم الفني والتذاكر")
        s.panel_desc = data.get("panel_desc", "مرحباً بك!")
        s.banner_url = data.get("banner_url")
        s.target_channel_id = data.get("target_channel_id")
        s.num_categories = data.get("num_categories", 1)
        s.current_cat_index = data.get("current_cat_index", 0)
        s.categories = data.get("categories", [])
        return s

    def auto_save(self):
        db.save_wizard_session(self.user_id, self.to_dict())

    def add_or_update_category(self, cat_data: Dict[str, Any]):
        if self.current_cat_index < len(self.categories):
            self.categories[self.current_cat_index].update(cat_data)
        else:
            self.categories.append(cat_data)
        self.auto_save()

# In-Memory Active Wizard Sessions
wizard_sessions: Dict[int, PanelCreationState] = {}

# --- Modals ---

class PanelBasicInfoModal(Modal):
    def __init__(self, session: PanelCreationState):
        super().__init__(title="🎯 الخطوة 1: المعلومات الأساسية للوحة")
        self.session = session

        self.panel_title = TextInput(
            label="اسم / عنوان اللوحة (Panel Title)",
            default=session.panel_title,
            required=True,
            max_length=100
        )
        self.panel_desc = TextInput(
            label="الوصف والتعليمات (Description)",
            default=session.panel_desc,
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )
        self.banner_url = TextInput(
            label="رابط صورة الهيدر / Banner (اختياري)",
            placeholder="https://example.com/banner.png",
            default=session.banner_url or "",
            required=False,
            max_length=300
        )

        self.add_item(self.panel_title)
        self.add_item(self.panel_desc)
        self.add_item(self.banner_url)

    async def on_submit(self, interaction: discord.Interaction):
        if not await check_perm_or_deny(interaction):
            return

        self.session.panel_title = self.panel_title.value.strip()
        self.session.panel_desc = self.panel_desc.value.strip()
        self.session.banner_url = self.banner_url.value.strip() or None

        # Next Step: Select Target Channel
        embed = discord.Embed(
            title="🎯 الخطوة 2: اختيار قناة نشر اللوحة",
            description=(
                f"**عنوان اللوحة:** {self.session.panel_title}\n"
                f"**الوصف:** {self.session.panel_desc[:100]}...\n\n"
                f"📌 **يرجى اختيار القناة الكتابية التي تريد إرسال اللوحة إليها:**"
            ),
            color=EmbedBuilder.COLOR_PRIMARY
        )
        view = TargetChannelSelectView(self.session)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class CategoryInfoModal(Modal):
    def __init__(self, session: PanelCreationState):
        cat_idx = session.current_cat_index + 1
        super().__init__(title=f"🎫 إعداد نوع التذكرة ({cat_idx} من {session.num_categories})")
        self.session = session

        existing_cat = session.categories[session.current_cat_index] if session.current_cat_index < len(session.categories) else {}

        self.cat_name = TextInput(
            label="اسم نوع التذكرة (Category Name)",
            default=existing_cat.get("name", f"قسم {cat_idx}"),
            required=True,
            max_length=50
        )
        self.cat_desc = TextInput(
            label="وصف القسم (Description)",
            default=existing_cat.get("description", "انقر هنا لفتح تذكرة جديدة"),
            required=True,
            max_length=100
        )
        self.cat_emoji = TextInput(
            label="الإيموجي (Emoji)",
            default=existing_cat.get("emoji", "🎫"),
            required=True,
            max_length=10
        )
        self.welcome_msg = TextInput(
            label="رسالة الترحيب داخل التذكرة (Welcome Msg)",
            default=existing_cat.get("welcome_msg", "مرحباً {user}! شرفتنا في قسم {category}. يرجى توضيح طلبك وسيصلك الدعم فوراً."),
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000
        )
        self.points_input = TextInput(
            label="عدد النقاط عند الإغلاق (Points)",
            default=str(existing_cat.get("points", 5)),
            required=True,
            max_length=4
        )

        self.add_item(self.cat_name)
        self.add_item(self.cat_desc)
        self.add_item(self.cat_emoji)
        self.add_item(self.welcome_msg)
        self.add_item(self.points_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not await check_perm_or_deny(interaction):
            return

        try:
            p_val = int(self.points_input.value.strip())
            p_val = max(0, p_val)
        except ValueError:
            p_val = 5

        cat_data = {
            "id": f"cat_{self.session.current_cat_index + 1}",
            "name": self.cat_name.value.strip(),
            "description": self.cat_desc.value.strip(),
            "emoji": self.cat_emoji.value.strip() or "🎫",
            "welcome_msg": self.welcome_msg.value.strip(),
            "points": p_val,
            "max_tickets": existing_cat.get("max_tickets", 1),
            "category_id": existing_cat.get("category_id"),
            "support_role_ids": existing_cat.get("support_role_ids", []),
            "enabled": True
        }

        self.session.add_or_update_category(cat_data)

        # Next Sub-step: Select Discord Category Channel
        embed = discord.Embed(
            title=f"📁 الخطوة الفرعية: اختيار التصنيف (Category Channel)",
            description=(
                f"**اسم القسم:** {cat_data['emoji']} {cat_data['name']}\n\n"
                f"📁 **اختر التصنيف (Discord Category) الذي سيتم فيه إنشاء قنوات التذاكر لهذا القسم:**\n"
                f"*(إذا لم تختر تصنيفاً، سيتم إنشاؤها خارج التصنيفات)*"
            ),
            color=EmbedBuilder.COLOR_PRIMARY
        )
        view = DiscordCategorySelectView(self.session)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class AntiSpamSettingsModal(Modal):
    def __init__(self, current_cooldown: int, current_max: int):
        super().__init__(title="🛡️ إعدادات الحماية والأمان (Anti-Spam)")

        self.cooldown = TextInput(
            label="وقت الانتظار بين فتح التذاكر (بالثواني)",
            default=str(current_cooldown),
            required=True,
            max_length=3
        )
        self.max_tickets = TextInput(
            label="الحد الأقصى الإجمالي للتذاكر المفتوحة للعضو",
            default=str(current_max),
            required=True,
            max_length=2
        )

        self.add_item(self.cooldown)
        self.add_item(self.max_tickets)

    async def on_submit(self, interaction: discord.Interaction):
        if not await check_perm_or_deny(interaction):
            return

        try:
            cd = max(0, int(self.cooldown.value.strip()))
            mt = max(1, int(self.max_tickets.value.strip()))
        except ValueError:
            return await interaction.response.send_message("❌ قيم غير صحيحة.", ephemeral=True)

        db.set_guild_setting(interaction.guild_id, "cooldown_seconds", cd)
        db.set_guild_setting(interaction.guild_id, "max_open_tickets", mt)

        await interaction.response.send_message(
            f"✅ **تم تحديث إعدادات الأمان والتذاكر:**\n• وقت الانتظار: `{cd}` ثانية\n• حد التذاكر المفتوحة: `{mt}` تذكرة لكل عضو",
            ephemeral=True
        )


class BlacklistManageModal(Modal):
    def __init__(self, action: str = "add"):
        title_str = "🚫 إضافة حظر مستخدم" if action == "add" else "✅ إلغاء حظر مستخدم"
        super().__init__(title=title_str)
        self.action = action

        self.user_id_input = TextInput(
            label="معرف المستخدم (User ID)",
            placeholder="مثال: 1406547827865288786",
            required=True,
            max_length=50
        )
        self.add_item(self.user_id_input)

        if action == "add":
            self.reason_input = TextInput(
                label="سبب الحظر",
                default="مخالفة نظام التذاكر",
                required=False,
                max_length=200
            )
            self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not await check_perm_or_deny(interaction):
            return

        raw = self.user_id_input.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        try:
            target_id = int(raw)
        except ValueError:
            return await interaction.response.send_message("❌ معرف المستخدم غير صحيح.", ephemeral=True)

        if self.action == "add":
            reason = self.reason_input.value.strip() or "بدون سبب"
            db.blacklist_user(target_id, reason, interaction.user.id)
            await interaction.response.send_message(
                f"🚫 **تم حظر المستخدم <@{target_id}> من فتح التذاكر.**\nالسبب: {reason}",
                ephemeral=True
            )
        else:
            db.unblacklist_user(target_id)
            await interaction.response.send_message(
                f"✅ **تم إلغاء حظر المستخدم <@{target_id}> بنجاح.**",
                ephemeral=True
            )


# --- Select Views ---

class TargetChannelSelectView(View):
    def __init__(self, session: PanelCreationState):
        super().__init__(timeout=None)
        self.session = session

        select = ChannelSelect(
            placeholder="📌 اختر القناة الكتابية لنشر اللوحة...",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
            custom_id="wizard_target_channel_select"
        )
        select.callback = self.on_channel_selected
        self.add_item(select)

    async def on_channel_selected(self, interaction: discord.Interaction):
        if not await check_perm_or_deny(interaction):
            return

        ch_id = int(interaction.data["values"][0])
        self.session.target_channel_id = ch_id

        # Step 3: Choose Number of Ticket Categories
        embed = discord.Embed(
            title="🔢 الخطوة 3: عدد أنواع / أقسام التذاكر",
            description=(
                f"**القناة المحددة:** <#{ch_id}>\n\n"
                f"كم عدد أقسام التذاكر التي تريد إضافتها في هذه اللوحة؟\n"
                f"*(يمكنك اختيار من قسم واحد إلى 5 أقسام مختلفة)*"
            ),
            color=EmbedBuilder.COLOR_PRIMARY
        )
        view = CategoryCountSelectView(self.session)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class CategoryCountSelectView(View):
    def __init__(self, session: PanelCreationState):
        super().__init__(timeout=None)
        self.session = session

        options = [
            discord.SelectOption(label="قسم واحد (1 Category)", value="1", emoji="1️⃣", description="نوع تذكرة واحد فقط"),
            discord.SelectOption(label="قسمين (2 Categories)", value="2", emoji="2️⃣", description="قسمان مختلفان للتذاكر"),
            discord.SelectOption(label="3 أقسام (3 Categories)", value="3", emoji="3️⃣", description="ثلاثة أقسام متخصصة"),
            discord.SelectOption(label="4 أقسام (4 Categories)", value="4", emoji="4️⃣", description="أربعة أقسام متكاملة"),
            discord.SelectOption(label="5 أقسام (5 Categories)", value="5", emoji="5️⃣", description="خمسة أقسام شاملة"),
        ]

        select = Select(
            placeholder="🔢 اختر عدد أقسام التذاكر...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="wizard_cat_count_select"
        )
        select.callback = self.on_count_selected
        self.add_item(select)

    async def on_count_selected(self, interaction: discord.Interaction):
        if not await check_perm_or_deny(interaction):
            return

        num = int(interaction.data["values"][0])
        self.session.num_categories = num
        self.session.current_cat_index = 0

        # Start Category Configuration Loop
        await interaction.response.send_modal(CategoryInfoModal(self.session))


class DiscordCategorySelectView(View):
    def __init__(self, session: PanelCreationState):
        super().__init__(timeout=None)
        self.session = session

        select = ChannelSelect(
            placeholder="📁 اختر تصنيف ديسكورد (Discord Category)...",
            channel_types=[discord.ChannelType.category],
            min_values=0,
            max_values=1,
            custom_id="wizard_discord_cat_select"
        )
        select.callback = self.on_category_selected
        self.add_item(select)

        skip_btn = Button(label="تخطي (بدون تصنيف)", style=discord.ButtonStyle.secondary, emoji="⏭️")
        skip_btn.callback = self.on_skip
        self.add_item(skip_btn)

    async def on_category_selected(self, interaction: discord.Interaction):
        if not await check_perm_or_deny(interaction):
            return

        values = interaction.data.get("values", [])
        cat_id = int(values[0]) if values else None
        self.session.categories[self.session.current_cat_index]["category_id"] = cat_id

        await self.proceed_to_roles_select(interaction)

    async def on_skip(self, interaction: discord.Interaction):
        if not await check_perm_or_deny(interaction):
            return

        self.session.categories[self.session.current_cat_index]["category_id"] = None
        await self.proceed_to_roles_select(interaction)

    async def proceed_to_roles_select(self, interaction: discord.Interaction):
        curr_cat = self.session.categories[self.session.current_cat_index]
        cat_channel_str = f"<#{curr_cat['category_id']}>" if curr_cat['category_id'] else "بدون تصنيف"

        embed = discord.Embed(
            title="👥 الخطوة الفرعية: اختيار رتب الدعم المسؤولة",
            description=(
                f"**القسم:** {curr_cat['emoji']} {curr_cat['name']}\n"
                f"**التصنيف:** {cat_channel_str}\n\n"
                f"👥 **اختر الرتب التي تمتلك صلاحية رؤية وإجابة تذاكر هذا القسم:**\n"
                f"*(يمكنك اختيار أكثر من رتبة)*"
            ),
            color=EmbedBuilder.COLOR_PRIMARY
        )
        view = CategoryRolesSelectView(self.session)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class CategoryRolesSelectView(View):
    def __init__(self, session: PanelCreationState):
        super().__init__(timeout=None)
        self.session = session

        role_select = RoleSelect(
            placeholder="👥 اختر رتب الدعم لهذا القسم...",
            min_values=0,
            max_values=10,
            custom_id="wizard_cat_roles_select"
        )
        role_select.callback = self.on_roles_selected
        self.add_item(role_select)

        skip_btn = Button(label="تخطي (استخدام رتب السيرفر الافتراضية)", style=discord.ButtonStyle.secondary, emoji="⏭️")
        skip_btn.callback = self.on_skip
        self.add_item(skip_btn)

    async def on_roles_selected(self, interaction: discord.Interaction):
        if not await check_perm_or_deny(interaction):
            return

        role_ids = [int(r) for r in interaction.data.get("values", [])]
        self.session.categories[self.session.current_cat_index]["support_role_ids"] = role_ids

        await self.next_step_or_finish(interaction)

    async def on_skip(self, interaction: discord.Interaction):
        if not await check_perm_or_deny(interaction):
            return

        self.session.categories[self.session.current_cat_index]["support_role_ids"] = []
        await self.next_step_or_finish(interaction)

    async def next_step_or_finish(self, interaction: discord.Interaction):
        self.session.current_cat_index += 1

        if self.session.current_cat_index < self.session.num_categories:
            # Continue loop for next category
            await interaction.response.send_modal(CategoryInfoModal(self.session))
        else:
            # All categories configured! Show final deployment summary view
            embed = build_summary_embed(self.session, interaction.guild)
            view = DeploymentSummaryView(self.session)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# --- Final Deployment View ---

def build_summary_embed(session: PanelCreationState, guild: discord.Guild) -> discord.Embed:
    ch_str = f"<#{session.target_channel_id}>" if session.target_channel_id else "غير محددة"

    embed = discord.Embed(
        title="🎉 اكتمل معالج الإعداد! المعاينة والملخص النهائي",
        description=(
            f"**عنوان اللوحة:** {session.panel_title}\n"
            f"**الوصف:** {session.panel_desc}\n"
            f"**قناة النشر:** {ch_str}\n"
            f"**صورة الهيدر:** {session.banner_url or 'لا يوجد'}\n"
            f"**عدد الأقسام:** `{len(session.categories)}` قسم"
        ),
        color=EmbedBuilder.COLOR_SUCCESS
    )

    for idx, cat in enumerate(session.categories, 1):
        cat_ch_str = f"<#{cat['category_id']}>" if cat.get("category_id") else "بدون تصنيف"
        roles_str = " ".join([f"<@&{r}>" for r in cat.get("support_role_ids", [])]) if cat.get("support_role_ids") else "الرتب الافتراضية"

        val_text = (
            f"• **الوصف:** {cat['description']}\n"
            f"• **التصنيف:** {cat_ch_str}\n"
            f"• **رتب الدعم:** {roles_str}\n"
            f"• **النقاط:** `{cat.get('points', 5)}` نقطة\n"
            f"• **الحد الأقصى:** `{cat.get('max_tickets', 1)}` تذكرة لكل عضو"
        )
        embed.add_field(name=f"{cat['emoji']} القسم {idx}: {cat['name']}", value=val_text, inline=False)

    if session.banner_url:
        embed.set_image(url=session.banner_url)

    embed.set_footer(text="انقر على 'تأكيد ونشر اللوحة' لنشرها مباشرة في القناة")
    return embed


class DeploymentSummaryView(View):
    def __init__(self, session: PanelCreationState):
        super().__init__(timeout=None)
        self.session = session

    @discord.ui.button(label="🚀 تأكيد ونشر اللوحة الآن", style=discord.ButtonStyle.success, emoji="🚀", custom_id="wizard_deploy_confirm")
    async def confirm_deploy(self, interaction: discord.Interaction, button: Button):
        if not await check_perm_or_deny(interaction):
            return

        guild = interaction.guild
        target_ch = guild.get_channel(self.session.target_channel_id) if self.session.target_channel_id else interaction.channel

        if not target_ch:
            return await interaction.response.send_message("❌ القناة المحددة لنشر اللوحة غير موجودة.", ephemeral=True)

        # 1. Save Panel in Database
        panel_id = db.save_panel(
            title=self.session.panel_title,
            description=self.session.panel_desc,
            color=EmbedBuilder.COLOR_PRIMARY,
            categories=self.session.categories,
            channel_id=target_ch.id,
            image_url=self.session.banner_url
        )

        # 2. Build Panel Embed & View
        panel_embed = EmbedBuilder.panel_embed(
            title=self.session.panel_title,
            description=self.session.panel_desc,
            color=EmbedBuilder.COLOR_PRIMARY,
            guild=guild,
            image_url=self.session.banner_url,
            categories=self.session.categories
        )

        panel_view = PanelView(categories=self.session.categories, panel_id=panel_id)

        # 3. Post to Channel
        posted_msg = await target_ch.send(embed=panel_embed, view=panel_view)
        db.update_panel_message_id(panel_id, posted_msg.id)

        # Clear session
        if self.session.user_id in wizard_sessions:
            del wizard_sessions[self.session.user_id]

        await interaction.response.send_message(
            f"✅ **تم نشر لوحة التذاكر بنجاح!**\n"
            f"• القناة: {target_ch.mention}\n"
            f"• معرف اللوحة: `{panel_id}`\n"
            f"• رابط الرسالة: [انقر للانتقال للوحة]({posted_msg.jump_url})",
            ephemeral=True
        )

    @discord.ui.button(label="❌ إلغاء الإعداد", style=discord.ButtonStyle.danger, emoji="❌", custom_id="wizard_deploy_cancel")
    async def cancel_wizard(self, interaction: discord.Interaction, button: Button):
        if not await check_perm_or_deny(interaction):
            return

        if self.session.user_id in wizard_sessions:
            del wizard_sessions[self.session.user_id]

        await interaction.response.send_message("❌ تم إلغاء معالج الإعداد.", ephemeral=True)


# --- Settings Suite Dashboard View ---

class InAppSettingsDashboardView(View):
    def __init__(self, bot: discord.Client, guild: Optional[discord.Guild] = None):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild = guild

    @discord.ui.button(label="🎯 إنشاء لوحة جديدة", style=discord.ButtonStyle.primary, emoji="🎯", custom_id="dash_create_panel", row=1)
    async def btn_create_panel(self, interaction: discord.Interaction, button: Button):
        if not await check_perm_or_deny(interaction):
            return

        session = PanelCreationState(interaction.user.id, interaction.guild_id)
        wizard_sessions[interaction.user.id] = session
        await interaction.response.send_modal(PanelBasicInfoModal(session))

    @discord.ui.button(label="📋 قناة السجلات (Logs)", style=discord.ButtonStyle.secondary, emoji="📋", custom_id="dash_set_log_channel", row=1)
    async def btn_set_log_channel(self, interaction: discord.Interaction, button: Button):
        if not await check_perm_or_deny(interaction):
            return

        v = View()
        sel = ChannelSelect(placeholder="📋 اختر قناة السجلات...", channel_types=[discord.ChannelType.text])
        async def cb(i: discord.Interaction):
            ch_id = int(i.data["values"][0])
            db.set_guild_setting(i.guild_id, "log_channel_id", ch_id)
            await i.response.send_message(f"📋 **تم تحديث قناة السجلات إلى:** <#{ch_id}>", ephemeral=True)
        sel.callback = cb
        v.add_item(sel)
        await interaction.response.send_message("📋 **اختر القناة المخصصة لسجلات التذاكر (Logs):**", view=v, ephemeral=True)

    @discord.ui.button(label="📜 قناة الترانسكريبت", style=discord.ButtonStyle.secondary, emoji="📜", custom_id="dash_set_transcript_channel", row=1)
    async def btn_set_transcript_channel(self, interaction: discord.Interaction, button: Button):
        if not await check_perm_or_deny(interaction):
            return

        v = View()
        sel = ChannelSelect(placeholder="📜 اختر قناة الترانسكريبت...", channel_types=[discord.ChannelType.text])
        async def cb(i: discord.Interaction):
            ch_id = int(i.data["values"][0])
            db.set_guild_setting(i.guild_id, "transcript_channel_id", ch_id)
            await i.response.send_message(f"📜 **تم تحديث قناة الترانسكريبت إلى:** <#{ch_id}>", ephemeral=True)
        sel.callback = cb
        v.add_item(sel)
        await interaction.response.send_message("📜 **اختر القناة المخصصة لحفظ سكريبتات المحادثات (Transcripts):**", view=v, ephemeral=True)

    @discord.ui.button(label="🛡️ إعدادات Anti-Spam", style=discord.ButtonStyle.secondary, emoji="🛡️", custom_id="dash_antispam_modal", row=1)
    async def btn_antispam_modal(self, interaction: discord.Interaction, button: Button):
        if not await check_perm_or_deny(interaction):
            return

        cd = db.get_guild_setting(interaction.guild_id, "cooldown_seconds", 10)
        mt = db.get_guild_setting(interaction.guild_id, "max_open_tickets", 1)
        await interaction.response.send_modal(AntiSpamSettingsModal(current_cooldown=cd, current_max=mt))

    @discord.ui.button(label="👥 رتب الدعم والإدارة", style=discord.ButtonStyle.secondary, emoji="👥", custom_id="dash_set_roles", row=2)
    async def btn_set_roles(self, interaction: discord.Interaction, button: Button):
        if not await check_perm_or_deny(interaction):
            return

        v = View()
        type_sel = Select(placeholder="اختر مستوى الرتبة لتعديلها...", options=[
            discord.SelectOption(label="رتبة الدعم (Support)", value="support_role_id", emoji="🛠️"),
            discord.SelectOption(label="رتبة الدعم العالي (Senior)", value="senior_support_role_id", emoji="🎖️"),
            discord.SelectOption(label="مدير الدعم (Support Manager)", value="support_manager_role_id", emoji="👔"),
            discord.SelectOption(label="رتبة الإدارة (Admin)", value="admin_role_id", emoji="🛡️"),
            discord.SelectOption(label="رتبة المالك (Owner)", value="owner_role_id", emoji="👑")
        ])
        
        async def type_cb(i: discord.Interaction):
            setting_key = type_sel.values[0]
            label = next(o.label for o in type_sel.options if o.value == setting_key)
            
            v2 = View()
            r_sel = RoleSelect(placeholder=f"اختر {label}...", min_values=1, max_values=1)
            
            async def r_cb(i2: discord.Interaction):
                r_id = int(i2.data["values"][0])
                db.set_guild_setting(i2.guild_id, setting_key, r_id)
                await i2.response.send_message(f"✅ **تم تعيين {label} إلى:** <@&{r_id}>", ephemeral=True)
            
            r_sel.callback = r_cb
            v2.add_item(r_sel)
            await i.response.edit_message(content=f"👥 **اختر الرتبة لـ {label}:**", view=v2)

        type_sel.callback = type_cb
        v.add_item(type_sel)
        await interaction.response.send_message("👥 **إعداد رتب الطاقم الإداري (Staff Roles):**", view=v, ephemeral=True)

    @discord.ui.button(label="🚫 قائمة الحظر (Blacklist)", style=discord.ButtonStyle.danger, emoji="🚫", custom_id="dash_blacklist_mgt", row=2)
    async def btn_blacklist_mgt(self, interaction: discord.Interaction, button: Button):
        if not await check_perm_or_deny(interaction):
            return

        bl_users = db.get_blacklisted_users() or []
        bl_text = "\n".join([f"• <@{u['user_id']}> (السبب: {u.get('reason', 'غير محدد')})" for u in bl_users[:10]]) if bl_users else "لا يوجد مستخدمون محظورون حالياً."

        embed = discord.Embed(
            title="🚫 إدارة حظر التذاكر (Blacklist)",
            description=f"**عدد المحظورين:** `{len(bl_users)}`\n\n{bl_text}",
            color=EmbedBuilder.COLOR_DANGER
        )

        v = View()
        b_add = Button(label="إضافة حظر", style=discord.ButtonStyle.danger, emoji="➕")
        b_rem = Button(label="إلغاء حظر", style=discord.ButtonStyle.success, emoji="➖")

        async def add_cb(i: discord.Interaction):
            await i.response.send_modal(BlacklistManageModal("add"))
        async def rem_cb(i: discord.Interaction):
            await i.response.send_modal(BlacklistManageModal("remove"))

        b_add.callback = add_cb
        b_rem.callback = rem_cb
        v.add_item(b_add)
        v.add_item(b_rem)

        await interaction.response.send_message(embed=embed, view=v, ephemeral=True)

    @discord.ui.button(label="📜 سجل التغييرات (Audit Log)", style=discord.ButtonStyle.secondary, emoji="📜", custom_id="dash_audit_logs", row=2)
    async def btn_audit_logs(self, interaction: discord.Interaction, button: Button):
        if not await check_perm_or_deny(interaction):
            return

        logs = db.get_settings_audit_logs(interaction.guild_id, limit=10)
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

    @discord.ui.button(label="🌐 اللغة / Language", style=discord.ButtonStyle.secondary, emoji="🌐", custom_id="dash_toggle_lang", row=2)
    async def btn_toggle_lang(self, interaction: discord.Interaction, button: Button):
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

    @discord.ui.button(label="🔄 تحديث الشاشة", style=discord.ButtonStyle.success, emoji="🔄", custom_id="dash_refresh_screen", row=3)
    async def btn_refresh_screen(self, interaction: discord.Interaction, button: Button):
        if not await check_perm_or_deny(interaction):
            return

        embed = build_in_app_settings_embed(self.bot, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)


# --- Interactive Panel Editor Suite ---

class PanelEditInfoModal(Modal):
    def __init__(self, panel_data: Dict[str, Any]):
        super().__init__(title="📝 تعديل معلومات اللوحة")
        self.panel_data = panel_data

        self.title_input = TextInput(
            label="اسم اللوحة (Title)",
            default=panel_data.get("title", ""),
            required=True,
            max_length=100
        )
        self.desc_input = TextInput(
            label="وصف اللوحة (Description)",
            default=panel_data.get("description", ""),
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )
        self.image_input = TextInput(
            label="رابط الصورة / Banner (اختياري)",
            default=panel_data.get("image_url") or "",
            required=False,
            max_length=300
        )
        self.color_input = TextInput(
            label="كود اللون Hex (مثال: #5865F2)",
            default=f"#{panel_data.get('color', 5793266):06X}",
            required=False,
            max_length=10
        )

        self.add_item(self.title_input)
        self.add_item(self.desc_input)
        self.add_item(self.image_input)
        self.add_item(self.color_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not await check_perm_or_deny(interaction):
            return

        self.panel_data["title"] = self.title_input.value.strip()
        self.panel_data["description"] = self.desc_input.value.strip()
        self.panel_data["image_url"] = self.image_input.value.strip() or None

        hex_str = self.color_input.value.strip().replace("#", "")
        try:
            self.panel_data["color"] = int(hex_str, 16)
        except ValueError:
            self.panel_data["color"] = EmbedBuilder.COLOR_PRIMARY

        await interaction.response.send_message("✅ **تم تحديث معلومات اللوحة المؤقتة. انقر على 'حفظ وتحديث اللوحة الحية' لتطبيق التغييرات.**", ephemeral=True)


class CategoryEditModal(Modal):
    def __init__(self, category_data: Dict[str, Any]):
        super().__init__(title=f"⚙️ تعديل قسم: {category_data.get('name', '')}")
        self.category_data = category_data

        self.name_input = TextInput(
            label="اسم نوع التذكرة",
            default=category_data.get("name", ""),
            required=True,
            max_length=50
        )
        self.desc_input = TextInput(
            label="الوصف المختصر",
            default=category_data.get("description", ""),
            required=True,
            max_length=100
        )
        self.emoji_input = TextInput(
            label="الإيموجي",
            default=category_data.get("emoji", "🎫"),
            required=True,
            max_length=10
        )
        self.welcome_input = TextInput(
            label="رسالة الترحيب (تدعم {user} و{server})",
            default=category_data.get("welcome_msg", "مرحباً {user}! شرفتنا في قسم {category}."),
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000
        )
        self.points_input = TextInput(
            label="عدد النقاط عند الإغلاق (Points)",
            default=str(category_data.get("points", 5)),
            required=True,
            max_length=4
        )

        self.add_item(self.name_input)
        self.add_item(self.desc_input)
        self.add_item(self.emoji_input)
        self.add_item(self.welcome_input)
        self.add_item(self.points_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not await check_perm_or_deny(interaction):
            return

        self.category_data["name"] = self.name_input.value.strip()
        self.category_data["description"] = self.desc_input.value.strip()
        self.category_data["emoji"] = self.emoji_input.value.strip() or "🎫"
        self.category_data["welcome_msg"] = self.welcome_input.value.strip()

        try:
            self.category_data["points"] = max(0, int(self.points_input.value.strip()))
        except ValueError:
            self.category_data["points"] = 5

        await interaction.response.send_message(f"✅ **تم تحديث بيانات القسم `{self.category_data['name']}`.**", ephemeral=True)


class InteractivePanelEditorView(View):
    def __init__(self, bot: discord.Client, panel_data: Dict[str, Any]):
        super().__init__(timeout=None)
        self.bot = bot
        self.panel_data = panel_data
        self.selected_cat_index: int = 0
        self.refresh_components()

    def refresh_components(self):
        self.clear_items()

        categories = self.panel_data.get("categories", [])

        # Category Select Dropdown
        if categories:
            options = [
                discord.SelectOption(
                    label=f"{idx+1}. {c.get('emoji', '🎫')} {c.get('name', 'قسم')}",
                    value=str(idx),
                    description=c.get("description", "")[:50],
                    default=(idx == self.selected_cat_index)
                ) for idx, c in enumerate(categories)
            ]
            cat_select = Select(placeholder="🔍 اختر قسم التذكرة للتحكم والتعديل...", options=options, min_values=1, max_values=1, custom_id="editor_cat_select")
            
            async def cat_sel_cb(i: discord.Interaction):
                self.selected_cat_index = int(i.data["values"][0])
                embed = self.build_editor_embed(i.guild)
                self.refresh_components()
                await i.response.edit_message(embed=embed, view=self)

            cat_select.callback = cat_sel_cb
            self.add_item(cat_select)

        # Action Buttons Row 1
        b_info = Button(label="📝 تعديل اللوحة", style=discord.ButtonStyle.primary, emoji="📝", row=1)
        async def info_cb(i: discord.Interaction):
            await i.response.send_modal(PanelEditInfoModal(self.panel_data))
        b_info.callback = info_cb
        self.add_item(b_info)

        b_add_cat = Button(label="➕ إضافة قسم جديد", style=discord.ButtonStyle.success, emoji="➕", row=1)
        async def add_cat_cb(i: discord.Interaction):
            new_cat = {
                "id": f"cat_{len(self.panel_data['categories']) + 1}",
                "name": f"قسم جديد {len(self.panel_data['categories']) + 1}",
                "description": "وصف القسم الجديد",
                "emoji": "🎫",
                "welcome_msg": "مرحباً {user}! يرجى توضيح استفسارك.",
                "max_tickets": 1,
                "enabled": True
            }
            self.panel_data["categories"].append(new_cat)
            self.selected_cat_index = len(self.panel_data["categories"]) - 1
            await i.response.send_modal(CategoryEditModal(new_cat))
        b_add_cat.callback = add_cat_cb
        self.add_item(b_add_cat)

        b_preview = Button(label="👁️ معاينة حية (Live Preview)", style=discord.ButtonStyle.secondary, emoji="👁️", row=1)
        async def preview_cb(i: discord.Interaction):
            embed = EmbedBuilder.panel_embed(
                title=self.panel_data["title"],
                description=self.panel_data["description"],
                color=self.panel_data.get("color", EmbedBuilder.COLOR_PRIMARY),
                guild=i.guild,
                image_url=self.panel_data.get("image_url"),
                categories=self.panel_data.get("categories", [])
            )
            preview_view = PanelView(categories=self.panel_data.get("categories", []), panel_id=self.panel_data.get("id", 0))
            await i.response.send_message("👁️ **معاينة حية للوحة التذاكر كما ستظهر للأعضاء:**", embed=embed, view=preview_view, ephemeral=True)
        b_preview.callback = preview_cb
        self.add_item(b_preview)

        if categories:
            # Reorder & Edit Category Row 2
            b_edit_cat = Button(label="⚙️ تعديل القسم المختار", style=discord.ButtonStyle.secondary, emoji="⚙️", row=2)
            async def edit_cat_cb(i: discord.Interaction):
                if self.selected_cat_index < len(self.panel_data["categories"]):
                    await i.response.send_modal(CategoryEditModal(self.panel_data["categories"][self.selected_cat_index]))
            b_edit_cat.callback = edit_cat_cb
            self.add_item(b_edit_cat)

            b_up = Button(label="⬆️ أعلى", style=discord.ButtonStyle.secondary, emoji="⬆️", row=2)
            async def up_cb(i: discord.Interaction):
                idx = self.selected_cat_index
                if idx > 0:
                    cats = self.panel_data["categories"]
                    cats[idx], cats[idx-1] = cats[idx-1], cats[idx]
                    self.selected_cat_index -= 1
                    embed = self.build_editor_embed(i.guild)
                    self.refresh_components()
                    await i.response.edit_message(embed=embed, view=self)
                else:
                    await i.response.send_message("⚠️ هذا القسم في أعلى القائمة بالفعل.", ephemeral=True)
            b_up.callback = up_cb
            self.add_item(b_up)

            b_down = Button(label="⬇️ أسفل", style=discord.ButtonStyle.secondary, emoji="⬇️", row=2)
            async def down_cb(i: discord.Interaction):
                idx = self.selected_cat_index
                cats = self.panel_data["categories"]
                if idx < len(cats) - 1:
                    cats[idx], cats[idx+1] = cats[idx+1], cats[idx]
                    self.selected_cat_index += 1
                    embed = self.build_editor_embed(i.guild)
                    self.refresh_components()
                    await i.response.edit_message(embed=embed, view=self)
                else:
                    await i.response.send_message("⚠️ هذا القسم في أسفل القائمة بالفعل.", ephemeral=True)
            b_down.callback = down_cb
            self.add_item(b_down)

            b_dup = Button(label="📋 نسخ", style=discord.ButtonStyle.secondary, emoji="📋", row=2)
            async def dup_cb(i: discord.Interaction):
                idx = self.selected_cat_index
                if idx < len(self.panel_data["categories"]):
                    copied = json.loads(json.dumps(self.panel_data["categories"][idx]))
                    copied["name"] += " (نسخة)"
                    copied["id"] = f"cat_{len(self.panel_data['categories'])+1}"
                    self.panel_data["categories"].append(copied)
                    self.selected_cat_index = len(self.panel_data["categories"]) - 1
                    embed = self.build_editor_embed(i.guild)
                    self.refresh_components()
                    await i.response.edit_message(embed=embed, view=self)
            b_dup.callback = dup_cb
            self.add_item(b_dup)

            b_del = Button(label="🗑️ حذف القسم", style=discord.ButtonStyle.danger, emoji="🗑️", row=2)
            async def del_cb(i: discord.Interaction):
                idx = self.selected_cat_index
                if idx < len(self.panel_data["categories"]):
                    removed = self.panel_data["categories"].pop(idx)
                    self.selected_cat_index = max(0, idx - 1)
                    embed = self.build_editor_embed(i.guild)
                    self.refresh_components()
                    await i.response.edit_message(embed=embed, view=self)
            b_del.callback = del_cb
            self.add_item(b_del)

        # Row 3: Save & Update Live Panel
        b_save = Button(label="💾 حفظ وتحديث اللوحة الحية (Save & Update)", style=discord.ButtonStyle.success, emoji="💾", row=3)
        async def save_cb(i: discord.Interaction):
            p_id = db.save_panel(
                panel_id=self.panel_data.get("id"),
                title=self.panel_data["title"],
                description=self.panel_data["description"],
                color=self.panel_data.get("color", EmbedBuilder.COLOR_PRIMARY),
                categories=self.panel_data.get("categories", []),
                channel_id=self.panel_data.get("channel_id"),
                message_id=self.panel_data.get("message_id"),
                image_url=self.panel_data.get("image_url")
            )

            # Update live message if channel and message_id exist
            ch_id = self.panel_data.get("channel_id")
            msg_id = self.panel_data.get("message_id")
            if ch_id and msg_id and i.guild:
                ch = i.guild.get_channel(ch_id)
                if ch:
                    try:
                        msg = await ch.fetch_message(msg_id)
                        p_embed = EmbedBuilder.panel_embed(
                            title=self.panel_data["title"],
                            description=self.panel_data["description"],
                            color=self.panel_data.get("color", EmbedBuilder.COLOR_PRIMARY),
                            guild=i.guild,
                            image_url=self.panel_data.get("image_url"),
                            categories=self.panel_data.get("categories", [])
                        )
                        p_view = PanelView(categories=self.panel_data.get("categories", []), panel_id=p_id)
                        await msg.edit(embed=p_embed, view=p_view)
                    except Exception:
                        pass

            db.log_settings_change(i.guild_id, i.user.id, "EDIT_PANEL", f"Updated Panel #{p_id} ({self.panel_data['title']})")
            await i.response.send_message(f"✅ **تم حفظ الإعدادات وتحديث رسالة اللوحة الحية في ديسكورد بنجاح!**", ephemeral=True)

        b_save.callback = save_cb
        self.add_item(b_save)

    def build_editor_embed(self, guild: discord.Guild) -> discord.Embed:
        p = self.panel_data
        cats = p.get("categories", [])

        embed = discord.Embed(
            title=f"🎛️ محرّر اللوحة التفاعلي #{p.get('id', 'جديدة')}",
            description=(
                f"**عنوان اللوحة:** {p.get('title')}\n"
                f"**الوصف:** {p.get('description')}\n"
                f"**اللون:** `#{p.get('color', 5793266):06X}`\n"
                f"**الصورة:** {p.get('image_url') or 'لا يوجد'}\n"
                f"**عدد الأقسام:** `{len(cats)}`"
            ),
            color=p.get("color", EmbedBuilder.COLOR_PRIMARY)
        )

        for idx, c in enumerate(cats):
            is_sel = "👈 (مختار)" if idx == self.selected_cat_index else ""
            roles_str = " ".join([f"<@&{r}>" for r in c.get("support_role_ids", [])]) if c.get("support_role_ids") else "الافتراضية"
            cat_ch = f"<#{c.get('category_id')}>" if c.get("category_id") else "بدون تصنيف"

            embed.add_field(
                name=f"{c.get('emoji', '🎫')} {idx+1}. {c.get('name')} {is_sel}",
                value=(
                    f"• **الوصف:** {c.get('description')}\n"
                    f"• **التصنيف:** {cat_ch}\n"
                    f"• **الرتب المسؤولة:** {roles_str}\n"
                    f"• **النقاط:** `{c.get('points', 5)}` نقطة\n"
                    f"• **حد التذاكر:** `{c.get('max_tickets', 1)}`"
                ),
                inline=False
            )

        return embed


class ImportJsonModal(Modal):
    def __init__(self):
        super().__init__(title="📥 استيراد الإعدادات من JSON")

        self.json_input = TextInput(
            label="الصق كود JSON للإعدادات هنا",
            style=discord.TextStyle.paragraph,
            placeholder='{"version": "2.0", "settings": {...}, "panels": [...]}',
            required=True,
            max_length=4000
        )
        self.add_item(self.json_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not await check_perm_or_deny(interaction):
            return

        try:
            data = json.loads(self.json_input.value.strip())
            db.import_guild_config(interaction.guild_id, data, interaction.user.id)
            await interaction.response.send_message("✅ **تم استيراد كافة الإعدادات واللوحات بنجاح!**", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ فشل تحليل أو استيراد كود JSON: {e}", ephemeral=True)


def build_in_app_settings_embed(bot: discord.Client, guild: Any) -> discord.Embed:
    if isinstance(guild, int):
        g_id = guild
    elif hasattr(guild, "id"):
        g_id = guild.id
    else:
        g_id = 0
    settings = db.get_guild_settings(g_id) or {}
    panels = db.get_panels() or []

    log_ch = f"<#{settings.get('log_channel_id')}>" if settings.get("log_channel_id") else "غير مفعّلة ❌"
    trans_ch = f"<#{settings.get('transcript_channel_id')}>" if settings.get("transcript_channel_id") else "غير مفعّلة ❌"
    supp_role = f"<@&{settings.get('support_role_id')}>" if settings.get("support_role_id") else "غير محددة ❌"

    cd = settings.get("cooldown_seconds", 10)
    mt = settings.get("max_open_tickets", 1)

    all_tickets = db.get_all_tickets() or []
    open_t = len([t for t in all_tickets if t.get("status") == "open"])
    closed_t = len([t for t in all_tickets if t.get("status") in ["closed", "deleted"]])

    embed = discord.Embed(
        title="⚙️ مركز إعدادات البوت والتحكم الشامل داخل ديسكورد",
        description=(
            f"مرحباً بك في نظام إدارة وتكوين البوت المباشر بدون موقع خارجي!\n"
            f"**مالك البوت الأصلي:** <@{MASTER_OWNER_ID}> (ID: `{MASTER_OWNER_ID}`)"
        ),
        color=0x5865F2
    )

    if hasattr(guild, "icon") and guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(
        name="📊 حالة النظام واللوحات",
        value=(
            f"• 🎯 اللوحات المفعلة: `{len(panels)}` لوحة\n"
            f"• 🎫 إجمالي التذاكر: `{len(all_tickets)}`\n"
            f"• 🔓 التذاكر المفتوحة: `{open_t}`\n"
            f"• 🔒 التذاكر المغلقة: `{closed_t}`"
        ),
        inline=True
    )

    embed.add_field(
        name="📋 القنوات والسجلات",
        value=(
            f"• 📋 قناة السجلات: {log_ch}\n"
            f"• 📜 قناة الترانسكريبت: {trans_ch}\n"
            f"• 👥 رتبة الدعم: {supp_role}"
        ),
        inline=True
    )

    embed.add_field(
        name="🛡️ إعدادات الحماية والحدود",
        value=(
            f"• ⏱️ الانتظار بين التذاكر: `{cd}` ثانية\n"
            f"• 🎫 الحد الأقصى للتذاكر: `{mt}` تذكرة/عضو"
        ),
        inline=True
    )

    embed.set_footer(text="استخدم الأزرار أسفله للتعديل المباشر أو ابدأ معالج الإعداد الجديد عبر /setup")
    return embed
