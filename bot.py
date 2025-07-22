import os
import logging
import openai
import requests

from telegram import Update, InputFile, MessageEntity
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
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
    "Відповідай українською у неформальному стилі, інколи можна і суржиком, з емпатією й легким гумором, максимально 1–2 речення. "
    "Іноді у відповідному контексті можеш рідко вживати «блять» або «піздєц»."
)



async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if message is None:
        return

    is_private = message.chat.type == "private"

    should_respond = is_private

    if not is_private:
        if message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id:
            should_respond = True
        elif message.entities:
            for entity in message.entities:
                if entity.type == MessageEntity.MENTION:
                    mentioned_text = message.text[entity.offset:entity.offset + entity.length]
                    if f"@{context.bot.username}".lower() in mentioned_text.lower():
                        should_respond = True
                        break

    if not should_respond:
        return

    user_text = message.text.replace(f"@{context.bot.username}", "").strip()

    messages = [
        {"role": "system", "content": BASE_SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=300,
            temperature=0.8,
            top_p=0.95
        )
        bot_reply = response["choices"][0]["message"]["content"]
    except Exception as e:
        logging.error(f"OpenAI API Error: {e}")
        bot_reply = "На жаль, сталося щось дивне у чарівному ефірі. Спробуй ще раз, друже."

    try:
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        }
        tts_data = {
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

        tts_response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
            headers=headers,
            json=tts_data
        )

        if tts_response.status_code == 200:
            audio_path = "dumbledore_voice.mp3"
            with open(audio_path, "wb") as f:
                f.write(tts_response.content)
            with open(audio_path, "rb") as audio_file:
                await message.reply_voice(voice=InputFile(audio_file))
        else:
            logging.error(f"TTS Error: {tts_response.status_code}, {tts_response.text}")
            await message.reply_text(bot_reply)

    except Exception as e:
        logging.error(f"TTS Generation Error: {e}")
        await message.reply_text(bot_reply)


def main():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    PORT = int(os.getenv("PORT", "8443"))
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="",
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    main()
