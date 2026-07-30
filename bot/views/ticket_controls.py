import discord
from discord.ui import View, Select
import asyncio
import os
from bot.database.db import db
from bot.utils.permissions import PermissionHandler
from bot.config.locales import get_text
from bot.utils.embeds import EmbedBuilder
from bot.utils.transcript_generator import TranscriptGenerator
from bot.utils.logger import TicketLogger
from bot.views.modal_views import (
    TransferTicketModal, ChangePriorityModal, RenameTicketModal,
    ChangeDepartmentModal, ChangeOwnerModal, AddMemberModal,
    RemoveMemberModal, InternalNoteModal, RatingModal, AddEvidenceModal
)

# 1. Base Class for Action Handling
class TicketActionBase(Select):
    def __init__(self, ticket: dict, lang: str, placeholder: str, options: list, custom_id: str):
        self.ticket = ticket
        self.lang = lang
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options, custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        await self.process_action(interaction, self.values[0])

    async def process_action(self, interaction: discord.Interaction, action: str):
        guild = interaction.guild
        member = interaction.user
        
        # Always fetch fresh data to be stateless
        ticket = db.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            # Run rich diagnostics to explain why the lookup failed
            import os
            db_path_val = getattr(db, "db_path", "database/tickets.db")
            db_exists = os.path.exists(db_path_val)
            db_size = os.path.getsize(db_path_val) if db_exists else 0
            
            # Count how many tickets are in DB
            try:
                all_tickets_count = len(db.get_all_tickets())
            except Exception as e:
                all_tickets_count = f"Error: {e}"

            diagnostic_details = (
                f"❌ **لم يتم العثور على بيانات لهذه التذكرة في قاعدة البيانات.**\n\n"
                f"🔍 **معلومات تتبع ودورة حياة التذكرة (Diagnostics):**\n"
                f"• **اسم الملف الذي يفشل فيه البحث:** `bot/views/ticket_controls.py`\n"
                f"• **رقم السطر الذي يفشل فيه البحث:** السطر `33` (داخل `db.get_ticket_by_channel`)\n"
                f"• **مُعرِّف القناة المستخدم (Channel ID):** `{interaction.channel_id}`\n"
                f"• **اسم القناة الحالي:** `#{interaction.channel.name}`\n"
                f"• **مسار قاعدة البيانات المستخدم:** `{db.db_path}`\n"
                f"• **حالة ملف قاعدة البيانات:** {'موجود ✅' if db_exists else 'غير موجود ❌'} (الحجم: {db_size} بايت)\n"
                f"• **إجمالي التذاكر المسجلة بالكامل:** `{all_tickets_count}`\n\n"
                f"💡 **السبب المحتمل:** إذا كانت القناة قد تم إنشاؤها حديثاً ولم تجد لها سجلاً، فمن المحتمل أن تكون عملية الحفظ (INSERT) قد فشلت في الملف `bot/views/panel_view.py` بالسطر `106` أثناء إنشاء القناة، أو أن هذه القناة ليست تذكرة مسجلة بشكل رسمي في النظام."
            )
            return await interaction.response.send_message(diagnostic_details, ephemeral=True)
            
        ticket_user_id = ticket.get("user_id")
        claimed_by = ticket.get("claimed_by")

        # Specific user-friendly checks for staff/administration actions
        staff_actions = [
            "claim", "unclaim", "transfer", "toggle_hide", "department", "priority",
            "lock", "unlock", "hold", "resume", "hold_resume", "toggle_hold", "add_note",
            "audit_log", "generate_transcript", "delete", "rename", "summon_member", "owner",
            "toggle_evidence", "view_evidence"
        ]
        
        if action in staff_actions:
            if not PermissionHandler.is_staff(member) and not PermissionHandler.is_bot_owner(member.id):
                return await interaction.response.send_message("❌ عفواً! هذه الخيارات والأوامر مخصصة فقط لإدارة وطاقم الدعم الفني.", ephemeral=True)

            # Restrict Evidence management and critical system actions to Admin rank
            if action in ["toggle_evidence", "view_evidence", "delete", "audit_log", "generate_transcript"]:
                if not PermissionHandler.is_admin(member) and not PermissionHandler.is_bot_owner(member.id):
                    return await interaction.response.send_message("❌ عفواً! هذا الخيار مخصص فقط لمسؤولي الإدارة (Admin).", ephemeral=True)

            if action not in ["claim"] and not claimed_by:
                user_rank = PermissionHandler.get_member_rank(member)
                if user_rank < PermissionHandler.ROLE_HIERARCHY["admin"] and not PermissionHandler.is_bot_owner(member.id):
                    return await interaction.response.send_message("⚠️ يجب استلام التذكرة أولاً لتتمكن من استخدام أوامر الإدارة عليها!", ephemeral=True)

            if claimed_by and member.id != claimed_by:
                user_rank = PermissionHandler.get_member_rank(member)
                if user_rank < PermissionHandler.ROLE_HIERARCHY["admin"] and not PermissionHandler.is_bot_owner(member.id):
                    return await interaction.response.send_message(f"❌ هذه التذكرة مستلمة من قبل موظف آخر (<@{claimed_by}>)، ولا يمكنك إدارتها إلا إذا كنت مسؤولاً.", ephemeral=True)

        if action != "restart" and not PermissionHandler.can_execute_action(guild, member, action, ticket_user_id, ticket_data=ticket):
            return await interaction.response.send_message(get_text("permission_denied", self.lang), ephemeral=True)

        if action in ["transfer", "priority", "rename", "department", "owner", "add_member", "remove_member", "add_note", "rate_staff", "add_evidence"]:
            # These open modals, cannot defer
            if action == "add_evidence":
                if not db.is_evidence_enabled(interaction.channel_id):
                    return await interaction.response.send_message("⚠️ ميزة إضافة الأدلة معطلة لهذه التذكرة حالياً من قبل الإدارة.", ephemeral=True)
                await interaction.response.send_modal(AddEvidenceModal(ticket, self.lang))
            elif action == "rate_staff":
                if not ticket.get("claimed_by"):
                    return await interaction.response.send_message("⚠️ لا يمكن تقييم التذكرة لأنها لم تُستلم من قبل أي موظف بعد.", ephemeral=True)
                if member.id != ticket_user_id:
                    return await interaction.response.send_message("❌ خيار تقييم الموظف مخصص فقط لصاحب التذكرة!", ephemeral=True)
                if member.id == ticket.get("claimed_by"):
                    return await interaction.response.send_message("❌ لا يمكنك تقييم نفسك!", ephemeral=True)
                await interaction.response.send_modal(RatingModal(ticket, staff_id=ticket.get("claimed_by"), lang=self.lang))
            elif action == "transfer": await interaction.response.send_modal(TransferTicketModal(ticket, self.lang))
            elif action == "priority": await interaction.response.send_modal(ChangePriorityModal(ticket, self.lang))
            elif action == "rename": await interaction.response.send_modal(RenameTicketModal(ticket, self.lang))
            elif action == "department": await interaction.response.send_modal(ChangeDepartmentModal(ticket, self.lang))
            elif action == "owner": await interaction.response.send_modal(ChangeOwnerModal(ticket, self.lang))
            elif action == "add_member": await interaction.response.send_modal(AddMemberModal(ticket, self.lang))
            elif action == "remove_member": await interaction.response.send_modal(RemoveMemberModal(ticket, self.lang))
            elif action == "add_note": await interaction.response.send_modal(InternalNoteModal(ticket, self.lang))
            return

        # For other actions, defer immediately to prevent "Application did not respond"
        await interaction.response.defer(ephemeral=True if action in ["info", "audit_log", "toggle_hide"] else False)

        if action == "claim":
            if ticket.get("claimed_by"):
                return await interaction.followup.send("❌ هذه التذكرة مستلمة بالفعل!", ephemeral=True)
            if member.id == ticket_user_id:
                return await interaction.followup.send("❌ لا يمكنك استلام تذكرتك الخاصة!", ephemeral=True)

            db.claim_ticket(interaction.channel_id, member.id)
            db.increment_staff_tickets(guild.id, member.id)
            
            # Award category points on claim
            category_points = ticket.get("category_points", 0)
            if category_points > 0:
                db.update_staff_points(guild.id, member.id, category_points)
            
            settings = db.get_guild_settings(guild.id) or {}
            staff_roles = [settings.get("support_role_id"), settings.get("senior_support_role_id"), settings.get("admin_role_id"), settings.get("support_manager_role_id"), settings.get("owner_role_id")]
            overwrites = interaction.channel.overwrites
            
            for role_id in staff_roles:
                if role_id:
                    role = guild.get_role(int(role_id))
                    if role: overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=False)
            
            overwrites[member] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True, manage_messages=True)
            
            owner = guild.get_member(ticket_user_id)
            if owner: overwrites[owner] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)
            
            await interaction.channel.edit(overwrites=overwrites)
            await interaction.followup.send(embed=EmbedBuilder.create_embed(title="📌 تم استلام التذكرة", description=f"تم استلام التذكرة بواسطة {member.mention}.", color=EmbedBuilder.COLOR_SUCCESS))
            await TicketLogger.log_action(guild, ticket, "استلام التذكرة", member)

        elif action == "unclaim":
            claimed_id = ticket.get("claimed_by")
            if not claimed_id: return await interaction.followup.send("⚠️ التذكرة غير مستلمة حالياً!", ephemeral=True)
            
            db.claim_ticket(interaction.channel_id, None)
            settings = db.get_guild_settings(guild.id) or {}
            staff_roles = [settings.get("support_role_id"), settings.get("senior_support_role_id"), settings.get("admin_role_id"), settings.get("support_manager_role_id"), settings.get("owner_role_id")]
            overwrites = interaction.channel.overwrites
            
            for role_id in staff_roles:
                if role_id:
                    role = guild.get_role(int(role_id))
                    if role: overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=False)
            
            claimant = guild.get_member(claimed_id)
            if claimant and claimant in overwrites: del overwrites[claimant]
            
            await interaction.channel.edit(overwrites=overwrites)
            await interaction.followup.send(embed=EmbedBuilder.create_embed(title="🔓 تم إلغاء الاستلام", description="عادت التذكرة متاحة للاستلام.", color=EmbedBuilder.COLOR_WARNING))
            await TicketLogger.log_action(guild, ticket, "إلغاء الاستلام", member)

        elif action == "close":
            db.update_ticket_status(interaction.channel_id, "closed")
            owner = guild.get_member(ticket_user_id) if ticket_user_id else None
            if not owner and ticket_user_id:
                try:
                    owner = await guild.fetch_member(ticket_user_id)
                except Exception:
                    try:
                        owner = await interaction.client.fetch_user(ticket_user_id)
                    except Exception:
                        owner = None

            if owner and isinstance(owner, discord.Member):
                await interaction.channel.set_permissions(owner, view_channel=True, send_messages=False)

            await interaction.followup.send(embed=EmbedBuilder.create_embed(title="🔒 تم إغلاق التذكرة", description=f"أغلقت التذكرة بواسطة {member.mention}.", color=EmbedBuilder.COLOR_DANGER))
            await TicketLogger.log_action(guild, ticket, "إغلاق التذكرة", member)

            try:
                from bot.utils.transcript_generator import TranscriptGenerator
                await TranscriptGenerator.send_transcript(interaction.channel, ticket, guild)
            except Exception as e:
                print(f"Error sending transcript on close: {e}")

            # Send rating view to ticket owner if claimed
            staff_id = ticket.get("claimed_by")
            if owner and ticket_user_id and staff_id:
                from bot.views.rating_view import RatingView
                try:
                    staff_member = guild.get_member(staff_id)
                    if not staff_member:
                        try:
                            staff_member = await guild.fetch_member(staff_id)
                        except Exception:
                            staff_member = None
                    staff_mention = staff_member.mention if staff_member else f"<@{staff_id}>"

                    rating_embed = EmbedBuilder.create_embed(
                        title="⭐ تقييم خدمة الدعم الفني",
                        description=(
                            f"مرحباً <@{ticket_user_id}> 👋،\n"
                            f"تم إغلاق تذكرتك بنجاح في سيرفر **{guild.name}**.\n\n"
                            f"👤 **مستلم التذكرة / المسؤول:** {staff_mention}\n\n"
                            f"يرجى تقييم أداء الموظف وجودة الخدمة التي تلقيتها بالضغط على الأزرار أدناه (1 إلى 5 نجوم):"
                        ),
                        color=EmbedBuilder.COLOR_PRIMARY
                    )
                    await owner.send(embed=rating_embed, view=RatingView(ticket['id'], staff_id, self.lang))
                except Exception as e:
                    print(f"Error sending rating DM to owner: {e}")

        elif action == "summon_staff":
            settings = db.get_guild_settings(guild.id) or {}
            staff_role_id = settings.get("support_role_id")
            role_mention = f"<@&{staff_role_id}>" if staff_role_id else "@everyone"
            await interaction.channel.send(f"🔔 {role_mention}، العضو {member.mention} بحاجة للمساعدة!")
            await interaction.followup.send("✅ تم إرسال نداء لطاقم الدعم.", ephemeral=True)

            # Private DM notification to the claimed staff member
            claimed_id = ticket.get("claimed_by")
            if claimed_id:
                try:
                    claimed_member = guild.get_member(claimed_id) or await guild.fetch_member(claimed_id)
                    if claimed_member:
                        lang = settings.get("language", "ar")
                        title_dm = "🔔 نداء دعم في تذكرة مستلمة" if lang == "ar" else "🔔 Support Summon in Claimed Ticket"
                        desc_dm = (
                            f"لقد تم استدعاؤك في التذكرة {interaction.channel.mention} من قبل العضو {member.mention}.\nيرجى التوجه إلى القناة لتقديم المساعدة."
                            if lang == "ar" else
                            f"You have been summoned in ticket {interaction.channel.mention} by member {member.mention}.\nPlease head over to the channel to assist."
                        )
                        embed_dm = EmbedBuilder.create_embed(title=title_dm, description=desc_dm, color=EmbedBuilder.COLOR_WARNING)
                        await claimed_member.send(embed=embed_dm)
                except Exception as e:
                    print(f"Error sending DM alert to claimed staff: {e}")

        elif action == "summon_member":
            owner_id = ticket.get("user_id")
            if not owner_id:
                return await interaction.followup.send("❌ لم يتم العثور على صاحب التذكرة.", ephemeral=True)
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
                await interaction.channel.send(content=owner.mention, embed=embed)
            else:
                await interaction.channel.send(f"🔔 نداء حضور: صاحب التذكرة <@{owner_id}> يرجى التواجد ومتابعة الدعم الفني.")
            await interaction.followup.send("✅ تم إرسال نداء لصاحب التذكرة.", ephemeral=True)


        elif action == "toggle_hide":
            is_hidden = ticket.get("is_hidden", 0)
            new_hidden = 0 if is_hidden else 1
            await PermissionHandler.set_ticket_visibility(interaction.channel, guild, ticket, is_hidden=bool(new_hidden))
            status_text = "مخفية (فقط المستلم وصاحب التذكرة)" if new_hidden else "مرئية لكافة الطاقم (مشاهدة فقط بدون كتابة)"
            await interaction.followup.send(f"✅ تم تغيير حالة التذكرة إلى: **{status_text}**", ephemeral=True)

        elif action in ["lock", "unlock"]:
            owner = guild.get_member(ticket_user_id) if ticket_user_id else None
            if not owner and ticket_user_id:
                try:
                    owner = await guild.fetch_member(ticket_user_id)
                except Exception:
                    owner = None

            if action == "lock":
                if owner and isinstance(owner, discord.Member):
                    await interaction.channel.set_permissions(owner, view_channel=False)
                db.update_ticket_status(interaction.channel_id, "locked")
                await interaction.followup.send(embed=EmbedBuilder.create_embed(title="🔐 تم قفل التذكرة", description="تم قفل التذكرة وإخفاؤها عن العضو.", color=EmbedBuilder.COLOR_DANGER))
            else:
                if owner and isinstance(owner, discord.Member):
                    await interaction.channel.set_permissions(owner, view_channel=True, send_messages=True)
                new_st = "claimed" if ticket.get("claimed_by") else "open"
                db.update_ticket_status(interaction.channel_id, new_st)
                await interaction.followup.send(embed=EmbedBuilder.create_embed(title="🔓 تم فتح التذكرة", description="تمت إعادة صلاحية الرؤية والكتابة للعضو.", color=EmbedBuilder.COLOR_SUCCESS))

        elif action in ["hold", "resume", "hold_resume", "toggle_hold"]:
            current_status = ticket.get("status", "open")
            owner = guild.get_member(ticket_user_id) if ticket_user_id else None
            if not owner and ticket_user_id:
                try:
                    owner = await guild.fetch_member(ticket_user_id)
                except Exception:
                    owner = None

            if current_status == "on_hold" or action == "resume":
                if owner and isinstance(owner, discord.Member):
                    await interaction.channel.set_permissions(owner, view_channel=True, send_messages=True)
                new_st = "claimed" if ticket.get("claimed_by") else "open"
                db.update_ticket_status(interaction.channel_id, new_st)
                await interaction.followup.send(embed=EmbedBuilder.create_embed(title="▶️ تم استئناف التذكرة", description="تمت إعادة صلاحية الكتابة للعضو بنجاح.", color=EmbedBuilder.COLOR_SUCCESS))
                await TicketLogger.log_action(guild, ticket, "استئناف التذكرة", member)
            else:
                if owner and isinstance(owner, discord.Member):
                    await interaction.channel.set_permissions(owner, view_channel=True, send_messages=False)
                db.update_ticket_status(interaction.channel_id, "on_hold")
                await interaction.followup.send(embed=EmbedBuilder.create_embed(title="⏸️ تم تعليق التذكرة", description="العضو الآن قادر على الرؤية فقط ولا يمكنه الكتابة.", color=EmbedBuilder.COLOR_WARNING))
                await TicketLogger.log_action(guild, ticket, "تعليق التذكرة", member)

        elif action == "restart":
            is_hidden = ticket.get("is_hidden", 0)
            await PermissionHandler.set_ticket_visibility(interaction.channel, guild, ticket, is_hidden=bool(is_hidden))
            await interaction.followup.send(
                embed=EmbedBuilder.create_embed(
                    title="🔄 تم إعادة تشغيل القائمة والتذكرة",
                    description="تم تحديث حالة القائمة وضبط صلاحيات القناة بنجاح! 🔄",
                    color=EmbedBuilder.COLOR_PRIMARY
                ),
                ephemeral=True
            )

        elif action == "info":
            owner_id = ticket.get("user_id")
            claimed_id = ticket.get("claimed_by")
            
            owner_mention = f"<@{owner_id}>" if owner_id else "غير معروف"
            claimed_mention = f"<@{claimed_id}>" if claimed_id else "❌ لم تستلم بعد"
            
            embed = EmbedBuilder.create_embed(title=f"📊 حالة التذكرة #{ticket.get('id')}", color=EmbedBuilder.COLOR_INFO)
            embed.add_field(name="👤 صاحب التذكرة", value=owner_mention, inline=True)
            embed.add_field(name="📌 المستلم الحالي", value=claimed_mention, inline=True)
            embed.add_field(name="🔒 الحالة", value=f"**{ticket.get('status', 'open').upper()}**", inline=True)
            embed.add_field(name="👁️ الرؤية", value="🙈 مخفية" if ticket.get("is_hidden") else "👁️ عامة للطاقم", inline=True)
            created_at = ticket.get("created_at")
            try:
                if isinstance(created_at, str) and "T" in created_at:
                    from datetime import datetime
                    ts = int(datetime.fromisoformat(created_at).timestamp())
                else:
                    ts = int(float(created_at or 0))
            except: ts = 0
            
            embed.add_field(name="📅 تاريخ الفتح", value=f"<t:{ts}:F>" if ts else "غير معروف", inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)

        elif action == "audit_log":
            audits = db.get_audit_logs(ticket.get("id"))
            log_text = "\n".join([f"• {a['action']} بواسطة <@{a['executor_id']}>" for a in audits[-10:]])
            await interaction.followup.send(f"📜 **سجل العمليات الأخير:**\n{log_text or 'لا توجد عمليات مسجلة.'}", ephemeral=True)

        elif action == "toggle_evidence":
            new_state = db.toggle_ticket_evidence(interaction.channel_id)
            status_str = "مفعّلة ✅" if new_state else "معطّلة ❌"
            embed = EmbedBuilder.create_embed(
                title="⚙️ حالة ميزة الأدلة والصور",
                description=f"تم تعديل ميزة استقبال وتسجيل الأدلة لهذه التذكرة لتصبح: **{status_str}**",
                color=EmbedBuilder.COLOR_SUCCESS if new_state else EmbedBuilder.COLOR_WARNING
            )
            await interaction.followup.send(embed=embed)
            await TicketLogger.log_action(guild, ticket, "تغيير حالة الأدلة", member, details=f"أصبحت: {status_str}")

        elif action == "view_evidence":
            evidence_list = db.get_ticket_evidence(ticket.get("id", 0))
            if not evidence_list:
                embed = EmbedBuilder.create_embed(
                    title="📸 قائمة أدلة ومرفقات التذكرة",
                    description="📷 لم يتم تسجيل أو إرفاق أي أدلة لهذه التذكرة حتى الآن.",
                    color=EmbedBuilder.COLOR_INFO
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)

            embed = EmbedBuilder.create_embed(
                title=f"📸 قائمة الأدلة والمرفقات للتذكرة #{ticket.get('id')}",
                description=f"إجمالي الأدلة المسجلة: **{len(evidence_list)}** دليلاً\n\n",
                color=EmbedBuilder.COLOR_PRIMARY
            )
            
            for idx, item in enumerate(evidence_list, 1):
                u_id = item.get("user_id")
                url = item.get("evidence_url")
                note = item.get("note")
                dt_str = item.get("created_at", "")
                
                try:
                    if isinstance(dt_str, str) and "T" in dt_str:
                        from datetime import datetime
                        ts = int(datetime.fromisoformat(dt_str).timestamp())
                        time_fmt = f"<t:{ts}:R>"
                    else:
                        time_fmt = dt_str
                except:
                    time_fmt = dt_str

                val = f"👤 بواسطة: <@{u_id}> ({time_fmt})\n🔗 [رابط الدليل / الصورة]({url})"
                if note:
                    val += f"\n📝 ملاحظة: {note}"
                
                embed.add_field(name=f"دليل #{idx}", value=val, inline=False)

            latest_url = evidence_list[-1].get("evidence_url")
            if latest_url and (latest_url.startswith("http://") or latest_url.startswith("https://")):
                embed.set_image(url=latest_url)

            await interaction.followup.send(embed=embed)

        elif action == "generate_transcript":
            from bot.utils.transcript_generator import TranscriptGenerator
            await TranscriptGenerator.send_transcript(interaction.channel, ticket, guild, interaction)
            await TicketLogger.log_action(guild, ticket, "تصدير Transcript", member)
        
        elif action == "delete":
            await interaction.followup.send("🗑️ جاري حذف التذكرة وإرسال طلب التقييم لصاحب التذكرة خلال 3 ثوانٍ...")
            try:
                from bot.utils.transcript_generator import TranscriptGenerator
                await TranscriptGenerator.send_transcript(interaction.channel, ticket, guild)
            except Exception as e:
                print(f"Error sending transcript on delete: {e}")
            owner = guild.get_member(ticket_user_id) if ticket_user_id else None
            if not owner and ticket_user_id:
                try:
                    owner = await guild.fetch_member(ticket_user_id)
                except Exception:
                    try:
                        owner = await interaction.client.fetch_user(ticket_user_id)
                    except Exception:
                        owner = None

            staff_id = ticket.get("claimed_by")
            if owner and ticket_user_id and staff_id:
                from bot.views.rating_view import RatingView
                try:
                    staff_member = guild.get_member(staff_id)
                    if not staff_member:
                        try:
                            staff_member = await guild.fetch_member(staff_id)
                        except Exception:
                            staff_member = None
                    staff_mention = staff_member.mention if staff_member else f"<@{staff_id}>"

                    rating_embed = EmbedBuilder.create_embed(
                        title="⭐ تقييم خدمة الدعم الفني",
                        description=(
                            f"مرحباً <@{ticket_user_id}> 👋،\n"
                            f"تم حذف تذكرتك في سيرفر **{guild.name}**.\n\n"
                            f"👤 **مستلم التذكرة / المسؤول:** {staff_mention}\n\n"
                            f"يرجى تقييم أداء الموظف وجودة الخدمة التي تلقيتها بالضغط على الأزرار أدناه (1 إلى 5 نجوم):"
                        ),
                        color=EmbedBuilder.COLOR_PRIMARY
                    )
                    await owner.send(embed=rating_embed, view=RatingView(ticket['id'], staff_id, self.lang))
                except Exception as e:
                    print(f"Error sending rating DM on delete: {e}")

            db.update_ticket_status(interaction.channel_id, "deleted")
            await TicketLogger.log_action(guild, ticket, "حذف التذكرة", member)
            await asyncio.sleep(3)
            await interaction.channel.delete()


