import discord
from discord.ui import Modal, TextInput
from bot.database.db import db
from bot.config.locales import get_text
from bot.utils.embeds import EmbedBuilder
from bot.utils.logger import TicketLogger

class TransferTicketModal(Modal):
    def __init__(self, ticket: dict, lang: str = "ar"):
        super().__init__(title="🔄 نقل التذكرة إلى موظف آخر")
        self.ticket = ticket
        self.lang = lang

        self.staff_input = TextInput(
            label="معرف الموظف أو المنشن (ID or @Mention)",
            placeholder="مثال: 123456789012345678",
            required=True,
            max_length=100
        )
        self.add_item(self.staff_input)

    async def on_submit(self, interaction: discord.Interaction):
        val = self.staff_input.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        try:
            target_id = int(val)
            target_member = interaction.guild.get_member(target_id)
        except ValueError:
            target_member = None

        if not target_member:
            return await interaction.response.send_message("❌ لم يتم العثور على الموظف المحدد.", ephemeral=True)

        db.claim_ticket(interaction.channel_id, target_member.id)
        db.increment_staff_tickets(interaction.guild_id, target_member.id)
        
        # Award category points on transfer if desired (optional, but consistent)
        if self.ticket and self.ticket.get("category_points"):
            db.update_staff_points(interaction.guild_id, target_member.id, self.ticket.get("category_points", 0))
        
        embed = EmbedBuilder.create_embed(
            title="🔄 تم نقل التذكرة",
            description=f"تم نقل التذكرة بنجاح إلى الموظف {target_member.mention} بواسطة {interaction.user.mention}.",
            color=EmbedBuilder.COLOR_INFO
        )
        await interaction.response.send_message(embed=embed)

        await TicketLogger.log_action(
            guild=interaction.guild,
            ticket=self.ticket,
            action_name="نقل التذكرة",
            executor=interaction.user,
            details=f"تم النقل إلى الموظف: {target_member.display_name} ({target_member.id})"
        )

class ChangePriorityModal(Modal):
    def __init__(self, ticket: dict, lang: str = "ar"):
        super().__init__(title="⚡ تغيير أولوية التذكرة")
        self.ticket = ticket
        self.lang = lang

        self.priority_input = TextInput(
            label="الأولوية (منخفضة / متوسطة / عالية / عاجلة)",
            placeholder="مثال: عالية (High)",
            required=True,
            max_length=50
        )
        self.add_item(self.priority_input)

    async def on_submit(self, interaction: discord.Interaction):
        p_val = self.priority_input.value.strip()
        db.update_priority(interaction.channel_id, p_val)

        embed = EmbedBuilder.create_embed(
            title="⚡ تم تحديث الأولوية",
            description=get_text("priority_updated", self.lang, priority=p_val),
            color=EmbedBuilder.COLOR_WARNING
        )
        await interaction.response.send_message(embed=embed)

        await TicketLogger.log_action(
            guild=interaction.guild,
            ticket=self.ticket,
            action_name="تغيير الأولوية",
            executor=interaction.user,
            details=f"الأولوية الجديدة: {p_val}"
        )

class RenameTicketModal(Modal):
    def __init__(self, ticket: dict, lang: str = "ar"):
        super().__init__(title="✏️ تغيير اسم قناة التذكرة")
        self.ticket = ticket
        self.lang = lang

        self.name_input = TextInput(
            label="الاسم الجديد للقناة",
            placeholder="مثال: ticket-vip-issue",
            required=True,
            max_length=100
        )
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction):
        new_name = self.name_input.value.strip().lower().replace(" ", "-")
        old_name = interaction.channel.name
        await interaction.channel.edit(name=new_name)

        embed = EmbedBuilder.create_embed(
            title="✏️ تم تغيير الاسم",
            description=get_text("rename_success", self.lang, name=new_name),
            color=EmbedBuilder.COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed)

        await TicketLogger.log_action(
            guild=interaction.guild,
            ticket=self.ticket,
            action_name="تغيير الاسم",
            executor=interaction.user,
            details=f"من {old_name} إلى {new_name}"
        )

