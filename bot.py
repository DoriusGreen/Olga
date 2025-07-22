import os
import logging
import openai
import requests

from telegram import Update, InputFile, MessageEntity
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters
)

# ------------------------------
# Змінні середовища
# ------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = "pNiaJ7NOaoIWnRJo2dZt"

# ------------------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

openai.api_key = OPENAI_API_KEY

# Промт Ольги
BASE_SYSTEM_PROMPT = (
    "Ти — Оля, 27 років, працівниця антикорупційного суду в Києві. "
    "Ти народилась 24 липня, 1998 року в смт Криве Озеро. "
    "Працювала в Укртелекомі, потім у Святошинському суді, зараз в Антикорупційному суді Києва. "
    "Не дуже любиш каву (хіба інколи латте), більше фруктовий чай, любиш тортики та солодке. "
    "З їжі — креветки й курку, обожнюєш нові заклади. В тебе є авто, ти непогано водиш. "
    "Відповідай українською у неформальному стилі, з емпатією й легким гумором, максимально 1–2 речення. "
    "Іноді у відповідному контексті можеш рідко вживати «блять» або «піздєц». "
)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    # визначаємо, чи в приваті, чи є згадка/реплай
    is_private = message.chat.type == "private"
    should_respond = is_private

    if not is_private:
        if message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id:
            should_respond = True
        elif message.entities:
            for entity in message.entities:
                if entity.type == MessageEntity.MENTION:
                    text_mention = message.text[entity.offset:entity.offset + entity.length]
                    if f"@{context.bot.username}".lower() in text_mention.lower():
                        should_respond = True
                        break

    if not should_respond:
        return

    user_text = message.text.replace(f"@{context.bot.username}", "").strip()

    messages = [
        {"role": "system", "content": BASE_SYSTEM_PROMPT},
        {"role": "user",   "content": user_text},
    ]

    # Генеруємо відповідь GPT
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=200,
            temperature=0.8,
            top_p=0.95
        )
        bot_reply = resp.choices[0].message.content
    except Exception as e:
        logging.error(f"OpenAI API Error: {e}")
        bot_reply = "Ой, щось пішло не так із GPT. Спробуй ще раз."

    # Спроба озвучки ElevenLabs
    try:
        tts_resp = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json"
            },
            json={
                "text": bot_reply,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.7,
                    "style": 0.4,
                    "use_speaker_boost": True,
                    "speed": 1.0
                }
            }
        )

        if tts_resp.status_code == 200:
            with open("voice.mp3", "wb") as f:
                f.write(tts_resp.content)
            with open("voice.mp3", "rb") as f:
                await message.reply_voice(voice=InputFile(f))
        else:
            logging.error(f"TTS Error: {tts_resp.status_code} {tts_resp.text}")
            await message.reply_text(bot_reply)

    except Exception as e:
        logging.error(f"TTS Generation Error: {e}")
        await message.reply_text(bot_reply)


def main():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Тільки один єдиний handler для тексту
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    # Запуск вебхука
    PORT = int(os.getenv("PORT", "8443"))
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="",         # або свій шлях
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    main()