# Select Components
class MemberActionsSelect(TicketActionBase):
    def __init__(self, ticket: dict, lang: str = "ar"):
        super().__init__(ticket=ticket, lang=lang, placeholder="👤 أوامر العضو", options=[
            discord.SelectOption(label="إغلاق التذكرة", value="close", emoji="🔒"),
            discord.SelectOption(label="إضافة دليل", value="add_evidence", emoji="📸"),
            discord.SelectOption(label="تقييم الإداري", value="rate_staff", emoji="⭐"),
            discord.SelectOption(label="نداء الدعم", value="summon_staff", emoji="🔔"),
            discord.SelectOption(label="إضافة عضو", value="add_member", emoji="➕"),
            discord.SelectOption(label="حالة التذكرة", value="info", emoji="📊"),
            discord.SelectOption(label="🔄 ريستارت / إعادة تحديث القائمة", value="restart", emoji="🔄")
        ], custom_id="sel_member")

class StaffManagementSelect(TicketActionBase):
    def __init__(self, ticket: dict, lang: str = "ar"):
        claimed = ticket.get("claimed_by")
        super().__init__(ticket=ticket, lang=lang, placeholder="👔 إدارة الطاقم", options=[
            discord.SelectOption(label="استلام التذكرة" if not claimed else "استلام (مستلمة)", value="claim", emoji="📌"),
            discord.SelectOption(label="إلغاء الاستلام", value="unclaim", emoji="🔓"),
            discord.SelectOption(label="نقل التذكرة", value="transfer", emoji="🔄"),
            discord.SelectOption(label="تغيير اسم التذكرة", value="rename", emoji="✏️"),
            discord.SelectOption(label="نداء صاحب التذكرة", value="summon_member", emoji="🔔"),
            discord.SelectOption(label="عرض الأدلة", value="view_evidence", emoji="📸"),
            discord.SelectOption(label="إخفاء/إظهار", value="toggle_hide", emoji="👁️"),
            discord.SelectOption(label="تغيير القسم", value="department", emoji="🏢"),
            discord.SelectOption(label="تغيير الأولوية", value="priority", emoji="⚡"),
            discord.SelectOption(label="🔄 ريستارت / إعادة تحديث القائمة", value="restart", emoji="🔄")
        ], custom_id="sel_staff_mgmt")

