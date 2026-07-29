import re
import logging
import discord
from discord.ui import View, Select, Button, Modal, TextInput
from bot.database.db import db
from bot.utils.antispam import antispam
from bot.config.locales import get_text
from bot.utils.embeds import EmbedBuilder

logger = logging.getLogger("discord_bot")

class TicketQuestionsModal(Modal):
    def __init__(
        self,
        panel_id: int,
        category_id: str,
        category_info: dict,
        lang: str,
        permission_overwrites: dict,
        target_category_obj: any,
        category_name: str,
        pings: list
    ):
        modal_title = f"📝 بيانات تذكرة: {category_name[:30]}"
        super().__init__(title=modal_title)
        
        self.panel_id = panel_id
        self.category_id = category_id
        self.category_info = category_info
        self.lang = lang
        self.permission_overwrites = permission_overwrites
        self.target_category_obj = target_category_obj
        self.category_name = category_name
        self.pings = pings

        # Determine questions to ask
        configured_questions = category_info.get("questions") or []
        self.text_inputs = []

        if configured_questions and isinstance(configured_questions, list):
            for idx, q in enumerate(configured_questions[:5]):
                label = q.get("label") or f"السؤال {idx + 1}"
                is_req = q.get("required", True)
                style_type = discord.TextStyle.paragraph if q.get("style") == "paragraph" else discord.TextStyle.short
                inp = TextInput(
                    label=label[:45],
                    placeholder=q.get("placeholder", "أدخل الإجابة هنا...")[:100],
                    style=style_type,
                    required=is_req,
                    max_length=1000
                )
                self.text_inputs.append(inp)
                self.add_item(inp)
        else:
            # Default interactive questions
            q1 = TextInput(
                label="السبب الرئيسي لفتح التذكرة",
                placeholder="أدخل عنوان أو سبب فتح التذكرة هنا...",
                style=discord.TextStyle.short,
                required=True,
                max_length=150
            )
            q2 = TextInput(
                label="تفاصيل وتوضيح الطلب / المشكلة",
                placeholder="اشرح المشكلة أو الاستفسار بالتفصيل...",
                style=discord.TextStyle.paragraph,
                required=True,
                max_length=1000
            )
            q3 = TextInput(
                label="أي معلومات إضافية / معرّف أو رابط (اختياري)",
                placeholder="مثال: اسم حسابك، رابط، أو صورة...",
                style=discord.TextStyle.short,
                required=False,
                max_length=200
            )
            self.text_inputs = [q1, q2, q3]
            self.add_item(q1)
            self.add_item(q2)
            self.add_item(q3)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        guild = interaction.guild

        if not guild:
            return await interaction.followup.send("❌ حدث خطأ: تعذر الوصول إلى بيانات السيرفر.", ephemeral=True)

        try:
            # 1. Clean username for channel name
            clean_username = re.sub(r'[^a-zA-Z0-9]', '', interaction.user.name).lower()
            if not clean_username:
                clean_username = f"user-{user_id % 10000}"
            channel_name = f"ticket-{clean_username}"

            # 2. Create ticket channel with correct overwrites argument
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=self.target_category_obj if isinstance(self.target_category_obj, discord.CategoryChannel) else None,
                overwrites=self.permission_overwrites,
                reason=f"Support ticket opened by {interaction.user.name}"
            )

            # 3. Save ticket in database
            ticket_id = db.create_ticket(
                guild_id=guild.id,
                channel_id=ticket_channel.id,
                user_id=user_id,
                panel_id=self.panel_id,
                category_id=self.category_id,
                points=self.category_info.get("points", 0)
            )

            # 4. Prepare Answers Embed Section
            answers_text = ""
            for inp in self.text_inputs:
                ans_val = inp.value.strip() if inp.value else "*(لم يتم التحديد)*"
                answers_text += f"• **{inp.label}:**\n```{ans_val}```\n"

            # 5. Welcome Embed & Controls
            from bot.views.ticket_controls import TicketControlView
            welcome_embed = EmbedBuilder.ticket_welcome_embed(interaction.user, self.category_name, lang=self.lang, guild=guild)

            custom_welcome = self.category_info.get("welcome_msg")
            if custom_welcome and custom_welcome.strip():
                fmt_welcome = custom_welcome.replace("{user}", interaction.user.mention).replace("{category}", self.category_name).replace("{server}", guild.name)
                welcome_embed.description = fmt_welcome

            if answers_text:
                welcome_embed.add_field(
                    name="📝 بيانات وإجابات النموذج التفاعلي (Submitted Details):",
                    value=answers_text[:1024],
                    inline=False
                )

            control_view = TicketControlView(lang=self.lang)
            ping_content = " | ".join(self.pings)

            await ticket_channel.send(content=ping_content, embed=welcome_embed, view=control_view)

            # 6. Send DM confirmation
            try:
                dm_embed = discord.Embed(
                    title="🎫 تم فتح تذكرتك بنجاح!",
                    description=(
                        f"مرحباً {interaction.user.mention}،\n"
                        f"لقد قمت بفتح تذكرة جديدة في سيرفر **{guild.name}**.\n\n"
                        f"📌 **قناة التذكرة:** {ticket_channel.mention}\n"
                        f"🏷️ **القسم:** `{self.category_name}`\n\n"
                        f"يرجى الانتقال إلى القناة ومتابعة الردود مع فريق الدعم."
                    ),
                    color=EmbedBuilder.COLOR_PRIMARY
                )
                if guild.icon:
                    dm_embed.set_footer(text=guild.name, icon_url=guild.icon.url)
                else:
                    dm_embed.set_footer(text=guild.name)

                await interaction.user.send(content=f"🔔 **تم فتح تذكرتك بنجاح:** {ticket_channel.mention}", embed=dm_embed)
            except Exception as dm_err:
                logger.warning(f"Could not send DM to {interaction.user}: {dm_err}")

            success_msg = get_text("ticket_created_success", lang=self.lang, channel=ticket_channel.mention)
            await interaction.followup.send(
                f"{success_msg}\n*(ملاحظة: يمكنك استخدام خيار 🔄 **إعادة تعيين القائمة** عند الحاجة لإعادة الاختيار)*",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"❌ Error creating ticket: {e}", exc_info=True)
            await interaction.followup.send(f"❌ حدث خطأ غير متوقع أثناء إنشاء التذكرة:\n```{str(e)[:500]}```", ephemeral=True)


