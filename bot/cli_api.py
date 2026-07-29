import sys
import json
import os
import asyncio
import logging
import urllib.request
import urllib.error
from typing import Any, Dict

# Redirect root logger to sys.stderr so stdout stays pure JSON
logging.basicConfig(level=logging.ERROR, stream=sys.stderr)
for log_name in ("discord", "discord.client", "discord.gateway", "discord.http"):
    logging.getLogger(log_name).setLevel(logging.ERROR)

# Ensure bot directory is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.database.db import db
from bot.config.settings import Config

import base64

def get_bot_invite_url() -> str:
    db_token = db.get_guild_setting(0, "bot_token")
    token = db_token or os.getenv("DISCORD_BOT_TOKEN") or Config.BOT_TOKEN or ""
    if token:
        token = token.strip().strip('"').strip("'")
        if token.lower().startswith("bot "):
            token = token[4:].strip()
        elif token.lower().startswith("bearer "):
            token = token[7:].strip()
        parts = token.split(".")
        if len(parts) >= 1 and len(parts[0]) > 5:
            try:
                padded = parts[0] + "=" * ((4 - len(parts[0]) % 4) % 4)
                bot_id = base64.b64decode(padded).decode('utf-8')
                if bot_id.isdigit():
                    return f"https://discord.com/api/oauth2/authorize?client_id={bot_id}&permissions=8&scope=bot%20applications.commands"
            except Exception:
                pass
    return "https://discord.com/developers/applications"

