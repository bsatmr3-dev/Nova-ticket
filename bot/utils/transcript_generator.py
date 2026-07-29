import os
import html
from typing import List
import discord

class TranscriptGenerator:
    @staticmethod
    async def generate_html(channel: discord.TextChannel, ticket_info: dict = None) -> str:
        messages: List[discord.Message] = []
        async for msg in channel.history(limit=1000, oldest_first=True):
            messages.append(msg)

        ticket_id = ticket_info.get("id", channel.name) if ticket_info else channel.name
        user_name = ticket_info.get("user_id", "Unknown User") if ticket_info else "User"

        messages_html = ""
        for m in messages:
            author_name = html.escape(m.author.display_name)
            avatar_url = m.author.display_avatar.url
            timestamp = m.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            content = html.escape(m.content) if m.content else ""
            bot_badge = '<span class="bot-badge">BOT</span>' if m.author.bot else ""

            # Attachments
            attachments_html = ""
            for att in m.attachments:
                if att.content_type and "image" in att.content_type:
                    attachments_html += f'<div class="attachment"><img src="{att.url}" alt="image" style="max-width:350px; border-radius:8px; margin-top:6px;" /></div>'
                else:
                    attachments_html += f'<div class="attachment"><a href="{att.url}" target="_blank" style="color:#00b0f4; text-decoration:underline;">📎 {html.escape(att.filename)}</a></div>'

            # Embeds
            embeds_html = ""
            for emb in m.embeds:
                emb_title = html.escape(emb.title) if emb.title else ""
                emb_desc = html.escape(emb.description) if emb.description else ""
                emb_color = f"{emb.color.value:06x}" if emb.color else "5865f2"
                embeds_html += f'''
                <div class="embed-box" style="border-left: 4px solid #{emb_color};">
                    {f'<div class="embed-title">{emb_title}</div>' if emb_title else ''}
                    {f'<div class="embed-desc">{emb_desc}</div>' if emb_desc else ''}
                </div>
                '''

            messages_html += f'''
            <div class="chat-message">
                <img class="avatar" src="{avatar_url}" alt="avatar" />
                <div class="message-body">
                    <div class="message-header">
                        <span class="author">{author_name}</span> {bot_badge}
                        <span class="timestamp">{timestamp}</span>
                    </div>
                    <div class="content">{content}</div>
                    {embeds_html}
                    {attachments_html}
                </div>
            </div>
            '''

        html_template = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Transcript #{ticket_id}</title>
    <style>
        body {{
            background-color: #313338;
            color: #dbdee1;
            font-family: 'gg sans', 'Noto Sans', 'Helvetica Neue', Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 20px;
        }}
        .header-bar {{
            background-color: #2b2d31;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 24px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            border: 1px solid #1e1f22;
        }}
        .header-title {{
            font-size: 24px;
            font-weight: 700;
            color: #ffffff;
            margin: 0 0 8px 0;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .header-meta {{
            font-size: 14px;
            color: #949ba4;
        }}
        .chat-container {{
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}
        .chat-message {{
            display: flex;
            gap: 16px;
            padding: 8px 12px;
            border-radius: 8px;
            transition: background 0.2s ease;
        }}
        .chat-message:hover {{
            background-color: #2e3035;
        }}
        .avatar {{
            width: 42px;
            height: 42px;
            border-radius: 50%;
            object-fit: cover;
        }}
        .message-body {{
            display: flex;
            flex-direction: column;
            flex: 1;
        }}
        .message-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 4px;
        }}
        .author {{
            font-weight: 600;
            color: #f2f3f5;
            font-size: 15px;
        }}
        .bot-badge {{
            background-color: #5865f2;
            color: #ffffff;
            font-size: 10px;
            font-weight: 700;
            padding: 2px 5px;
            border-radius: 4px;
        }}
        .timestamp {{
            font-size: 12px;
            color: #949ba4;
        }}
        .content {{
            font-size: 15px;
            line-height: 1.4;
            color: #dbdee1;
            white-space: pre-wrap;
        }}
        .embed-box {{
            background-color: #2b2d31;
            padding: 12px;
            border-radius: 6px;
            margin-top: 8px;
            max-width: 520px;
        }}
        .embed-title {{
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 6px;
        }}
        .embed-desc {{
            font-size: 14px;
            color: #b5bac1;
        }}
        .footer-note {{
            margin-top: 40px;
            text-align: center;
            font-size: 13px;
            color: #80848e;
            border-top: 1px solid #3f4147;
            padding-top: 16px;
        }}
    </style>
</head>
<body>
    <div class="header-bar">
        <div class="header-title">🎫 Discord Ticket Transcript #{ticket_id}</div>
        <div class="header-meta">
            Channel: #{channel.name} | Messages: {len(messages)} | Saved on: {discord.utils.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}
        </div>
    </div>
    <div class="chat-container">
        {messages_html}
    </div>
    <div class="footer-note">
        Generated by Discord Advanced Ticket System • All Rights Reserved
    </div>
</body>
</html>'''
        return html_template
