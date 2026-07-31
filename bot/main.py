import asyncio
import os
import sys
import logging
from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands
from bot.config.settings import Config
from bot.database.db import db
from bot.utils.permissions import PermissionHandler
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("TicketBot")

COGS = [
    "bot.cogs.tickets",
    "bot.cogs.management",
    "bot.cogs.stats",
    "bot.cogs.admin",
    "bot.cogs.transcript",
    "bot.cogs.control_panel",
    "bot.cogs.setup_wizard",
    "bot.cogs.help",
    "bot.cogs.points"
]

class TicketBot(commands.Bot):
    def __init__(self, intents: Optional[discord.Intents] = None, **kwargs):
        if intents is None:
            intents = discord.Intents.default()
            intents.message_content = True
            intents.members = True
        kwargs.setdefault("command_prefix", "$")
        kwargs.setdefault("help_command", None)
        super().__init__(intents=intents, **kwargs)

    async def setup_hook(self):
        self.tree.on_error = self.on_tree_error

        for cog in COGS:
            try:
                await self.load_extension(cog)
                logger.info(f"📦 Loaded extension: {cog}")
            except Exception as e:
                logger.error(f"❌ Failed to load extension {cog}: {e}", exc_info=True)

        # Start inactivity check task
        self.loop.create_task(self.check_inactivity())

        # Register persistent views
        try:
            from bot.views.ticket_controls import TicketControlView
            from bot.views.control_panel_view import MasterControlPanelView
            from bot.views.setup_wizard_views import InAppSettingsDashboardView
            from bot.views.panel_view import PanelView

            self.add_view(TicketControlView(lang="ar"))
            self.add_view(MasterControlPanelView(self))
            self.add_view(InAppSettingsDashboardView(self))

            panels = db.get_panels() or []
            for p in panels:
                self.add_view(PanelView(categories=p.get("categories", []), panel_id=p["id"]))
            logger.info(f"✅ Registered persistent views ({len(panels)} ticket panel views initialized).")
        except Exception as e:
            logger.error(f"⚠️ Error registering persistent views: {e}", exc_info=True)

    async def check_inactivity(self):
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                tickets = db.get_all_tickets()
                now = datetime.utcnow()
                for t in tickets:
                    if t["status"] == "open" and t.get("last_staff_message_at") and not t.get("member_responded"):
                        last_reply = datetime.fromisoformat(t["last_staff_message_at"])
                        diff = (now - last_reply).total_seconds()
                        if diff >= 3600: # 1 hour
                            channel = self.get_channel(t["channel_id"])
                            if channel:
                                embed = EmbedBuilder.create_embed(
                                    title="⏲️ تنبيه عدم الرد",
                                    description="مرحباً، لقد قامت الإدارة بالرد على تذكرتك منذ فترة ولم نتلقَ أي رد منك.\nيرجى الرد لتجنب إغلاق التذكرة آلياً.",
                                    color=EmbedBuilder.COLOR_WARNING
                                )
                                await channel.send(embed=embed)
                                db.set_member_responded(t["channel_id"]) # Mark as reminded
            except Exception as e:
                logger.error(f"Error in inactivity check: {e}")
            await asyncio.sleep(600) # Check every 10 minutes

    async def on_tree_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        cmd_name = interaction.command.name if interaction.command else "Unknown"
        logger.error(f"❌ Exception in Slash Command '{cmd_name}': {error}", exc_info=error)
        
        msg = f"❌ حدث خطأ أثناء تنفيذ الأمر `{cmd_name}`:\n```{str(error)[:1000]}```"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception as send_err:
            logger.error(f"Failed to send error message to user: {send_err}")

    async def on_interaction(self, interaction: discord.Interaction):
        try:
            custom_id = interaction.data.get("custom_id") if (interaction.data and isinstance(interaction.data, dict) and "custom_id" in interaction.data) else None
            if custom_id and str(custom_id).startswith("panel_select_"):
                try:
                    panel_id = int(str(custom_id).split("_")[-1])
                    panel = db.get_panel_by_id(panel_id)
                    if not panel:
                        msg = (
                            f"⚠️ **لم يتم العثور على لوحة التذاكر رقم {panel_id} في قاعدة البيانات.**\n\n"
                            f"يرجى إعادة حفظ أو نشر هذه اللوحة من خلال لوحة التحكم لتحديث بياناتها وتفعيل أزرارها."
                        )
                        if not interaction.response.is_done():
                            await interaction.response.send_message(msg, ephemeral=True)
                        return
                except Exception as e:
                    logger.error(f"Error handling dynamic panel interaction: {e}")

        except Exception as err:
            logger.error(f"❌ Critical Uncaught Exception in Interaction: {err}", exc_info=err)
            try:
                msg = f"❌ حدث خطأ غير متوقع أثناء معالجة الطلب:\n```{str(err)[:500]}```"
                if interaction.response.is_done():
                    await interaction.followup.send(msg, ephemeral=True)
                else:
                    await interaction.response.send_message(msg, ephemeral=True)
            except Exception as send_err:
                logger.error(f"Failed to respond to failed interaction: {send_err}")

    async def on_ready(self):
        logger.info(f"⚡ Bot logged in successfully as: {self.user.name} ({self.user.id})")
        try:
            synced = await self.tree.sync()
            logger.info(f"✅ Synced {len(synced)} Slash Command(s) globally.")
        except Exception as e:
            logger.error(f"❌ Failed to sync slash commands: {e}")

        # Sync bot profile avatar with server icon if available
        for guild in self.guilds:
            if guild and guild.icon:
                try:
                    icon_bytes = await guild.icon.read()
                    await self.user.edit(avatar=icon_bytes)
                    logger.info(f"🖼️ Bot avatar updated to match server icon of '{guild.name}'.")
                    break
                except Exception as av_err:
                    logger.debug(f"Could not update bot avatar from guild {guild.id}: {av_err}")

        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="Tickets | /setup_panel")
        )

    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        ticket = db.get_ticket_by_channel(message.channel.id)
        if ticket:
            user_id = ticket["user_id"]
            claimed_by = ticket.get("claimed_by")
            status = ticket.get("status", "open")
            
            is_staff = PermissionHandler.is_staff(message.author)
            is_owner = (message.author.id == user_id)
            
            # 1. Staff Writing Restrictions
            if is_staff and not is_owner:
                # Bypass check for bot owner, guild owner, or administrators
                is_admin_bypass = (
                    PermissionHandler.is_bot_owner(message.author.id) or 
                    message.author.id == message.guild.owner_id or 
                    message.author.guild_permissions.administrator
                )
                
                if not is_admin_bypass:
                    # Check if they are the claimant
                    is_claimant = (claimed_by and message.author.id == claimed_by)
                    
                    # Check if they were explicitly added via add_member (has user-specific overwrite allowing send_messages)
                    is_added_member = False
                    overwrites = message.channel.overwrites
                    if message.author in overwrites:
                        ov = overwrites[message.author]
                        if ov.send_messages is True:
                            is_added_member = True

                    if not is_claimant and not is_added_member:
                        # If not claimed at all
                        if not claimed_by:
                            try:
                                await message.delete()
                                return await message.channel.send(f"⚠️ {message.author.mention}، لا يمكنك الكتابة في التذكرة قبل استلامها.", delete_after=5)
                            except: pass
                        
                        # If claimed by someone else
                        else:
                            # Check rank for secondary bypass (Support Manager+)
                            rank = PermissionHandler.get_member_rank(message.author)
                            if rank < PermissionHandler.ROLE_HIERARCHY["support_manager"]:
                                try:
                                    await message.delete()
                                    return await message.channel.send(f"⚠️ {message.author.mention}، التذكرة مستلمة من قبل <@{claimed_by}>، هو الوحيد المخول بالكتابة حالياً.", delete_after=5)
                                except: pass

                # Tracking last staff message
                db.update_staff_reply(message.channel.id, datetime.utcnow().isoformat())
                if not ticket.get("first_response_at"):
                    db.set_first_response(message.channel.id)
            
            # 2. Owner Writing Restrictions
            elif message.author.id == user_id:
                if status in ["on_hold", "locked", "closed"]:
                    try:
                        await message.delete()
                        msg_text = "التذكرة في حالة انتظار حالياً، لا يمكنك الكتابة." if status == "on_hold" else "التذكرة مقفلة أو مغلقة حالياً."
                        return await message.channel.send(f"⚠️ {message.author.mention}، {msg_text}", delete_after=5)
                    except: pass
                
                # Tracking member response
                db.set_member_responded(message.channel.id)

            # 3. Evidence Collection (Automatic)
            if message.attachments and db.is_evidence_enabled(message.channel.id):
                saved_count = 0
                for attachment in message.attachments:
                    if any(attachment.filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]):
                        db.add_evidence(
                            ticket_id=ticket.get("id", 0),
                            channel_id=message.channel.id,
                            user_id=message.author.id,
                            evidence_url=attachment.url,
                            note=f"دليل تلقائي: {attachment.filename}"
                        )
                        saved_count += 1
                
                if saved_count > 0:
                    try:
                        await message.add_reaction("📸")
                    except:
                        pass

        await self.process_commands(message)