class StaffSystemSelect(TicketActionBase):
    def __init__(self, ticket: dict, lang: str = "ar"):
        super().__init__(ticket=ticket, lang=lang, placeholder="⚙️ النظام والأرشيف", options=[
            discord.SelectOption(label="قفل/فتح (للعضو)", value="lock", emoji="🔐"),
            discord.SelectOption(label="تعليق/استئناف", value="hold_resume", emoji="⏸️"),
            discord.SelectOption(label="ملاحظة داخلية", value="add_note", emoji="📝"),
            discord.SelectOption(label="سجل العمليات", value="audit_log", emoji="📜"),
            discord.SelectOption(label="تعطيل/تفعيل الأدلة", value="toggle_evidence", emoji="🚫"),
            discord.SelectOption(label="Transcript", value="generate_transcript", emoji="📄"),
            discord.SelectOption(label="حذف نهائي", value="delete", emoji="🗑️"),
            discord.SelectOption(label="🔄 ريستارت / إعادة تحديث القائمة", value="restart", emoji="🔄")
        ], custom_id="sel_staff_sys")

class TicketControlView(View):
    def __init__(self, lang: str = "ar"):
        super().__init__(timeout=None)
        # Pass a dummy ticket, selects will fetch real data in callback
        dummy = {"id": 0, "status": "open"}
        self.add_item(MemberActionsSelect(dummy, lang))
        self.add_item(StaffManagementSelect(dummy, lang))
        self.add_item(StaffSystemSelect(dummy, lang))

    @discord.ui.button(label="🔄 ريستارت القائمة", style=discord.ButtonStyle.secondary, custom_id="btn_restart_ticket_controls", row=3)
    async def btn_restart_controls(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        ticket = db.get_ticket_by_channel(interaction.channel_id)
        if ticket:
            is_hidden = ticket.get("is_hidden", 0)
            await PermissionHandler.set_ticket_visibility(interaction.channel, interaction.guild, ticket, is_hidden=bool(is_hidden))
        await interaction.followup.send("🔄 **تم إعادة تشغيل وتحديث قائمة التذكرة وصلاحياتها بنجاح!**", ephemeral=True)

