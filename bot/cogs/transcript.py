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
        await interaction.response.defer(ephemeral=True)
        ticket = db.get_ticket_by_channel(interaction.channel_id)
        await TranscriptGenerator.send_transcript(interaction.channel, ticket, interaction.guild, interaction)


async def setup(bot: commands.Bot):
    await bot.add_cog(TranscriptCog(bot))
