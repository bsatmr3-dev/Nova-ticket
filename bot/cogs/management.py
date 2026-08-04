import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from bot.database.db import db
from bot.utils.permissions import PermissionHandler
from bot.utils.embeds import EmbedBuilder
from bot.utils.transcript_generator import TranscriptGenerator
from bot.views.modal_views import InternalNoteModal, RenameTicketModal

class TicketManagementCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def check_ticket_state(self, interaction: discord.Interaction, ticket: dict, action: str) -> bool:
        """
        Checks state and permissions. Sends error if unauthorized, and returns False.
        """
        member = interaction.user
        guild = interaction.guild
        ticket_user_id = ticket.get("user_id")
        claimed_by = ticket.get("claimed_by")

        # 1. Master owner and admin override
        if PermissionHandler.is_bot_owner(member.id):
            return True
        if guild and (member.id == guild.owner_id or member.guild_permissions.administrator):
            return True

        # 2. Check general command permissions using the permission handler
        if not PermissionHandler.can_execute_action(guild, member, action, ticket_user_id, ticket_data=ticket):
            await interaction.response.send_message("❌ ليس لديك صلاحية لاستخدام هذا الأمر.", ephemeral=True)
            return False

        # 3. Check claim state for administrative actions
        staff_actions = [
            "unclaim", "transfer", "toggle_hide", "department", "priority",
            "lock", "unlock", "hold", "resume", "note", "delete_ticket",
            "add_member", "remove_member", "rename", "summon_member",
            "hide", "show"
        ]
        
        if action in staff_actions:
            if not PermissionHandler.is_staff(member) and not PermissionHandler.is_bot_owner(member.id):
                await interaction.response.send_message("❌ هذا الأمر مخصص فقط لإدارة وطاقم الدعم الفني.", ephemeral=True)
                return False

            if not claimed_by and action not in ["close", "hide", "show"]:
                user_rank = PermissionHandler.get_member_rank(member)
                if user_rank < PermissionHandler.ROLE_HIERARCHY["admin"] and not PermissionHandler.is_bot_owner(member.id):
                    await interaction.response.send_message("⚠️ يجب استلام التذكرة أولاً لتتمكن من استخدام أوامر الإدارة عليها!", ephemeral=True)
                    return False

            if claimed_by and member.id != claimed_by:
                user_rank = PermissionHandler.get_member_rank(member)
                if user_rank < PermissionHandler.ROLE_HIERARCHY["admin"] and not PermissionHandler.is_bot_owner(member.id):
                    await interaction.response.send_message("❌ هذه التذكرة مستلمة من قبل موظف آخر، ولا يمكنك إدارتها إلا إذا كنت مسؤولاً.", ephemeral=True)
                    return False

        return True

    @app_commands.command(name="claim", description="Claim current ticket / استلام التذكرة")
    async def claim(self, interaction: discord.Interaction):
        if not PermissionHandler.is_staff(interaction.user):
            return await interaction.response.send_message("❌ غير مسموح لك باستخدام هذا الأمر.", ephemeral=True)

        ticket = db.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            return await interaction.response.send_message("❌ هذا ليس بقناة تذكرة صالحة.", ephemeral=True)

        if ticket.get("claimed_by"):
            return await interaction.response.send_message("⚠️ هذه التذكرة مستلمة بالفعل!", ephemeral=True)

        await interaction.response.defer()
        
        db.claim_ticket(interaction.channel_id, interaction.user.id)
        db.increment_staff_tickets(interaction.guild_id, interaction.user.id)
        
        # Award category points on claim
        category_points = ticket.get("category_points", 0)
        if category_points > 0:
            db.update_staff_points(interaction.guild_id, interaction.user.id, category_points)
        
        # Update permissions
        guild = interaction.guild
        settings = db.get_guild_settings(guild.id) or {}
        staff_roles = [settings.get("support_role_id"), settings.get("senior_support_role_id"), settings.get("admin_role_id"), settings.get("support_manager_role_id"), settings.get("owner_role_id")]
        
        overwrites = interaction.channel.overwrites
        for role_id in staff_roles:
            if role_id:
                role = guild.get_role(int(role_id))
                if role: overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=False)
        
        overwrites[interaction.user] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True, manage_messages=True)
        
        await interaction.channel.edit(overwrites=overwrites)
        await interaction.followup.send(embed=EmbedBuilder.create_embed(title="📌 تم استلام التذكرة", description=f"تم استلام التذكرة بواسطة {interaction.user.mention}.", color=EmbedBuilder.COLOR_SUCCESS))

    @app_commands.command(name="unclaim", description="Unclaim current ticket / إلغاء استلام التذكرة")
    async def unclaim(self, interaction: discord.Interaction):
        ticket = db.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            return await interaction.response.send_message("❌ هذا ليس بقناة تذكرة صالحة.", ephemeral=True)

        if not await self.check_ticket_state(interaction, ticket, "unclaim"):
            return

        claimed_id = ticket.get("claimed_by")
        await interaction.response.defer()
        
        db.claim_ticket(interaction.channel_id, None)
        
        # Update permissions
        guild = interaction.guild
        settings = db.get_guild_settings(guild.id) or {}
        staff_roles = [settings.get("support_role_id"), settings.get("senior_support_role_id"), settings.get("admin_role_id"), settings.get("support_manager_role_id"), settings.get("owner_role_id")]
        
        overwrites = interaction.channel.overwrites
        for role_id in staff_roles:
            if role_id:
                role = guild.get_role(int(role_id))
                if role: overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=False)
        
        claimant = guild.get_member(claimed_id)
        if claimant and claimant in overwrites:
            del overwrites[claimant]
        
        await interaction.channel.edit(overwrites=overwrites)
        await interaction.followup.send(embed=EmbedBuilder.create_embed(title="🔓 تم إلغاء الاستلام", description="تم إلغاء استلام التذكرة وعادت متاحة للطاقم.", color=EmbedBuilder.COLOR_WARNING))

    @app_commands.command(name="close", description="إغلاق التذكرة / Close ticket")
    async def close(self, interaction: discord.Interaction):
        ticket = db.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            return await interaction.response.send_message("❌ هذه القناة ليست قناة تذكرة صالحة.", ephemeral=True)

        if not await self.check_ticket_state(interaction, ticket, "close"):
            return

        # Check for closure workflow bypass (Bot Owners only)
        if not PermissionHandler.is_bot_owner(interaction.user.id):
            closure_info = db.get_closure_info(ticket.get("id", 0))
            if not closure_info:
                from bot.views.closure_workflow import ClosureWorkflowView
                workflow_view = ClosureWorkflowView(ticket.get("id"), "close")
                
                async def final_callback():
                    # This is tricky because we need to trigger the logic again
                    # But slash commands can't really be re-triggered easily
                    # We can just call the close logic directly here if we had it extracted
                    # For now, let's just use the view's embed
                    pass

                workflow_view.final_callback = final_callback
                
                embed = EmbedBuilder.create_embed(
                    title="⚠️ متطلبات إغلاق التذكرة",
                    description=(
                        "يرجى استكمال بيانات الإغلاق أولاً عبر الأزرار في القائمة.\n"
                        "يجب على صاحب التذكرة والموظف الإجابة على الأسئلة المطلوبة."
                    ),
                    color=EmbedBuilder.COLOR_WARNING
                )
                return await interaction.response.send_message(embed=embed, view=workflow_view)

        guild = interaction.guild
        member = interaction.user
        ticket_user_id = ticket.get("user_id")

        db.update_ticket_status(interaction.channel_id, "closed")

        owner = guild.get_member(ticket_user_id) if ticket_user_id else None
        if not owner and ticket_user_id:
            try:
                owner = await guild.fetch_member(ticket_user_id)
            except Exception:
                try:
                    owner = await self.bot.fetch_user(ticket_user_id)
                except Exception:
                    owner = None

        if owner and isinstance(owner, discord.Member):
            await interaction.channel.set_permissions(owner, view_channel=True, send_messages=False)

        await interaction.response.send_message(embed=EmbedBuilder.create_embed(title="🔒 تم إغلاق التذكرة", description=f"أغلقت التذكرة بواسطة {member.mention}.", color=EmbedBuilder.COLOR_DANGER))
        await TicketLogger.log_action(guild, ticket, "إغلاق التذكرة", member)

        try:
            await TranscriptGenerator.send_transcript(interaction.channel, ticket, guild)
        except Exception as e:
            print(f"Error sending transcript on close_ticket: {e}")

        # Send rating DM to owner if ticket was claimed and not previously rated
        staff_id = ticket.get("claimed_by")
        if owner and ticket_user_id and staff_id and not db.has_ticket_been_rated(ticket.get("id", 0)):
            from bot.views.rating_view import RatingView
            try:
                staff_member = guild.get_member(staff_id)
                if not staff_member:
                    try:
                        staff_member = await guild.fetch_member(staff_id)
                    except Exception:
                        staff_member = None
                staff_mention = staff_member.mention if staff_member else f"<@{staff_id}>"

                settings = db.get_guild_settings(guild.id) or {}
                lang = settings.get("language", "ar")

                rating_embed = EmbedBuilder.create_embed(
                    title="📋 استبيان وتحديد تقييم خدمة الدعم الفني",
                    description=(
                        f"مرحباً <@{ticket_user_id}> 👋،\n"
                        f"تم إغلاق تذكرتك بنجاح في سيرفر **{guild.name}**.\n\n"
                        f"📊 **تفاصيل استبيان التذكرة المغلقة:**\n"
                        f"• **رقم التذكرة:** `#{ticket.get('id')}`\n"
                        f"• **المسؤول / مستلم التذكرة:** {staff_mention}\n"
                        f"• **الحالة:** تم الإنهاء والإغلاق ✅\n\n"
                        f"⭐ **استبيان الرضا وتقييم الخدمة:**\n"
                        f"يرجى تقييم أداء الموظف وجودة الخدمة التي تلقيتها بالضغط على الأزرار أدناه (1 إلى 5 نجوم):"
                    ),
                    color=EmbedBuilder.COLOR_PRIMARY
                )
                await owner.send(embed=rating_embed, view=RatingView(ticket['id'], staff_id, lang))
            except Exception as e:
                print(f"Error sending rating DM: {e}")

    @app_commands.command(name="hide", description="إخفاء التذكرة عن رتب الإدارة (تصبح مرئية للمستلم وصاحبها فقط)")
    async def hide(self, interaction: discord.Interaction):
        ticket = db.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            return await interaction.response.send_message("❌ هذه القناة ليست قناة تذكرة صالحة.", ephemeral=True)

        if not await self.check_ticket_state(interaction, ticket, "toggle_hide"):
            return

        await PermissionHandler.set_ticket_visibility(interaction.channel, interaction.guild, ticket, is_hidden=True)
        await interaction.response.send_message("🔒 **تم إخفاء التذكرة عن رتب الإدارة بنجاح!** (مرئية الآن لصاحب التذكرة والمستلم فقط)", ephemeral=True)

    @app_commands.command(name="show", description="إظهار التذكرة لرتب الإدارة (رؤية فقط بدون صلاحية كتابة)")
    async def show(self, interaction: discord.Interaction):
        ticket = db.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            return await interaction.response.send_message("❌ هذه القناة ليست قناة تذكرة صالحة.", ephemeral=True)

        if not await self.check_ticket_state(interaction, ticket, "toggle_hide"):
            return

        await PermissionHandler.set_ticket_visibility(interaction.channel, interaction.guild, ticket, is_hidden=False)
        await interaction.response.send_message("👁️ **تم إظهار التذكرة لرتب الإدارة بنجاح!** (رؤية فقط بدون كتابة)", ephemeral=True)

    @app_commands.command(name="ticket_status", description="عرض معلومات مفصلة عن التذكرة / View detailed ticket info")
    async def ticket_status(self, interaction: discord.Interaction):
        ticket = db.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            return await interaction.response.send_message("❌ هذا ليس بقناة تذكرة صالحة.", ephemeral=True)

        guild = interaction.guild
        owner_id = ticket.get("user_id")
        claimed_id = ticket.get("claimed_by")
        
        owner_mention = f"<@{owner_id}>" if owner_id else "غير معروف"
        claimed_mention = f"<@{claimed_id}>" if claimed_id else "❌ غير مستلمة"
        
        embed = EmbedBuilder.create_embed(title=f"📊 حالة التذكرة #{ticket['id']}", color=EmbedBuilder.COLOR_INFO)
        embed.add_field(name="👤 صاحب التذكرة", value=owner_mention, inline=True)
        embed.add_field(name="📌 المستلم", value=claimed_mention, inline=True)
        embed.add_field(name="🔒 الحالة", value=f"**{ticket.get('status', 'open').upper()}**", inline=True)
        embed.add_field(name="👁️ الظهور", value="🙈 مخفية عن الطاقم" if ticket.get("is_hidden") else "👁️ مرئية للطاقم", inline=True)
        created_at = ticket.get("created_at")
        try:
            if isinstance(created_at, str) and "T" in created_at:
                from datetime import datetime
                ts = int(datetime.fromisoformat(created_at).timestamp())
            else:
                ts = int(float(created_at or 0))
        except: ts = 0

        embed.add_field(name="📅 أنشئت في", value=f"<t:{ts}:F>" if ts else "غير معروف", inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="lock", description="قفل التذكرة وإخفاؤها عن العضو / Lock ticket from owner")
    async def lock(self, interaction: discord.Interaction):
        ticket = db.get_ticket_by_channel(interaction.channel_id)
        if not ticket: return await interaction.response.send_message("❌ قناة غير صالحة.", ephemeral=True)

        if not await self.check_ticket_state(interaction, ticket, "lock"):
            return

        owner = interaction.guild.get_member(ticket["user_id"])
        if owner: await interaction.channel.set_permissions(owner, view_channel=False)
        db.update_ticket_status(interaction.channel_id, "locked")
        
        await interaction.response.send_message(embed=EmbedBuilder.create_embed(title="🔐 تم قفل التذكرة", description="تم إخفاء التذكرة عن صاحبها بنجاح.", color=EmbedBuilder.COLOR_DANGER))

    @app_commands.command(name="unlock", description="فتح التذكرة وإظهارها للعضو / Unlock ticket for owner")
    async def unlock(self, interaction: discord.Interaction):
        ticket = db.get_ticket_by_channel(interaction.channel_id)
        if not ticket: return await interaction.response.send_message("❌ قناة غير صالحة.", ephemeral=True)

        if not await self.check_ticket_state(interaction, ticket, "unlock"):
            return

        owner = interaction.guild.get_member(ticket["user_id"])
        if owner: await interaction.channel.set_permissions(owner, view_channel=True, send_messages=True)
        db.update_ticket_status(interaction.channel_id, "open")
        
        await interaction.response.send_message(embed=EmbedBuilder.create_embed(title="🔓 تم فتح التذكرة", description="تمت إعادة صلاحية الرؤية والكتابة لصاحب التذكرة.", color=EmbedBuilder.COLOR_SUCCESS))

    @app_commands.command(name="hold", description="تعليق التذكرة (رؤية فقط للعضو) / Put ticket on hold")
    async def hold(self, interaction: discord.Interaction):
        ticket = db.get_ticket_by_channel(interaction.channel_id)
        if not ticket: return await interaction.response.send_message("❌ قناة غير صالحة.", ephemeral=True)

        if not await self.check_ticket_state(interaction, ticket, "hold"):
            return

        ticket_user_id = ticket.get("user_id")
        owner = interaction.guild.get_member(ticket_user_id) if ticket_user_id else None
        if not owner and ticket_user_id:
            try: owner = await interaction.guild.fetch_member(ticket_user_id)
            except Exception: owner = None

        if owner:
            await interaction.channel.set_permissions(owner, view_channel=True, send_messages=False)
        db.update_ticket_status(interaction.channel_id, "on_hold")
        
        await interaction.response.send_message(embed=EmbedBuilder.create_embed(title="⏸️ تم تعليق التذكرة", description="صاحب التذكرة قادر على الرؤية فقط الآن.", color=EmbedBuilder.COLOR_WARNING))

    @app_commands.command(name="resume", description="استئناف التذكرة للعضو / Resume ticket")
    async def resume(self, interaction: discord.Interaction):
        ticket = db.get_ticket_by_channel(interaction.channel_id)
        if not ticket: return await interaction.response.send_message("❌ قناة غير صالحة.", ephemeral=True)

        if not await self.check_ticket_state(interaction, ticket, "resume"):
            return

        ticket_user_id = ticket.get("user_id")
        owner = interaction.guild.get_member(ticket_user_id) if ticket_user_id else None
        if not owner and ticket_user_id:
            try: owner = await interaction.guild.fetch_member(ticket_user_id)
            except Exception: owner = None

        if owner:
            await interaction.channel.set_permissions(owner, view_channel=True, send_messages=True)
        new_st = "claimed" if ticket.get("claimed_by") else "open"
        db.update_ticket_status(interaction.channel_id, new_st)
        
        await interaction.response.send_message(embed=EmbedBuilder.create_embed(title="▶️ استئناف التذكرة", description="تمت إعادة صلاحية الكتابة لصاحب التذكرة بنجاح.", color=EmbedBuilder.COLOR_SUCCESS))

    @app_commands.command(name="delete_ticket", description="Delete ticket channel / حذف القناة نهائياً")
    async def delete_ticket(self, interaction: discord.Interaction):
        ticket = db.get_ticket_by_channel(interaction.channel_id)
        if not ticket: return await interaction.response.send_message("❌ قناة غير صالحة.", ephemeral=True)

        if not await self.check_ticket_state(interaction, ticket, "delete"):
            return

        # Check for closure workflow bypass (Bot Owners only)
        if not PermissionHandler.is_bot_owner(interaction.user.id):
            closure_info = db.get_closure_info(ticket.get("id", 0))
            if not closure_info:
                from bot.views.closure_workflow import ClosureWorkflowView
                workflow_view = ClosureWorkflowView(ticket.get("id"), "delete")
                
                async def final_callback():
                    pass

                workflow_view.final_callback = final_callback
                
                embed = EmbedBuilder.create_embed(
                    title="⚠️ متطلبات حذف التذكرة",
                    description=(
                        "يرجى استكمال بيانات الإغلاق أولاً عبر الأزرار في القائمة.\n"
                        "يجب على صاحب التذكرة والموظف الإجابة على الأسئلة المطلوبة قبل الحذف."
                    ),
                    color=EmbedBuilder.COLOR_WARNING
                )
                return await interaction.response.send_message(embed=embed, view=workflow_view)

        guild = interaction.guild
        member = interaction.user
        ticket_user_id = ticket.get("user_id")

        await interaction.response.send_message("🗑️ جاري حذف التذكرة وإرسال طلب التقييم لصاحب التذكرة خلال 3 ثوانٍ...")

        try:
            await TranscriptGenerator.send_transcript(interaction.channel, ticket, guild)
        except Exception as e:
            print(f"Error sending transcript on delete_ticket: {e}")

        owner = guild.get_member(ticket_user_id) if ticket_user_id else None
        if not owner and ticket_user_id:
            try:
                owner = await guild.fetch_member(ticket_user_id)
            except Exception:
                try:
                    owner = await self.bot.fetch_user(ticket_user_id)
                except Exception:
                    owner = None

        staff_id = ticket.get("claimed_by")
        if owner and ticket_user_id and staff_id and not db.has_ticket_been_rated(ticket.get("id", 0)):
            from bot.views.rating_view import RatingView
            try:
                staff_member = guild.get_member(staff_id)
                if not staff_member:
                    try:
                        staff_member = await guild.fetch_member(staff_id)
                    except Exception:
                        staff_member = None
                staff_mention = staff_member.mention if staff_member else f"<@{staff_id}>"

                settings = db.get_guild_settings(guild.id) or {}
                lang = settings.get("language", "ar")

                rating_embed = EmbedBuilder.create_embed(
                    title="📋 استبيان وتحديد تقييم خدمة الدعم الفني",
                    description=(
                        f"مرحباً <@{ticket_user_id}> 👋،\n"
                        f"تم حذف تذكرتك في سيرفر **{guild.name}**.\n\n"
                        f"📊 **تفاصيل استبيان التذكرة المحذوفة:**\n"
                        f"• **رقم التذكرة:** `#{ticket.get('id')}`\n"
                        f"• **المسؤول / مستلم التذكرة:** {staff_mention}\n\n"
                        f"⭐ **استبيان الرضا وتقييم الخدمة:**\n"
                        f"يرجى تقييم أداء الموظف وجودة الخدمة التي تلقيتها بالضغط على الأزرار أدناه (1 إلى 5 نجوم):"
                    ),
                    color=EmbedBuilder.COLOR_PRIMARY
                )
                await owner.send(embed=rating_embed, view=RatingView(ticket['id'], staff_id, lang))
            except Exception as e:
                print(f"Error sending rating DM on delete_ticket: {e}")

        db.update_ticket_status(interaction.channel_id, "deleted")
        await TicketLogger.log_action(guild, ticket, "حذف التذكرة", member)
        await asyncio.sleep(3)
        await interaction.channel.delete(reason=f"Ticket deleted by {interaction.user.name}")

    @app_commands.command(name="reopen", description="Reopen a closed ticket / إعادة فتح التذكرة المغلقة")
    async def reopen(self, interaction: discord.Interaction):
        ticket = db.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            return await interaction.response.send_message("❌ هذه القناة ليست قناة تذكرة صالحة.", ephemeral=True)

        if not await self.check_ticket_state(interaction, ticket, "reopen"):
            return

        guild = interaction.guild
        member = interaction.user
        ticket_user_id = ticket.get("user_id")

        owner = guild.get_member(ticket_user_id) if ticket_user_id else None
        if not owner and ticket_user_id:
            try:
                owner = await guild.fetch_member(ticket_user_id)
            except Exception:
                try:
                    owner = await self.bot.fetch_user(ticket_user_id)
                except Exception:
                    owner = None

        if owner and isinstance(owner, discord.Member):
            await interaction.channel.set_permissions(
                owner,
                view_channel=True,
                send_messages=True,
                attach_files=True,
                embed_links=True,
                read_message_history=True
            )

        new_status = "claimed" if ticket.get("claimed_by") else "open"
        db.update_ticket_status(interaction.channel_id, new_status)

        embed = EmbedBuilder.create_embed(
            title="🔓 تم إعادة فتح التذكرة",
            description=f"تم إعادة فتح التذكرة بنجاح بواسطة {member.mention}.",
            color=EmbedBuilder.COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed)
        await TicketLogger.log_action(guild, ticket, "إعادة فتح التذكرة", member)

    @app_commands.command(name="add_member", description="Add user to ticket / إضافة عضو للتذكرة")
    async def add_member(self, interaction: discord.Interaction, member: discord.Member):
        ticket = db.get_ticket_by_channel(interaction.channel_id)
        if not ticket: return await interaction.response.send_message("❌ قناة غير صالحة.", ephemeral=True)

        if not await self.check_ticket_state(interaction, ticket, "add_member"):
            return

        await interaction.channel.set_permissions(member, view_channel=True, send_messages=True, attach_files=True, embed_links=True, read_message_history=True)
        await interaction.response.send_message(f"✅ Added {member.mention} to this ticket.")

    @app_commands.command(name="remove_member", description="Remove user from ticket / إزالة عضو")
    async def remove_member(self, interaction: discord.Interaction, member: discord.Member):
        ticket = db.get_ticket_by_channel(interaction.channel_id)
        if not ticket: return await interaction.response.send_message("❌ قناة غير صالحة.", ephemeral=True)

        if not await self.check_ticket_state(interaction, ticket, "remove_member"):
            return

        await interaction.channel.set_permissions(member, view_channel=False)
        await interaction.response.send_message(f"❌ Removed {member.mention} from this ticket.")

    @app_commands.command(name="priority", description="Set ticket priority / تغيير أولوية التذكرة")
    @app_commands.choices(priority=[
        app_commands.Choice(name="Low", value="Low"),
        app_commands.Choice(name="Medium", value="Medium"),
        app_commands.Choice(name="High", value="High"),
        app_commands.Choice(name="Urgent", value="Urgent")
    ])
    async def priority(self, interaction: discord.Interaction, priority: str):
        ticket = db.get_ticket_by_channel(interaction.channel_id)
        if not ticket: return await interaction.response.send_message("❌ قناة غير صالحة.", ephemeral=True)

        if not await self.check_ticket_state(interaction, ticket, "priority"):
            return

        db.update_priority(interaction.channel_id, priority)
        await interaction.response.send_message(f"📌 Priority set to: **{priority}**")

    @app_commands.command(name="note", description="Add internal staff note / إضافة ملاحظة داخلية")
    async def note(self, interaction: discord.Interaction):
        ticket = db.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            return await interaction.response.send_message("❌ Not a valid ticket channel.", ephemeral=True)

        if not await self.check_ticket_state(interaction, ticket, "add_note"):
            return

        modal = InternalNoteModal(ticket_id=ticket["id"])
        await interaction.response.send_modal(modal)

    @app_commands.command(name="rename", description="Rename ticket channel / تغيير اسم التذكرة")
    async def rename(self, interaction: discord.Interaction):
        ticket = db.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            return await interaction.response.send_message("❌ Not a valid ticket channel.", ephemeral=True)

        if not await self.check_ticket_state(interaction, ticket, "rename"):
            return

        settings = db.get_guild_settings(interaction.guild_id) or {}
        lang = settings.get("language", "ar")

        modal = RenameTicketModal(ticket=ticket, lang=lang)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="call", description="Call/alert the ticket owner / نداء صاحب التذكرة للحضور")
    async def call_member(self, interaction: discord.Interaction):
        ticket = db.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            return await interaction.response.send_message("❌ هذا ليس بقناة تذكرة صالحة.", ephemeral=True)

        if not await self.check_ticket_state(interaction, ticket, "summon_member"):
            return

        owner_id = ticket.get("user_id")
        if not owner_id:
            return await interaction.response.send_message("❌ لم يتم العثور على صاحب التذكرة.", ephemeral=True)

        guild = interaction.guild
        owner = guild.get_member(owner_id)
        if not owner:
            try:
                owner = await guild.fetch_member(owner_id)
            except:
                owner = None

        if owner:
            embed = EmbedBuilder.create_embed(
                title="🔔 نداء حضور / Attention Required",
                description=f"مرحباً {owner.mention}،\nيرجى التواجد في التذكرة {interaction.channel.mention} للرد على استفسار الدعم الفني.",
                color=EmbedBuilder.COLOR_WARNING
            )
            await interaction.response.send_message(content=owner.mention, embed=embed)
        else:
            await interaction.response.send_message(f"🔔 نداء حضور: صاحب التذكرة <@{owner_id}> يرجى التواجد ومتابعة الدعم الفني.")

    @app_commands.command(name="closure_search", description="Retrieve closure details for a ticket / استرجاع بيانات إغلاق تذكرة")
    @app_commands.describe(ticket_id="The ID of the ticket / رقم التذكرة")
    async def closure_search(self, interaction: discord.Interaction, ticket_id: int):
        if not PermissionHandler.is_staff(interaction.user):
            return await interaction.response.send_message("❌ هذا الأمر مخصص للطاقم فقط.", ephemeral=True)

        info = db.get_closure_info(ticket_id)
        if not info:
            return await interaction.response.send_message(f"❌ لم يتم العثور على بيانات إغلاق للتذكرة رقم #{ticket_id}.", ephemeral=True)

        ticket = db.get_ticket_by_id(ticket_id)
        
        embed = EmbedBuilder.create_embed(
            title=f"📋 بيانات واستبيان إغلاق التذكرة #{ticket_id}",
            color=EmbedBuilder.COLOR_INFO
        )
        
        if ticket:
            embed.add_field(name="👤 صاحب التذكرة", value=f"<@{ticket.get('user_id')}>", inline=True)
            embed.add_field(name="👔 الموظف المستلم", value=f"<@{ticket.get('claimed_by')}>", inline=True)
        
        t_type = info.get("ticket_type", "general")
        type_str = "🚨 شكوى" if t_type == "complaint" else ("💡 اقتراح" if t_type == "suggestion" else "💬 استفسار/عام")
        embed.add_field(name="🏷️ نوع التذكرة", value=type_str, inline=True)

        accepted_str = "✅ تم قبولها / التعامل بنجاح" if info.get("complaint_accepted") else "❌ لم يتم القبول / تعذر التعامل"
        embed.add_field(name="📊 حالة الطلب / الشكوى", value=accepted_str, inline=True)

        embed.add_field(name="🙋‍♂️ إجابة العضو (تم الحل؟)", value="نعم" if info.get("user_handled") else "لا", inline=True)

        p_type = info.get("punishment_type", "none")
        p_str = p_type
        if p_type == "timeout": p_str = f"⏳ تايم أوت ({info.get('timeout_duration', 0)} دقيقة)"
        elif p_type == "official_warning": p_str = "⚠️ تحذير رسمي"
        elif p_type == "verbal_warning": p_str = "🗣️ تحذير شفهي"
        elif p_type == "friendly": p_str = "🤝 تم حلها ودي"
        elif p_type == "none": p_str = "❌ لا يوجد عقوبة"

        embed.add_field(name="⚖️ العقوبة المتخذة", value=p_str, inline=True)

        punished_id = info.get("punished_user_id", 0)
        if punished_id and punished_id > 0:
            embed.add_field(name="👤 العضو المعاقب", value=f"<@{punished_id}>", inline=True)

        embed.add_field(name="📸 الأدلة المرفقة", value=info.get("evidence_urls") or "لا يوجد", inline=False)
        embed.add_field(name="📝 تفاصيل وحيثيات الموظف", value=info.get("staff_details") or "لا يوجد", inline=False)
        embed.add_field(name="📅 تاريخ الإغلاق", value=str(info.get("created_at")), inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="user_infractions", description="Show infractions and warnings history for a member / عرض سجل عقوبات العضو")
    @app_commands.describe(member="Target member / العضو المستهدف")
    async def user_infractions(self, interaction: discord.Interaction, member: discord.Member):
        if not PermissionHandler.is_staff(interaction.user):
            return await interaction.response.send_message("❌ هذا الأمر مخصص للإدارة وطاقم الدعم الفني فقط.", ephemeral=True)

        guild = interaction.guild
        summary = db.get_user_infractions_summary(guild.id, member.id)
        infractions = db.get_user_infractions(guild.id, member.id)

        embed = EmbedBuilder.create_embed(
            title=f"📜 سجل عقوبات وتحذيرات العضو: {member.display_name}",
            description=(
                f"👤 **العضو:** {member.mention} (`{member.id}`)\n\n"
                f"📊 **ملخص العقوبات:**\n"
                f"• 🗣️ **التحذيرات الشفهية:** `{summary['verbal_warnings']}`\n"
                f"• ⚠️ **التحذيرات الرسمية:** `{summary['official_warnings']}`\n"
                f"• ⏳ **عقوبات التايم أوت:** `{summary['timeouts']}`\n"
                f"• 📈 **الإجمالي:** `{summary['total']}`"
            ),
            color=EmbedBuilder.COLOR_PRIMARY if infractions else EmbedBuilder.COLOR_SUCCESS
        )

        if not infractions:
            embed.add_field(
                name="✅ السجل نظيف",
                value="هذا العضو لا يملك أي تحذيرات أو عقوبات سابقة في السيرفر.",
                inline=False
            )
        else:
            recent_infractions = infractions[:10]  # Show last 10
            for idx, inf in enumerate(recent_infractions, start=1):
                itype = inf.get("infraction_type")
                if itype == "timeout":
                    type_title = f"⏳ تايم أوت ({inf.get('duration_minutes', 0)} دقيقة)"
                elif itype == "official_warning":
                    type_title = "⚠️ تحذير رسمي"
                elif itype == "verbal_warning":
                    type_title = "🗣️ تحذير شفهي"
                else:
                    type_title = f"⚖️ {itype}"

                ticket_id = inf.get("ticket_id", 0)
                ticket_str = f"`#{ticket_id}`" if ticket_id else "غير محدد"
                executor_id = inf.get("executor_id", 0)
                executor_str = f"<@{executor_id}>" if executor_id else "النظام"
                reason_str = inf.get("reason") or "بدون سبب مدون"

                created = str(inf.get("created_at", ""))[:16].replace("T", " ")

                embed.add_field(
                    name=f"مخالفة #{idx} - {type_title}",
                    value=(
                        f"• **المسؤول:** {executor_str}\n"
                        f"• **التذكرة:** {ticket_str}\n"
                        f"• **السبب:** {reason_str}\n"
                        f"• **التاريخ:** `{created}`"
                    ),
                    inline=False
                )

        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketManagementCog(bot))
