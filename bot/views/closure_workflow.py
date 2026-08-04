import discord
from discord.ui import View, Button, Select, Modal, TextInput
from bot.database.db import db
from bot.utils.embeds import EmbedBuilder
from bot.utils.permissions import PermissionHandler
from datetime import datetime, timedelta
import re

def parse_user_id(val: str) -> int:
    if not val:
        return 0
    digits = re.sub(r"\D", "", val)
    return int(digits) if digits else 0

class ComplaintClosureModal(Modal):
    def __init__(self, ticket_id: int, on_complete):
        super().__init__(title="🚨 استبيان تفاصيل الشكوى والعقوبة")
        self.ticket_id = ticket_id
        self.on_complete = on_complete

        self.punished_user_input = TextInput(
            label="معرف أو منشن العضو المعاقب (إن وجد)",
            placeholder="مثال: @User أو 123456789012345678",
            style=discord.TextStyle.short,
            required=False
        )
        self.timeout_duration_input = TextInput(
            label="مدة التايم أوت بالدقائق (مثال: 60)",
            placeholder="اكتب عدد الدقائق إذا كان العقاب تايم أوت (مثال: 60 أو 1440)",
            style=discord.TextStyle.short,
            required=False
        )
        self.evidence = TextInput(
            label="رابط الأدلة (صور/فيديو)",
            placeholder="انسخ رابط الصورة أو الفيديو هنا...",
            style=discord.TextStyle.paragraph,
            required=False
        )
        self.details = TextInput(
            label="سبب العقوبة / الحيثيات والتفاصيل",
            placeholder="اكتب أسباب العقوبة والتفاصيل الحيثية...",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.punished_user_input)
        self.add_item(self.timeout_duration_input)
        self.add_item(self.evidence)
        self.add_item(self.details)

    async def on_submit(self, interaction: discord.Interaction):
        p_user_id = parse_user_id(self.punished_user_input.value)
        dur = parse_user_id(self.timeout_duration_input.value)
        await self.on_complete(
            interaction,
            evidence=self.evidence.value,
            details=self.details.value,
            punished_user_id=p_user_id,
            timeout_duration=dur
        )

