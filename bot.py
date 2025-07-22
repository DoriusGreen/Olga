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
# Завантаження змінних середовища
# ------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY       = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL          = os.getenv("WEBHOOK_URL")
ELEVENLABS_API_KEY   = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID             = "pNiaJ7NOaoIWnRJo2dZt"

# ------------------------------
# Налаштування логування
# ------------------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

openai.api_key = OPENAI_API_KEY

# ------------------------------
# Системний промт для стилю Олі
# ------------------------------
BASE_SYSTEM_PROMPT = (
    "Ти — Оля, 27 років, працівниця антикорупційного суду в Києві. "
    "Ти народилась 24 липня, 1998 року в смт Криве Озеро. "
    "Працювала в Укртелекомі, потім у Святошинському суді, зараз в Антикорупційному суді Києва. "
    "Не дуже любиш каву (хіба інколи латте), більше фруктовий чай, любиш тортики та солодке. "
    "З їжі — креветки й курку, обожнюєш нові заклади. В тебе є авто, ти непогано водиш. "
    "Відповідай українською у неформальному стилі, з емпатією й легким гумором, максимально 1–2 речення. "
    "Іноді у відповідному контексті можеш рідко вживати «блять» або «піздєц». "
)

# ------------------------------
# Обробник вхідних повідомлень
# ------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    # --------------------------
    # 1) Визначаємо, чи в особистому чаті
    # --------------------------
    is_private = message.chat.type == "private"
    should_respond = is_private

    # --------------------------
    # 2) Якщо не особистий чат — перевіряємо цитату або тег
    # --------------------------
    if not is_private:
        # відповідає, якщо хтось відповів на повідомлення бота
        if message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id:
            should_respond = True
        # відповідає, якщо в тексті є @бот
        elif message.entities:
            for entity in message.entities:
                if entity.type == MessageEntity.MENTION:
                    mention = message.text[entity.offset:entity.offset + entity.length]
                    if f"@{context.bot.username}".lower() in mention.lower():
                        should_respond = True
                        break

    if not should_respond:
        return

    # --------------------------
    # 3) Підготовка повідомлення для GPT
    # --------------------------
    user_text = message.text.replace(f"@{context.bot.username}", "").strip()
    messages = [
        {"role": "system", "content": BASE_SYSTEM_PROMPT},
        {"role": "user",   "content": user_text},
    ]

    # --------------------------
    # 4) Виклик OpenAI для генерації відповіді
    # --------------------------
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

    # --------------------------
    # 5) Спроба озвучити відповідь через ElevenLabs
    # --------------------------
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
            # надсилаємо голосове повідомлення
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

# ------------------------------
# Старт та запуск бота
# ------------------------------
def main():
    # Ініціалізація Telegram-додатку
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Додаємо обробник тільки для текстових повідомлень (без команд)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    # Запускаємо вебхук на вказаному порту і URL
    PORT = int(os.getenv("PORT", "8443"))
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="",         # тут можна вказати свій шлях
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    main()
