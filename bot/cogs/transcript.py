import discord
from discord.ext import commands
from discord import app_commands
import os
from bot.database.db import db
from bot.utils.transcript_generator import TranscriptGenerator

class TranscriptCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="transcript", description="Generate HTML Transcript of channel / تصدير المحادثة كملف HTML")
    async def transcript(self, interaction: discord.Interaction):
        await self._generate_transcript(interaction)

    @app_commands.command(name="script", description="Generate HTML Transcript (alias) / تصدير المحادثة")
    async def script(self, interaction: discord.Interaction):
        await self._generate_transcript(interaction)

    async def _generate_transcript(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        ticket = db.get_ticket_by_channel(interaction.channel_id)
        html_content = await TranscriptGenerator.generate_html(interaction.channel, ticket)

        file_name = f"transcript-{interaction.channel.name}.html"
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(html_content)

        file = discord.File(file_name, filename=file_name)
        await interaction.followup.send("📄 **Ticket Transcript Generated:**", file=file)

        if os.path.exists(file_name):
            os.remove(file_name)

async def setup(bot: commands.Bot):
    await bot.add_cog(TranscriptCog(bot))
