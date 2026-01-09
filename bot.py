import discord
import aiohttp
import os
from datetime import datetime, timezone, timedelta
from deep_translator import GoogleTranslator
import re

# ============ 환경변수 설정 ============
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID"))

# ============ 초기화 ============
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

client = discord.Client(intents=intents)

# 한국어 감지 함수
def is_korean(text):
    if not text:
        return True
    korean_pattern = re.compile('[가-힣]')
    korean_chars = len(korean_pattern.findall(text))
    return korean_chars / max(len(text.replace(" ", "")), 1) > 0.3

# 번역 함수
def translate_to_korean(text):
    if not text or is_korean(text):
        return None
    try:
        translator = GoogleTranslator(source='auto', target='ko')
        return translator.translate(text)
    except Exception as e:
        print(f"번역 오류: {e}")
        return None

# UTC → KST 변환
def to_kst(dt):
    kst = timezone(timedelta(hours=9))
    return dt.astimezone(kst).strftime("%Y-%m-%d, %H:%M (KST)")

# Discord 메시지 URL 생성
def get_message_url(message):
    return f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"

# Slack 메시지 전송
async def send_to_slack(message):
    content = message.content or ""
    korean_translation = translate_to_korean(content)
    
    if korean_translation:
        content_block = f"원문:\n{content}\n\n국문:\n{korean_translation}"
    else:
        content_block = content if content else "(내용 없음)"
    
    # 첨부 파일 처리
    image_urls = []
    file_urls = []
    
    for att in message.attachments:
        if att.content_type and att.content_type.startswith("image"):
            image_urls.append(att.url)
        else:
            file_urls.append(f"<{att.url}|{att.filename}> ({att.size} bytes)")
    
    # Slack Block Kit 메시지 구성
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🔔 Discord 제보 알림 🔔",
                "emoji": True
            }
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*1. 채널:*\n🩴 {message.channel.name}"},
                {"type": "mrkdwn", "text": f"*2. 작성자:*\n{message.author.display_name}"}
            ]
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*3. 시간:*\n{to_kst(message.created_at)}"}
            ]
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*4. 내용:*\n{content_block}"}
        }
    ]
    
    # 첨부 파일 섹션
    if file_urls:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*5. 첨부 파일:*\n📎 " + "\n📎 ".join(file_urls)}
        })
    else:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*5. 첨부 파일:*\n(없음)"}
        })
    
    # 이미지 섹션
    if image_urls:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*6. 이미지/미디어:*"}
        })
        for img_url in image_urls:
            blocks.append({
                "type": "image",
                "image_url": img_url,
                "alt_text": "첨부 이미지"
            })
    else:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*6. 이미지/미디어:*\n(없음)"}
        })
    
    # 원본 링크
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"🔗 <{get_message_url(message)}|원본 Discord 메시지 보기>"
        }
    })
    
    # Slack으로 전송
    payload = {"blocks": blocks}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(SLACK_WEBHOOK_URL, json=payload) as resp:
            if resp.status == 200:
                print(f"✅ Slack 전송 성공: {message.id}")
            else:
                print(f"❌ Slack 전송 실패: {resp.status}")

# 메시지 수신 이벤트
@client.event
async def on_message(message):
    if message.author.bot:
        return
    
    if message.channel.id != TARGET_CHANNEL_ID:
        return
    
    print(f"📨 새 메시지 감지: {message.channel.name} - {message.author.display_name}")
    await send_to_slack(message)

@client.event
async def on_ready():
    print(f"✅ 봇 로그인 완료: {client.user}")
    print(f"📡 모니터링 채널 ID: {TARGET_CHANNEL_ID}")

if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