class ChangeDepartmentModal(Modal):
    def __init__(self, ticket: dict, lang: str = "ar"):
        super().__init__(title="🏢 نقل التذكرة إلى قسم آخر")
        self.ticket = ticket
        self.lang = lang

        self.dept_input = TextInput(
            label="اسم القسم الجديد",
            placeholder="مثال: قسم المبيعات والاشتراكات",
            required=True,
            max_length=100
        )
        self.add_item(self.dept_input)

    async def on_submit(self, interaction: discord.Interaction):
        new_dept = self.dept_input.value.strip()
        db.update_department(interaction.channel_id, new_dept)

        embed = EmbedBuilder.create_embed(
            title="🏢 تم تغيير القسم",
            description=get_text("dept_updated", self.lang, dept=new_dept),
            color=EmbedBuilder.COLOR_INFO
        )
        await interaction.response.send_message(embed=embed)

        await TicketLogger.log_action(
            guild=interaction.guild,
            ticket=self.ticket,
            action_name="تغيير القسم",
            executor=interaction.user,
            details=f"القسم الجديد: {new_dept}"
        )

class ChangeOwnerModal(Modal):
    def __init__(self, ticket: dict, lang: str = "ar"):
        super().__init__(title="👤 نقل ملكية التذكرة لعضو آخر")
        self.ticket = ticket
        self.lang = lang

        self.owner_input = TextInput(
            label="معرف المالك الجديد أو المنشن (ID or @Mention)",
            placeholder="مثال: 987654321098765432",
            required=True,
            max_length=100
        )
        self.add_item(self.owner_input)

    async def on_submit(self, interaction: discord.Interaction):
        val = self.owner_input.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        try:
            target_id = int(val)
            new_owner = interaction.guild.get_member(target_id)
        except ValueError:
            new_owner = None

        if not new_owner:
            return await interaction.response.send_message("❌ لم يتم العثور على العضو المحدد.", ephemeral=True)

        # Remove previous owner permissions
        old_owner_id = self.ticket.get("user_id")
        if old_owner_id:
            old_owner = interaction.guild.get_member(old_owner_id)
            if old_owner:
                await interaction.channel.set_permissions(old_owner, overwrite=None)

        # Grant new owner permissions
        await interaction.channel.set_permissions(new_owner, view_channel=True, send_messages=True, attach_files=True, embed_links=True, read_message_history=True)
        db.update_ticket_owner(interaction.channel_id, new_owner.id)

        embed = EmbedBuilder.create_embed(
            title="👤 تم نقل ملكية التذكرة",
            description=f"بات المالك الجديد للتذكرة هو: {new_owner.mention}",
            color=EmbedBuilder.COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed)

        await TicketLogger.log_action(
            guild=interaction.guild,
            ticket=self.ticket,
            action_name="تغيير مالك التذكرة",
            executor=interaction.user,
            details=f"المالك الجديد: {new_owner.display_name} ({new_owner.id})"
        )

class AddMemberModal(Modal):
    def __init__(self, ticket: dict, lang: str = "ar"):
        super().__init__(title="➕ إضافة عضو إلى التذكرة")
        self.ticket = ticket
        self.lang = lang

        self.member_input = TextInput(
            label="معرف العضو أو المنشن (ID or @Mention)",
            placeholder="مثال: 123456789012345678",
            required=True,
            max_length=100
        )
        self.add_item(self.member_input)

    async def on_submit(self, interaction: discord.Interaction):
        val = self.member_input.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        try:
            target_id = int(val)
            target_member = interaction.guild.get_member(target_id)
        except ValueError:
            target_member = None

        if not target_member:
            return await interaction.response.send_message("❌ لم يتم العثور على العضو المحدد.", ephemeral=True)

        await interaction.channel.set_permissions(target_member, view_channel=True, send_messages=True, attach_files=True, embed_links=True, read_message_history=True)

        embed = EmbedBuilder.create_embed(
            title="➕ تم إضافة عضو",
            description=get_text("user_added", self.lang, user=target_member.mention),
            color=EmbedBuilder.COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed)

        await TicketLogger.log_action(
            guild=interaction.guild,
            ticket=self.ticket,
            action_name="إضافة عضو",
            executor=interaction.user,
            details=f"العضو المضاف: {target_member.display_name} ({target_member.id})"
        )