async def main():
    token = Config.BOT_TOKEN
    if not token or token.startswith("YOUR_") or token == "MY_GEMINI_API_KEY" or len(token) < 10:
        logger.error("❌ [DISCORD_BOT_TOKEN مفقود] يرجى تعيين متغير البيئة DISCORD_BOT_TOKEN في Railway.")
        sys.exit(1)

    # Attempt standard intents (Message Content + Members + Guilds)
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True

    bot = TicketBot(intents=intents)

    try:
        async with bot:
            await bot.start(token)
    except discord.errors.PrivilegedIntentsRequired:
        logger.warning("⚠️ Privileged Intents (Message Content / Members) are disabled in Discord Developer Portal.")
        logger.warning("🔄 Switching to standard fallback intents without privileged flags...")
        
        intents_fallback = discord.Intents.default()
        intents_fallback.guilds = True
        intents_fallback.message_content = False
        intents_fallback.members = False

        bot_fallback = TicketBot(intents=intents_fallback)
        async with bot_fallback:
            await bot_fallback.start(token)
    except discord.errors.LoginFailure:
        logger.error("❌ [التوكن غير صحيح / Invalid Token] التوكن المستعمل غير صالح أو تم إعادة تعيينه من Discord Developer Portal.")
        logger.error("👉 يرجى نسخ توكن جديد من (Discord Developer Portal -> Bot -> Reset Token) ولصقه في الإعدادات.")
    except Exception as e:
        logger.error(f"❌ Unexpected error starting bot: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped manually.")
