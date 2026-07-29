import discord
from discord.ui import View, Button, Modal, TextInput
from bot.database.db import db
from bot.config.locales import get_text

class FeedbackModal(Modal):
    def __init__(self, ticket_id: int, staff_id: int, stars: int, lang: str = "ar"):
        super().__init__(title="⭐ Add Optional Feedback / إضافة تعليق")
        self.ticket_id = ticket_id
        self.staff_id = staff_id
        self.stars = stars
        self.lang = lang

        self.comment = TextInput(
            label="Feedback Comment / التعليق",
            placeholder="How was your experience with support?",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        self.add_item(self.comment)

    async def on_submit(self, interaction: discord.Interaction):
        feedback_text = self.comment.value or "No comment provided."
        db.add_rating(
            ticket_id=self.ticket_id,
            user_id=interaction.user.id,
            staff_id=self.staff_id,
            stars=self.stars,
            feedback=feedback_text
        )

        # Award Points based on rating multiplier
        ticket = db.get_ticket_by_id(self.ticket_id)
        if ticket and interaction.guild:
            base_points = ticket.get("category_points", 0)
            
            if base_points > 0:
                # Multiplier logic: (Base * Stars)
                # Since they already got 'Base' on claim, we add 'Base * (Stars - 1)'
                bonus_points = base_points * (self.stars - 1)
                if bonus_points != 0:
                    db.update_staff_points(interaction.guild.id, self.staff_id, bonus_points)
            
            # Update staff stats (stars/ratings)
            db.add_staff_rating_stat(interaction.guild.id, self.staff_id, self.stars)

        await interaction.response.send_message(get_text("rating_thanks", self.lang), ephemeral=True)

class RatingView(View):
    def __init__(self, ticket_id: int, staff_id: int, lang: str = "ar"):
        super().__init__(timeout=300)
        self.ticket_id = ticket_id
        self.staff_id = staff_id
        self.lang = lang

        for star in range(1, 6):
            btn = Button(
                label=f"{star} ⭐",
                style=discord.ButtonStyle.secondary if star < 4 else discord.ButtonStyle.success,
                custom_id=f"rate_{star}_{ticket_id}"
            )
            btn.callback = self.make_callback(star)
            self.add_item(btn)

    def make_callback(self, stars: int):
        async def callback(interaction: discord.Interaction):
            modal = FeedbackModal(ticket_id=self.ticket_id, staff_id=self.staff_id, stars=stars, lang=self.lang)
            await interaction.response.send_modal(modal)
        return callback