class RemoveMemberModal(Modal):
    def __init__(self, ticket: dict, lang: str = "ar"):
        super().__init__(title="➖ إزالة عضو من التذكرة")
        self.ticket = ticket
        self.lang = lang

        self.member_input = TextInput(
            label="معرف العضو المراد إزالته أو المنشن",
            placeholder="مثال: 123456789012345678",
            required=True,
            max_length=100
        )
        self.add_item(self.member_input)

    async def on_submit(self, interaction: discord.Interaction):
        val = self.member_input.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        try:
            target_id = int(val)
            target_member = interaction.guild.get_member(target_id)
        except ValueError:
            target_member = None

        if not target_member:
            return await interaction.response.send_message("❌ لم يتم العثور على العضو المحدد.", ephemeral=True)

        await interaction.channel.set_permissions(target_member, overwrite=None)

        embed = EmbedBuilder.create_embed(
            title="➖ تم إزالة عضو",
            description=get_text("user_removed", self.lang, user=target_member.mention),
            color=EmbedBuilder.COLOR_WARNING
        )
        await interaction.response.send_message(embed=embed)

        await TicketLogger.log_action(
            guild=interaction.guild,
            ticket=self.ticket,
            action_name="إزالة عضو",
            executor=interaction.user,
            details=f"العضو المزال: {target_member.display_name} ({target_member.id})"
        )