class TicketCategorySelect(Select):
    def __init__(self, categories: list, panel_id: int, lang: str = "ar"):
        self.panel_id = panel_id
        self.lang = lang
        options = []
        if categories:
            for cat in categories:
                raw_emoji = cat.get("emoji", "🎫")
                if raw_emoji:
                    raw_emoji = raw_emoji.strip()
                    if raw_emoji.startswith("<") and raw_emoji.endswith(">"):
                        emoji = raw_emoji
                    else:
                        cleaned = raw_emoji.replace("\ufe0f", "")
                        if not cleaned or any(c.isalpha() for c in cleaned):
                            emoji = "🎫"
                        else:
                            emoji = cleaned
                else:
                    emoji = "🎫"

                options.append(discord.SelectOption(
                    label=cat.get("name", "Ticket"),
                    description=cat.get("description", "Click to open ticket")[:100],
                    emoji=emoji,
                    value=str(cat.get("id", "general"))
                ))
        if not options:
            options.append(discord.SelectOption(
                label="قسم الدعم العامة",
                description="انقر هنا لفتح تذكرة جديدة",
                emoji="🎫",
                value="general"
            ))

        # Reset selection option
        options.append(discord.SelectOption(
            label="🔄 إعادة تعيين القائمة / Reset Selection",
            description="تفريغ القائمة لتتمكن من اختيار نفس القسم مجدداً",
            emoji="🔄",
            value="reset_selection"
        ))

        placeholder = get_text("panel_select_placeholder", lang=lang)
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options, custom_id=f"panel_select_{panel_id}")

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        category_id = self.values[0]

        # Handle Restart / Reset Selection option
        if category_id in ["reset_selection", "reset", "restart"]:
            await interaction.response.defer(ephemeral=True)
            return await interaction.followup.send(
                "🔄 **تم إعادة تعيين القائمة بنجاح!** يمكنك الآن اختيار القسم المطلوب مجدداً من القائمة.",
                ephemeral=True
            )

        try:
            # 1. Check blacklist
            if db.is_blacklisted(user_id):
                await interaction.response.defer(ephemeral=True)
                msg = get_text("blacklisted_user", lang=self.lang)
                return await interaction.followup.send(msg, ephemeral=True)

            # 2. Check anti-spam cooldown
            allowed, remaining = antispam.check_cooldown(user_id)
            if not allowed:
                await interaction.response.defer(ephemeral=True)
                return await interaction.followup.send(f"⏳ يرجى الانتظار {remaining:.1f} ثوانٍ قبل فتح تذكرة أخرى.", ephemeral=True)

            # 3. Check existing open ticket limit
            existing = db.get_user_open_ticket(user_id, category_id)
            if existing and interaction.guild:
                existing_ch = interaction.guild.get_channel(existing["channel_id"])
                if existing_ch:
                    await interaction.response.defer(ephemeral=True)
                    msg = get_text("ticket_limit_reached", lang=self.lang)
                    return await interaction.followup.send(f"{msg}\n📌 **تذكرتك المفتوحة حالياً:** {existing_ch.mention}", ephemeral=True)
                else:
                    db.update_ticket_status(existing["channel_id"], "deleted")

            # 4. Fetch panel and category info
            panel_id_target = self.panel_id
            if not panel_id_target or panel_id_target == 0:
                try:
                    custom_id_str = interaction.data.get("custom_id", "")
                    if "panel_select_" in custom_id_str:
                        panel_id_target = int(custom_id_str.replace("panel_select_", ""))
                except Exception:
                    panel_id_target = 0

            panel = db.get_panel_by_id(panel_id_target) if panel_id_target else None
            if not panel:
                panels = db.get_panels() or []
                panel = next((p for p in panels if p["id"] == panel_id_target), None) if panel_id_target else (panels[0] if panels else None)

            category_info = {}
            if panel and panel.get("categories"):
                for cat in panel.get("categories", []):
                    if str(cat.get("id")) == str(category_id):
                        category_info = cat
                        break

            guild = interaction.guild
            if not guild:
                await interaction.response.defer(ephemeral=True)
                return await interaction.followup.send("❌ حدث خطأ: تعذر الوصول إلى بيانات السيرفر.", ephemeral=True)

            guild_settings = db.get_guild_settings(guild.id) or {}

            # Permission overwrites setup
            permission_overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True)
            }

            bot_member = guild.me or guild.get_member(interaction.client.user.id)
            if bot_member:
                permission_overwrites[bot_member] = discord.PermissionOverwrite(
                    read_messages=True, send_messages=True, manage_channels=True, manage_messages=True, attach_files=True, embed_links=True
                )

            # Staff roles
            roles_to_allow = []
            if category_info.get("support_role_ids"):
                roles_to_allow.extend(category_info["support_role_ids"])
            elif category_info.get("support_role_id"):
                roles_to_allow.append(category_info["support_role_id"])
            else:
                if guild_settings.get("support_role_id"):
                    roles_to_allow.append(guild_settings["support_role_id"])
                if guild_settings.get("senior_support_role_id"):
                    roles_to_allow.append(guild_settings["senior_support_role_id"])

            if category_info.get("admin_role_id"):
                roles_to_allow.append(category_info["admin_role_id"])
            else:
                if guild_settings.get("admin_role_id"):
                    roles_to_allow.append(guild_settings["admin_role_id"])
                if guild_settings.get("owner_role_id"):
                    roles_to_allow.append(guild_settings["owner_role_id"])

            pings = [interaction.user.mention]
            for r_id in set(roles_to_allow):
                try:
                    if r_id and str(r_id).isdigit():
                        role_obj = guild.get_role(int(r_id))
                        if role_obj:
                            permission_overwrites[role_obj] = discord.PermissionOverwrite(
                                view_channel=True, send_messages=False, attach_files=True, embed_links=True, manage_messages=True
                            )
                            pings.append(role_obj.mention)
                except Exception:
                    pass

            # Target Discord Category Channel
            target_category_obj = None
            discord_cat_id = category_info.get("category_id") or guild_settings.get("category_id")
            if discord_cat_id and str(discord_cat_id).isdigit():
                try:
                    target_category_obj = guild.get_channel(int(discord_cat_id))
                    if not target_category_obj:
                        target_category_obj = await guild.fetch_channel(int(discord_cat_id))
                except Exception:
                    target_category_obj = None

            category_name = category_info.get("name") or next((c.label for c in self.options if c.value == category_id), "Ticket")

            # Pop up interactive Modal to collect user answers before creating ticket!
            questions_modal = TicketQuestionsModal(
                panel_id=self.panel_id,
                category_id=category_id,
                category_info=category_info,
                lang=self.lang,
                permission_overwrites=permission_overwrites,
                target_category_obj=target_category_obj,
                category_name=category_name,
                pings=pings
            )
            await interaction.response.send_modal(questions_modal)

        except Exception as e:
            logger.error(f"❌ Error initiating ticket modal: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
            await interaction.followup.send(f"❌ حدث خطأ غير متوقع أثناء إعداد التذكرة:\n```{str(e)[:500]}```", ephemeral=True)


class PanelView(View):
    def __init__(self, categories: list, panel_id: int, lang: str = "ar"):
        super().__init__(timeout=None)
        self.panel_id = panel_id
        self.add_item(TicketCategorySelect(categories, panel_id, lang))

    @discord.ui.button(label="🔄 ريستارت اللوحة", style=discord.ButtonStyle.secondary, custom_id="btn_restart_panel_view", row=1)
    async def btn_restart_panel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("🔄 **تم إعادة تشغيل وتحديث اللوحة بنجاح!**", ephemeral=True)