class NonComplaintClosureModal(Modal):
    def __init__(self, ticket_id: int, on_complete):
        super().__init__(title="📋 تفاصيل التعامل مع الطلب / الاقتراح")
        self.ticket_id = ticket_id
        self.on_complete = on_complete

        self.details = TextInput(
            label="سبب القبول أو الرفض / تفاصيل التعامل",
            placeholder="لماذا تم قبول/رفض الاقتراح أو كيف تم التعامل مع المشكلة...",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.evidence = TextInput(
            label="رابط الأدلة / التوضيحات (اختياري)",
            placeholder="أي روابط إضافية أو صور توضيحية...",
            style=discord.TextStyle.paragraph,
            required=False
        )
        self.add_item(self.details)
        self.add_item(self.evidence)

    async def on_submit(self, interaction: discord.Interaction):
        await self.on_complete(
            interaction,
            evidence=self.evidence.value,
            details=self.details.value,
            punished_user_id=0,
            timeout_duration=0
        )

class ClosureWorkflowView(View):
    def __init__(self, ticket_id: int, original_action: str, lang: str = "ar"):
        super().__init__(timeout=600)
        self.ticket_id = ticket_id
        self.original_action = original_action  # 'close' or 'delete'
        self.lang = lang

        self.user_answered = False
        self.staff_answered = False

        self.user_handled = 0
        self.ticket_type = "general"
        self.complaint_accepted = 0
        self.punished_user_id = 0
        self.punishment_type = "none"
        self.timeout_duration = 0
        self.evidence_urls = ""
        self.staff_details = ""
        self.staff_punished = 0

        self.add_user_buttons()

    def add_user_buttons(self):
        self.clear_items()
        
        select_type = Select(
            placeholder="1️⃣ (صاحب التذكرة) اختر نوع الاستبيان / التذكرة...",
            options=[
                discord.SelectOption(label="🚨 تيكت شكوى (Complaint)", value="complaint", emoji="🚨", description="شكوى ضد عضو أو إداري أو مخالفة"),
                discord.SelectOption(label="💡 تيكت اقتراح (Suggestion)", value="suggestion", emoji="💡", description="اقتراح جديد لتطوير السيرفر"),
                discord.SelectOption(label="💬 استفسار / دعم فني عام (Inquiry)", value="general", emoji="💬", description="استفسار أو مشكلة عامة")
            ]
        )
        select_type.callback = self.user_type_callback
        self.add_item(select_type)

        btn_yes = Button(label="نعم، تم التعامل / النظر في الطلب", style=discord.ButtonStyle.success, custom_id="user_yes")
        btn_no = Button(label="لا، لم يتم التعامل", style=discord.ButtonStyle.danger, custom_id="user_no")

        btn_yes.callback = self.user_yes_callback
        btn_no.callback = self.user_no_callback

        self.add_item(btn_yes)
        self.add_item(btn_no)

        btn_skip = Button(label="⏩ تخطي الاستبيان (إنهاء فوراً)", style=discord.ButtonStyle.secondary, custom_id="skip_survey")
        btn_skip.callback = self.skip_survey_callback
        self.add_item(btn_skip)

    async def skip_survey_callback(self, interaction: discord.Interaction):
        is_owner = (
            interaction.guild and interaction.user.id == interaction.guild.owner_id
        ) or PermissionHandler.is_bot_owner(interaction.user.id)

        if not is_owner:
            return await interaction.response.send_message("❌ زر تخطي الاستبيان مخصص فقط لمالك السيرفر (Owner).", ephemeral=True)

        self.user_answered = True
        self.staff_answered = True
        self.staff_details = "تم تخطي الاستبيان بواسطة مالك السيرفر"

        db.save_closure_info(
            ticket_id=self.ticket_id,
            user_handled=1,
            staff_punished=0,
            evidence_urls="",
            punishment_type="none",
            staff_details=self.staff_details,
            ticket_type=self.ticket_type or "general",
            complaint_accepted=0,
            punished_user_id=0,
            timeout_duration=0
        )

        embed = EmbedBuilder.create_embed(
            title="⏩ تم تخطي الاستبيان",
            description="تم تخطي الاستبيان بنجاح وجاري استكمال إجراءات الإغلاق...",
            color=EmbedBuilder.COLOR_PRIMARY
        )
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)

        if self.final_callback:
            await self.final_callback()

    async def user_type_callback(self, interaction: discord.Interaction):
        ticket = db.get_ticket_by_id(self.ticket_id)
        if interaction.user.id != ticket.get("user_id"):
            return await interaction.response.send_message("❌ هذا الاختيار مخصص لصاحب التذكرة فقط.", ephemeral=True)

        self.ticket_type = interaction.data["values"][0]
        type_labels = {
            "complaint": "🚨 شكوى",
            "suggestion": "💡 اقتراح",
            "general": "💬 استفسار / دعم فني عام"
        }
        await interaction.response.send_message(f"✅ تم تحديد نوع التذكرة بواسطة صاحب التذكرة: **{type_labels.get(self.ticket_type, self.ticket_type)}**. يرجى الآن الضغط على زر (نعم) أو (لا) للإنهاء.", ephemeral=True)

    async def user_yes_callback(self, interaction: discord.Interaction):
        ticket = db.get_ticket_by_id(self.ticket_id)
        if interaction.user.id != ticket.get("user_id"):
            return await interaction.response.send_message("❌ هذا السؤال مخصص لصاحب التذكرة فقط.", ephemeral=True)

        self.user_handled = 1
        self.user_answered = True
        await self.update_workflow(interaction)

    async def user_no_callback(self, interaction: discord.Interaction):
        ticket = db.get_ticket_by_id(self.ticket_id)
        if interaction.user.id != ticket.get("user_id"):
            return await interaction.response.send_message("❌ هذا السؤال مخصص لصاحب التذكرة فقط.", ephemeral=True)

        self.user_handled = 0
        self.user_answered = True
        await self.update_workflow(interaction)

    def add_staff_punishment_select(self):
        self.clear_items()
        if self.ticket_type == "complaint":
            select = Select(
                placeholder="2️⃣ اختر حالة الشكوى ونوع العقوبة المتخذة...",
                options=[
                    discord.SelectOption(label="⏳ قبول الشكوى - معاقبة بتايم أوت (Timeout)", value="timeout", emoji="⏳"),
                    discord.SelectOption(label="⚠️ قبول الشكوى - تحذير رسمي (Official Warning)", value="official_warning", emoji="⚠️"),
                    discord.SelectOption(label="🗣️ قبول الشكوى - تحذير شفهي (Verbal Warning)", value="verbal_warning", emoji="🗣️"),
                    discord.SelectOption(label="🤝 قبول الشكوى - تم حل المشكلة ودي (Friendly)", value="friendly", emoji="🤝"),
                    discord.SelectOption(label="❌ رفض الشكوى / لا يوجد عقوبة", value="none", emoji="❌")
                ]
            )
            select.callback = self.staff_complaint_option_callback
            self.add_item(select)
        else:
            select = Select(
                placeholder="2️⃣ اختر نتيجة التعامل مع الطلب / الاقتراح...",
                options=[
                    discord.SelectOption(label="✅ تم قبول الاقتراح / التعامل بنجاح مع المشكلة", value="accepted", emoji="✅"),
                    discord.SelectOption(label="❌ تم رفض الاقتراح / تعذر التعامل مع المشكلة", value="rejected", emoji="❌")
                ]
            )
            select.callback = self.staff_non_complaint_option_callback
            self.add_item(select)

        btn_modal = Button(label="📝 تعبئة بيانات الحيثيات والتفاصيل", style=discord.ButtonStyle.primary)
        btn_modal.callback = self.staff_modal_trigger
        self.add_item(btn_modal)

        btn_skip = Button(label="⏩ تخطي الاستبيان (إنهاء فوراً)", style=discord.ButtonStyle.secondary, custom_id="skip_survey_staff")
        btn_skip.callback = self.skip_survey_callback
        self.add_item(btn_skip)

    async def staff_complaint_option_callback(self, interaction: discord.Interaction):
        ticket = db.get_ticket_by_id(self.ticket_id)
        if interaction.user.id != ticket.get("claimed_by"):
            return await interaction.response.send_message("❌ هذا الإجراء مخصص للموظف المستلم فقط.", ephemeral=True)

        val = interaction.data["values"][0]
        self.punishment_type = val
        if val in ["timeout", "official_warning", "verbal_warning", "friendly"]:
            self.complaint_accepted = 1
            self.staff_punished = 1 if val != "friendly" else 0
        else:
            self.complaint_accepted = 0
            self.staff_punished = 0

        await interaction.response.send_message(f"✅ تم تحديد العقوبة / النتيجة: **{val}**. يرجى الآن الضغط على زر التعبئة لإنهاء الاستبيان.", ephemeral=True)

    async def staff_non_complaint_option_callback(self, interaction: discord.Interaction):
        ticket = db.get_ticket_by_id(self.ticket_id)
        if interaction.user.id != ticket.get("claimed_by"):
            return await interaction.response.send_message("❌ هذا الإجراء مخصص للموظف المستلم فقط.", ephemeral=True)

        val = interaction.data["values"][0]
        self.complaint_accepted = 1 if val == "accepted" else 0
        self.punishment_type = val
        self.staff_punished = 0

        await interaction.response.send_message(f"✅ تم تحديد النتيجة: **{val}**. يرجى الآن الضغط على زر التعبئة لإنهاء الاستبيان.", ephemeral=True)

    async def staff_modal_trigger(self, interaction: discord.Interaction):
        ticket = db.get_ticket_by_id(self.ticket_id)
        if interaction.user.id != ticket.get("claimed_by"):
            return await interaction.response.send_message("❌ هذا الإجراء مخصص للموظف المستلم فقط.", ephemeral=True)

        if self.ticket_type == "complaint":
            await interaction.response.send_modal(ComplaintClosureModal(self.ticket_id, self.staff_modal_complete))
        else:
            await interaction.response.send_modal(NonComplaintClosureModal(self.ticket_id, self.staff_modal_complete))

    async def staff_modal_complete(self, interaction: discord.Interaction, evidence: str, details: str, punished_user_id: int, timeout_duration: int):
        self.evidence_urls = evidence
        self.staff_details = details
        self.punished_user_id = punished_user_id
        self.timeout_duration = timeout_duration
        self.staff_answered = True

        await self.update_workflow(interaction)

    async def update_workflow(self, interaction: discord.Interaction):
        if self.user_answered and not self.staff_answered:
            self.add_staff_punishment_select()
            embed = interaction.message.embeds[0]
            type_labels = {
                "complaint": "🚨 شكوى",
                "suggestion": "💡 اقتراح",
                "general": "💬 استفسار / دعم فني عام"
            }
            embed.description = (
                f"✅ أجاب صاحب التذكرة وحدد نوع التذكرة: **{type_labels.get(self.ticket_type, self.ticket_type)}**.\n"
                f"⏳ الآن يرجى من الموظف المستلم تحديد نتيجة الاستبيان والعقوبات الحيثية إن وجدت."
            )
            await interaction.response.edit_message(embed=embed, view=self)

        elif self.staff_answered and self.user_answered:
            db.save_closure_info(
                ticket_id=self.ticket_id,
                user_handled=self.user_handled,
                staff_punished=self.staff_punished,
                evidence_urls=self.evidence_urls,
                punishment_type=self.punishment_type,
                staff_details=self.staff_details,
                ticket_type=self.ticket_type,
                complaint_accepted=self.complaint_accepted,
                punished_user_id=self.punished_user_id,
                timeout_duration=self.timeout_duration
            )

            guild = interaction.guild
            staff_user = interaction.user

            # Handle automatic sanctions and notifications
            if self.punished_user_id > 0 and guild:
                target_member = guild.get_member(self.punished_user_id)
                if not target_member:
                    try:
                        target_member = await guild.fetch_member(self.punished_user_id)
                    except Exception:
                        target_member = None

                ticket_ref = f"`#{self.ticket_id}`"

                if target_member:
                    # Time-out Execution
                    if self.punishment_type == "timeout":
                        dur_minutes = self.timeout_duration if self.timeout_duration > 0 else 60
                        try:
                            await target_member.timeout(timedelta(minutes=dur_minutes), reason=f"تكت #{self.ticket_id}: {self.staff_details}")
                        except Exception as e:
                            print(f"Error applying timeout: {e}")

                        db.add_infraction(
                            guild_id=guild.id,
                            user_id=target_member.id,
                            infraction_type="timeout",
                            reason=self.staff_details,
                            duration_minutes=dur_minutes,
                            executor_id=staff_user.id,
                            ticket_id=self.ticket_id
                        )

                        try:
                            dm_embed = EmbedBuilder.create_embed(
                                title="⏳ تنبيه: تم تطبيق عقوبة التايم أوت بحقك",
                                description=(
                                    f"مرحباً {target_member.mention} 👋،\n"
                                    f"تم تطبيق عقوبة **التايم أوت (Time-out)** بحقك في سيرفر **{guild.name}**.\n\n"
                                    f"📊 **تفاصيل العقوبة:**\n"
                                    f"• **التذكرة المرتبطة:** {ticket_ref}\n"
                                    f"• **مدة التايم أوت:** `{dur_minutes}` دقيقة\n"
                                    f"• **السبب والحيثيات:** {self.staff_details}\n"
                                    f"• **بواسطة المسؤول:** {staff_user.mention}\n\n"
                                    f"⚠️ **ملاحظة هامة:** تم تطبيق هذه العقوبة بسبب مخالفة القوانين. في حال كان لديك أي اعتراض، يمكنك فتح تذكرة دعم فني **بعد انتهاء مدة التايم أوت** لمراجعة الأمر مع الإدارة."
                                ),
                                color=EmbedBuilder.COLOR_ERROR
                            )
                            await target_member.send(embed=dm_embed)
                        except Exception as e:
                            print(f"Error sending timeout DM: {e}")

                    # Official Warning Execution
                    elif self.punishment_type == "official_warning":
                        db.add_infraction(
                            guild_id=guild.id,
                            user_id=target_member.id,
                            infraction_type="official_warning",
                            reason=self.staff_details,
                            duration_minutes=0,
                            executor_id=staff_user.id,
                            ticket_id=self.ticket_id
                        )

                        try:
                            dm_embed = EmbedBuilder.create_embed(
                                title="⚠️ تنبيه: تم توجيه تحذير رسمي بحقك",
                                description=(
                                    f"مرحباً {target_member.mention} 👋،\n"
                                    f"تم توجيه **تحذير رسمي (Official Warning)** بحقك في سيرفر **{guild.name}**.\n\n"
                                    f"📊 **تفاصيل التحذير:**\n"
                                    f"• **التذكرة المرتبطة:** {ticket_ref}\n"
                                    f"• **السبب والحيثيات:** {self.staff_details}\n"
                                    f"• **بواسطة المسؤول:** {staff_user.mention}\n\n"
                                    f"⚠️ **ملاحظة هامة:** تم توجيه هذا التحذير بسبب مخالفة قوانين السيرفر. في حال كان لديك أي اعتراض، يمكنك فتح تذكرة دعم فني لمراجعة الأمر."
                                ),
                                color=EmbedBuilder.COLOR_WARNING
                            )
                            await target_member.send(embed=dm_embed)
                        except Exception as e:
                            print(f"Error sending official warning DM: {e}")

                    # Verbal Warning Execution
                    elif self.punishment_type == "verbal_warning":
                        db.add_infraction(
                            guild_id=guild.id,
                            user_id=target_member.id,
                            infraction_type="verbal_warning",
                            reason=self.staff_details,
                            duration_minutes=0,
                            executor_id=staff_user.id,
                            ticket_id=self.ticket_id
                        )

                        try:
                            dm_embed = EmbedBuilder.create_embed(
                                title="🗣️ تنبيه: تم توجيه تحذير شفهي بحقك",
                                description=(
                                    f"مرحباً {target_member.mention} 👋،\n"
                                    f"تم توجيه **تحذير شفهي (Verbal Warning)** بحقك في سيرفر **{guild.name}**.\n\n"
                                    f"📊 **تفاصيل التنبيه:**\n"
                                    f"• **التذكرة المرتبطة:** {ticket_ref}\n"
                                    f"• **السبب والحيثيات:** {self.staff_details}\n"
                                    f"• **بواسطة المسؤول:** {staff_user.mention}\n\n"
                                    f"⚠️ **ملاحظة هامة:** تم توجيه هذا التحذير الشفهي بسبب مخالفة القوانين. في حال كان لديك أي اعتراض، يمكنك فتح تذكرة دعم فني لمراجعة الأمر."
                                ),
                                color=EmbedBuilder.COLOR_INFO
                            )
                            await target_member.send(embed=dm_embed)
                        except Exception as e:
                            print(f"Error sending verbal warning DM: {e}")

            embed = interaction.message.embeds[0]
            embed.description = "✅ اكتمل استبيان إغلاق التذكرة بنجاح وتسجيل جميع البيانات. جاري تنفيذ الإجراء المطلوب..."
            embed.color = discord.Color.green()
            await interaction.response.edit_message(embed=embed, view=None)

            if hasattr(self, 'final_callback'):
                await self.final_callback()