def fetch_discord(endpoint: str):
    db_token = db.get_guild_setting(0, "bot_token")
    token = db_token or os.getenv("DISCORD_BOT_TOKEN") or Config.BOT_TOKEN
    if token:
        token = token.strip().strip('"').strip("'")
        if token.lower().startswith("bot "):
            token = token[4:].strip()
        elif token.lower().startswith("bearer "):
            token = token[7:].strip()
    if not token or token.startswith("YOUR_") or len(token) < 10:
        return None, "يرجى تعيين توكن البوت (Discord Bot Token) أولاً في الإعدادات."
    
    url = f"https://discord.com/api/v10{endpoint}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bot {token}",
        "User-Agent": "DiscordBot (TicketBot, 1.0)"
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data, None
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return None, "خطأ (401): توكن البوت غير صحيح أو تم إلغاؤه من ديسكورد."
        elif e.code == 403:
            return None, "خطأ (403): البوت غير موجود في هذا السيرفر أو لا يملك صلاحية (Administrator)."
        elif e.code == 404:
            return None, "خطأ (404): لم يتم العثور على السيرفر أو القناة المطلوبة."
        return None, f"خطأ من ديسكورد ({e.code}): {e.reason}"
    except Exception as e:
        return None, str(e)

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No command provided"}))
        sys.exit(1)

    command = sys.argv[1]
    raw_args = sys.argv[2] if len(sys.argv) > 2 else "{}"
    try:
        args = json.loads(raw_args)
    except Exception:
        args = {}

    guild_id = args.get("guild_id", 0)

    try:
        if command == "get_guilds":
            guilds, err = fetch_discord("/users/@me/guilds")
            if err:
                print(json.dumps({"success": False, "error": err}))
            else:
                formatted = []
                for g in guilds:
                    icon_hash = g.get("icon")
                    ext = "gif" if icon_hash and str(icon_hash).startswith("a_") else "png"
                    icon_url = f"https://cdn.discordapp.com/icons/{g['id']}/{icon_hash}.{ext}" if icon_hash else None
                    formatted.append({
                        "id": g["id"],
                        "name": g["name"],
                        "icon": icon_url
                    })
                print(json.dumps({"success": True, "guilds": formatted}))

        elif command == "get_guild_details":
            target_gid = args.get("guild_id")
            if not target_gid:
                print(json.dumps({"success": False, "error": "المعرف غير محدد"}))
                return

            guild_meta, err_g = fetch_discord(f"/guilds/{target_gid}")
            channels_data, err_c = fetch_discord(f"/guilds/{target_gid}/channels")
            roles_data, err_r = fetch_discord(f"/guilds/{target_gid}/roles")

            if err_c and err_r and err_g:
                inv = get_bot_invite_url()
                err_msg = f"⚠️ البوت غير متواجد في هذا السيرفر ({target_gid}). يرجى إضافة ودعوة البوت أولاً للسيرفر وإعطائه صلاحيات Administrator."
                print(json.dumps({"success": False, "error": err_msg, "invite_url": inv}))
                return

            guild_info = None
            if isinstance(guild_meta, dict) and "id" in guild_meta:
                icon_hash = guild_meta.get("icon")
                ext = "gif" if icon_hash and str(icon_hash).startswith("a_") else "png"
                icon_url = f"https://cdn.discordapp.com/icons/{guild_meta['id']}/{icon_hash}.{ext}" if icon_hash else None
                guild_info = {
                    "id": guild_meta["id"],
                    "name": guild_meta.get("name", f"Server {guild_meta['id']}"),
                    "icon": icon_url
                }

            text_channels = []
            categories = []
            if isinstance(channels_data, list):
                for ch in channels_data:
                    # type 0 = GUILD_TEXT, type 5 = GUILD_ANNOUNCEMENT
                    if ch.get("type") in (0, 5):
                        text_channels.append({"id": ch["id"], "name": ch["name"]})
                    # type 4 = GUILD_CATEGORY
                    elif ch.get("type") == 4:
                        categories.append({"id": ch["id"], "name": ch["name"]})

            roles = []
            if isinstance(roles_data, list):
                for r in roles_data:
                    if r.get("name") != "@everyone":
                        roles.append({"id": r["id"], "name": r["name"], "color": r.get("color", 0)})

            print(json.dumps({
                "success": True,
                "guild_info": guild_info,
                "text_channels": text_channels,
                "categories": categories,
                "roles": roles
            }))

        elif command == "get_settings":
            settings = db.get_guild_settings(guild_id) or {
                "guild_id": guild_id,
                "log_channel_id": None,
                "transcript_channel_id": None,
                "category_id": None,
                "owner_role_id": None,
                "admin_role_id": None,
                "support_manager_role_id": None,
                "senior_support_role_id": None,
                "support_role_id": None,
                "language": "ar"
            }
            print(json.dumps({"success": True, "settings": settings}))

        elif command == "save_settings":
            for key in ["log_channel_id", "transcript_channel_id", "category_id", "owner_role_id",
                        "admin_role_id", "support_manager_role_id", "senior_support_role_id",
                        "support_role_id", "language"]:
                if key in args:
                    val = args[key]
                    if val is not None and str(val).isdigit():
                        val = int(val)
                    db.set_guild_setting(guild_id, key, val)
            print(json.dumps({"success": True, "message": "تم حفظ جميع الإعدادات ورتب الدعم وقناة اللوجز بنجاح!"}))

        elif command == "save_bot_token":
            token = args.get("token", "").strip()
            if token:
                db.set_guild_setting(0, "bot_token", token)
                os.environ["DISCORD_BOT_TOKEN"] = token
                Config.BOT_TOKEN = token
                try:
                    with open(".env", "w") as f:
                        f.write(f"DISCORD_BOT_TOKEN={token}\nPORT=3000\n")
                except Exception:
                    pass
                inv = get_bot_invite_url()
                print(json.dumps({"success": True, "message": "تم حفظ توكن البوت بنجاح!", "invite_url": inv}))
            else:
                print(json.dumps({"success": False, "error": "التوكن فارغ"}))

        elif command == "get_bot_token":
            db_token = db.get_guild_setting(0, "bot_token")
            token = db_token or os.getenv("DISCORD_BOT_TOKEN") or Config.BOT_TOKEN or ""
            inv = get_bot_invite_url()
            print(json.dumps({"success": True, "token": token, "invite_url": inv}))

        elif command == "get_panels":
            panels = db.get_panels()
            print(json.dumps({"success": True, "panels": panels}))

        elif command == "save_panel":
            target_panel_id = args.get("panel_id")
            title = args.get("title", "لوحة الدعم الفني والتذاكر")
            description = args.get("description", "اختر القسم المناسب من القائمة أسفله لفتح تذكرة مباشرة مع فريق الدعم.")
            color = args.get("color", 5793266)
            categories = args.get("categories", [])
            channel_id = args.get("channel_id")
            image_url = args.get("image_url")
            footer_text = args.get("footer_text")

            if channel_id and str(channel_id).isdigit():
                channel_id = int(channel_id)

            panel_id = db.save_panel(
                title=title,
                description=description,
                color=color,
                categories=categories,
                channel_id=channel_id,
                image_url=image_url,
                footer_text=footer_text,
                panel_id=int(target_panel_id) if target_panel_id else None
            )
            print(json.dumps({"success": True, "panel_id": panel_id, "message": "تم حفظ لوحة التذاكر بنجاح"}))

        elif command == "delete_panel":
            panel_id = args.get("panel_id")
            if panel_id:
                with db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM panels WHERE id = ?", (panel_id,))
                    conn.commit()
            print(json.dumps({"success": True, "message": "تم حذف اللوحة بنجاح"}))

        elif command == "dispatch_panel":
            panel_id = args.get("panel_id")
            channel_id = args.get("channel_id")
            db_token = db.get_guild_setting(0, "bot_token")
            token = os.getenv("DISCORD_BOT_TOKEN") or db_token or Config.BOT_TOKEN

            if not token or token.startswith("YOUR_") or len(token) < 10:
                print(json.dumps({"success": False, "error": "يرجى إضافة Discord Bot Token أولاً للقدرة على النشر إلى الديسكورد."}))
                return

            if not channel_id or not str(channel_id).isdigit():
                print(json.dumps({"success": False, "error": "معرف القناة غير صحيح."}))
                return

            # Execute single async dispatch via Discord client
            async def run_dispatch():
                import discord
                from bot.utils.embeds import EmbedBuilder
                from bot.views.panel_view import PanelView

                panels = db.get_panels()
                target_panel = next((p for p in panels if p["id"] == int(panel_id)), None)
                if not target_panel:
                    return {"success": False, "error": "اللوحة غير موجودة في قاعدة البيانات"}

                intents = discord.Intents.default()
                intents.guilds = True
                client = discord.Client(intents=intents)

                res = {"success": False}

                @client.event
                async def on_ready():
                    nonlocal res
                    try:
                        ch_id = int(channel_id)
                        channel = client.get_channel(ch_id) or await client.fetch_channel(ch_id)
                        if not channel:
                            res = {"success": False, "error": "تعذر العثور على القناة المحددة"}
                            await client.close()
                            return

                        embed = EmbedBuilder.panel_embed(
                            title=target_panel["title"],
                            description=target_panel["description"],
                            color=target_panel.get("color", 5793266),
                            guild=channel.guild,
                            image_url=target_panel.get("image_url"),
                            footer_text=target_panel.get("footer_text"),
                            categories=target_panel.get("categories", [])
                        )

                        view = PanelView(categories=target_panel.get("categories", []), panel_id=target_panel["id"])
                        msg = await channel.send(embed=embed, view=view)
                        db.update_panel_message_id(target_panel["id"], msg.id)
                        res = {"success": True, "message_id": msg.id, "message": f"تم نشر اللوحة بنجاح في القناة {channel.name}"}
                    except Exception as e:
                        res = {"success": False, "error": f"خطأ أثناء النشر: {str(e)}"}
                    finally:
                        await client.close()

                try:
                    await client.start(token)
                except Exception as ex:
                    res = {"success": False, "error": f"فشل تسجيل دخول البوت: {str(ex)}"}
                return res

            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(run_dispatch())
            print(json.dumps(result))

        elif command == "get_blacklist":
            import sqlite3
            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM blacklist ORDER BY created_at DESC")
                users = [dict(r) for r in cursor.fetchall()]
            print(json.dumps({"success": True, "blacklist": users}))

        elif command == "add_blacklist":
            user_id = args.get("user_id")
            reason = args.get("reason", "تم الإضافة من لوحة التحكم على الويب")
            if not user_id or not str(user_id).isdigit():
                print(json.dumps({"error": "معرف المستخدم غير صحيح"}))
                return
            db.blacklist_user(
                user_id=int(user_id),
                reason=reason,
                added_by=0
            )
            print(json.dumps({"success": True, "message": "تم إضافة المستخدم إلى القائمة السوداء بنجاح"}))

        elif command == "remove_blacklist":
            user_id = args.get("user_id")
            if not user_id or not str(user_id).isdigit():
                print(json.dumps({"error": "معرف المستخدم غير صحيح"}))
                return
            db.unblacklist_user(user_id=int(user_id))
            print(json.dumps({"success": True, "message": "تم إزالة المستخدم من القائمة السوداء"}))

        elif command == "get_stats":
            stats = db.get_statistics()
            print(json.dumps({"success": True, "stats": stats}))

        elif command == "sync_commands":
            async def run_sync():
                import discord
                db_token = db.get_guild_setting(0, "bot_token")
                token = db_token or os.getenv("DISCORD_BOT_TOKEN") or Config.BOT_TOKEN
                if token:
                    token = token.strip().strip('"').strip("'")
                if not token or len(token) < 10:
                    return {"success": False, "error": "يرجى إدخال توكن البوت أولاً في الإعدادات"}

                from bot.main import TicketBot
                intents = discord.Intents.default()
                intents.message_content = True
                intents.members = True
                bot_instance = TicketBot(command_prefix="!", intents=intents)

                res = {"success": False, "error": "Unknown error during sync"}

                @bot_instance.event
                async def on_ready():
                    nonlocal res
                    try:
                        synced = await bot_instance.tree.sync()
                        guild_sync_count = 0
                        for guild in bot_instance.guilds:
                            try:
                                await bot_instance.tree.sync(guild=guild)
                                guild_sync_count += 1
                            except Exception:
                                pass
                        res = {
                            "success": True,
                            "message": f"تم تحديث ومزامنة {len(synced)} أمر سلاش (Slash Commands) بنجاح على مستوى ديسكورد و {guild_sync_count} سيرفر مرتبط!",
                            "synced_count": len(synced),
                            "bot_tag": str(bot_instance.user),
                            "guilds_count": len(bot_instance.guilds)
                        }
                    except Exception as ex:
                        res = {"success": False, "error": f"فشل مزامنة الأوامر: {str(ex)}"}
                    finally:
                        await bot_instance.close()

                try:
                    await bot_instance.start(token)
                except Exception as ex:
                    res = {"success": False, "error": f"فشل تسجيل دخول البوت لمزامنة الأوامر: {str(ex)}"}
                return res

            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(run_sync())
            print(json.dumps(result))

        else:
            print(json.dumps({"error": f"Unknown command: {command}"}))

    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    main()