class InternalNoteModal(Modal):
    def __init__(self, ticket: dict, lang: str = "ar"):
        super().__init__(title="📝 إضافة ملاحظة داخلية (للإدارة)")
        self.ticket = ticket
        self.lang = lang

        self.note_input = TextInput(
            label="الملاحظة الداخلية (خاصة بالإدارة)",
            placeholder="اكتب ملاحظة طاقم الدعم الفني هنا...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )
        self.add_item(self.note_input)

    async def on_submit(self, interaction: discord.Interaction):
        db.add_internal_note(
            ticket_id=self.ticket.get("id", 0),
            author_id=interaction.user.id,
            content=self.note_input.value
        )

        await interaction.response.send_message(get_text("note_added", self.lang), ephemeral=True)

        await TicketLogger.log_action(
            guild=interaction.guild,
            ticket=self.ticket,
            action_name="إضافة ملاحظة داخلية",
            executor=interaction.user,
            details=f"محتوى الملاحظة: {self.note_input.value[:100]}..."
        )

class RatingModal(Modal):
    def __init__(self, ticket: dict, staff_id: int, lang: str = "ar"):
        super().__init__(title="⭐ تقييم خدمة الدعم الفني")
        self.ticket = ticket
        self.staff_id = staff_id
        self.lang = lang

        self.stars_input = TextInput(
            label="التقييم بالنجوم (من 1 إلى 5)",
            placeholder="5",
            required=True,
            max_length=1
        )
        self.feedback_input = TextInput(
            label="ملاحظات أو تعليقك (اختياري)",
            placeholder="اكتب انطباعك عن الخدمة...",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        self.add_item(self.stars_input)
        self.add_item(self.feedback_input)

    async def on_submit(self, interaction: discord.Interaction):
        ticket_id = self.ticket.get("id", 0)
        if db.has_ticket_been_rated(ticket_id):
            return await interaction.response.send_message("❌ لقد قمت بتقييم هذه التذكرة بالفعل!", ephemeral=True)

        try:
            num_stars = int(self.stars_input.value.strip())
            num_stars = max(1, min(5, num_stars))
        except ValueError:
            num_stars = 5

        # 1. Add to database
        db.add_rating(
            ticket_id=self.ticket.get("id", 0),
            user_id=interaction.user.id,
            staff_id=self.staff_id,
            stars=num_stars,
            feedback=self.feedback_input.value.strip() or None
        )

        # 2. Update staff stats and award bonus points if applicable
        if interaction.guild:
            # Award Points based on rating multiplier
            base_points = self.ticket.get("category_points", 0)
            if base_points > 0:
                # Bonus points based on stars (3 stars = neutral, 4 = bonus, 5 = double bonus?)
                # Actually following RatingView logic: base_points * (stars - 1)
                bonus_points = base_points * (num_stars - 1)
                if bonus_points != 0:
                    db.update_staff_points(interaction.guild.id, self.staff_id, bonus_points)
            
            # Update staff stats (stars/ratings count)
            db.add_staff_rating_stat(interaction.guild.id, self.staff_id, num_stars)

        embed = EmbedBuilder.create_embed(
            title="⭐ شكراً لتقييمك",
            description=get_text("rating_thanks", self.lang),
            color=EmbedBuilder.COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        await TicketLogger.log_action(
            guild=interaction.guild,
            ticket=self.ticket,
            action_name="تقييم الخدمة",
            executor=interaction.user,
            details=f"التقييم: {num_stars}/5 ★ | التعليق: {self.feedback_input.value or 'لا يوجد'}"
        )

class AddEvidenceModal(Modal):
    def __init__(self, ticket: dict, lang: str = "ar"):
        super().__init__(title="📸 إضافة دليل للتذكرة")
        self.ticket = ticket
        self.lang = lang

        self.url_input = TextInput(
            label="رابط الصورة أو الدليل (Image / Evidence URL)",
            placeholder="https://cdn.discordapp.com/attachments/.../image.png",
            required=True,
            max_length=500
        )
        self.note_input = TextInput(
            label="توضيح أو وصف للدليل (اختياري)",
            placeholder="اكتب توضيحاً مختصراً للشاشة أو المستند...",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        self.add_item(self.url_input)
        self.add_item(self.note_input)

    async def on_submit(self, interaction: discord.Interaction):
        url = self.url_input.value.strip()
        note = self.note_input.value.strip()

        if not (url.startswith("http://") or url.startswith("https://")):
            return await interaction.response.send_message("❌ يرجى إدخال رابط صحيح يبدأ بـ http:// أو https://", ephemeral=True)

        if not db.is_evidence_enabled(interaction.channel_id):
            return await interaction.response.send_message("⚠️ ميزة إضافة الأدلة معطلة لهذه التذكرة حالياً من قبل الإدارة.", ephemeral=True)

        ticket_id = self.ticket.get("id", 0)
        db.add_evidence(
            ticket_id=ticket_id,
            channel_id=interaction.channel_id,
            user_id=interaction.user.id,
            evidence_url=url,
            note=note
        )

        embed = EmbedBuilder.create_embed(
            title="📸 تم تسجيل الدليل بنجاح",
            description=f"تم إدراج الدليل الجديد في أرشيف التذكرة بواسطة {interaction.user.mention}.",
            color=EmbedBuilder.COLOR_SUCCESS
        )
        if note:
            embed.add_field(name="📝 التوضيح:", value=note, inline=False)
        embed.set_image(url=url)
        embed.set_footer(text=f"المُضيف: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None)

        await interaction.response.send_message(embed=embed)

        await TicketLogger.log_action(
            guild=interaction.guild,
            ticket=self.ticket,
            action_name="إضافة دليل",
            executor=interaction.user,
            details=f"رابط الدليل: {url} | ملاحظة: {note or 'بدون'}"
        )

