import discord
from discord.ui import View, Button, Select, Modal, TextInput
from bot.database.db import db
from bot.utils.embeds import EmbedBuilder
from datetime import datetime

class StaffClosureModal(Modal):
    def __init__(self, ticket_id: int, on_complete):
        super().__init__(title="📝 تفاصيل إغلاق التذكرة (للموظف)")
        self.ticket_id = ticket_id
        self.on_complete = on_complete

        self.evidence = TextInput(
            label="رابط الأدلة (صور/فيديو)",
            placeholder="انسخ رابط الصورة هنا أو اكتب تفاصيل...",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.details = TextInput(
            label="تفاصيل إضافية",
            placeholder="اكتب أي ملاحظات أخرى هنا...",
            style=discord.TextStyle.paragraph,
            required=False
        )
        self.add_item(self.evidence)
        self.add_item(self.details)

    async def on_submit(self, interaction: discord.Interaction):
        # We'll handle the punishment type in the view since it's a select
        await self.on_complete(interaction, self.evidence.value, self.details.value)

class ClosureWorkflowView(View):
    def __init__(self, ticket_id: int, original_action: str, lang: str = "ar"):
        super().__init__(timeout=600)
        self.ticket_id = ticket_id
        self.original_action = original_action # 'close' or 'delete'
        self.lang = lang
        
        self.user_answered = False
        self.staff_answered = False
        
        self.user_handled = 0
        self.staff_punished = 0
        self.evidence_urls = ""
        self.punishment_type = ""
        self.staff_details = ""

        # Staff controls will be added after user answers or if staff initiates
        self.add_user_buttons()

    def add_user_buttons(self):
        btn_yes = Button(label="نعم، تم التعامل", style=discord.ButtonStyle.success, custom_id="user_yes")
        btn_no = Button(label="لا، لم يتم التعامل", style=discord.ButtonStyle.danger, custom_id="user_no")
        
        btn_yes.callback = self.user_yes_callback
        btn_no.callback = self.user_no_callback
        
        self.add_item(btn_yes)
        self.add_item(btn_no)

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

    def add_staff_controls(self):
        self.clear_items()
        
        # Punishment Select
        select = Select(
            placeholder="اختر نوع العقوبة المتخذة...",
            options=[
                discord.SelectOption(label="تايم أوت (Time-out)", value="timeout"),
                discord.SelectOption(label="تحذير رسمي (Official Warning)", value="official_warning"),
                discord.SelectOption(label="تم حلها ودي (Resolved Friendly)", value="friendly"),
                discord.SelectOption(label="تحذير شفهي (Verbal Warning)", value="verbal_warning"),
                discord.SelectOption(label="لا يوجد عقوبة (No Punishment)", value="none")
            ]
        )
        select.callback = self.staff_select_callback
        self.add_item(select)
        
        btn_modal = Button(label="إضافة الأدلة والتفاصيل", style=discord.ButtonStyle.primary)
        btn_modal.callback = self.staff_modal_trigger
        self.add_item(btn_modal)

    async def staff_select_callback(self, interaction: discord.Interaction):
        ticket = db.get_ticket_by_id(self.ticket_id)
        if interaction.user.id != ticket.get("claimed_by"):
            return await interaction.response.send_message("❌ هذا الإجراء مخصص للموظف المستلم فقط.", ephemeral=True)
        
        self.punishment_type = interaction.data["values"][0]
        self.staff_punished = 1 if self.punishment_type not in ["none", "friendly"] else 0
        await interaction.response.send_message(f"✅ تم تحديد العقوبة: {self.punishment_type}", ephemeral=True)

    async def staff_modal_trigger(self, interaction: discord.Interaction):
        ticket = db.get_ticket_by_id(self.ticket_id)
        if interaction.user.id != ticket.get("claimed_by"):
            return await interaction.response.send_message("❌ هذا الإجراء مخصص للموظف المستلم فقط.", ephemeral=True)
        
        await interaction.response.send_modal(StaffClosureModal(self.ticket_id, self.staff_modal_complete))

    async def staff_modal_complete(self, interaction, evidence, details):
        self.evidence_urls = evidence
        self.staff_details = details
        self.staff_answered = True
        await self.update_workflow(interaction)

    async def update_workflow(self, interaction: discord.Interaction):
        if self.user_answered and not self.staff_answered:
            self.add_staff_controls()
            embed = interaction.message.embeds[0]
            embed.description = "✅ أجاب العضو.\n⏳ الآن يرجى من الموظف المستلم تعبئة بيانات الإغلاق (العقوبة والأدلة)."
            await interaction.response.edit_message(embed=embed, view=self)
        
        elif self.staff_answered and self.user_answered:
            # Save to DB
            db.save_closure_info(
                ticket_id=self.ticket_id,
                user_handled=self.user_handled,
                staff_punished=self.staff_punished,
                evidence_urls=self.evidence_urls,
                punishment_type=self.punishment_type,
                staff_details=self.staff_details
            )
            
            embed = interaction.message.embeds[0]
            embed.description = "✅ اكتملت جميع البيانات. جاري تنفيذ الإجراء المطلوب..."
            embed.color = discord.Color.green()
            await interaction.response.edit_message(embed=embed, view=None)
            
            # Execute original action
            from bot.views.ticket_controls import TicketControlsView
            # We need a way to trigger the actual close/delete now.
            # Usually we'd call the method in TicketControlsView
            if self.original_action == "close":
                # Trigger close logic
                pass 
            elif self.original_action == "delete":
                # Trigger delete logic
                pass
            
            # To avoid circular imports and complexity, we might want to pass a callback
            if hasattr(self, 'final_callback'):
                await self.final_callback()
