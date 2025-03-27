import os
import asyncio
from dotenv import load_dotenv
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes
)
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from openai import OpenAI

# --- Настройка ---
load_dotenv()

TELEGRAM_TOKEN = os.getenv("telegram_api_key")
client = OpenAI(
    base_url=os.getenv("base_url"),
    api_key=os.getenv("gemeni_api_key")
)

MAX_USERS = 30
chat_histories = {}

MANUAL_MEMBERS = [
    "@qweerbecouse",
    "@Depparain",
    "@vlgogolev1",
    "@alexander_korotkunov",
    "@NMihail535",
    "@grmaree",
    "@shro5k",
    "@iamllesya",
    "@TractoristZ",
    "@hugrollz",
    "@GeorTon",
    "@ahmedn23",
    "@haggag_ru",
    "@GGWPHENTA1"
]

# --- Удаление сообщения через delay ---
async def auto_delete(bot, chat_id, message_id, delay):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, message_id)
    except:
        pass

# --- DeepSeek: ответ ---
async def handle_deepseek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text.lower().startswith("deepseek:"):
        return

    prompt = msg.text[len("deepseek:"):].strip()
    thread_id = msg.message_thread_id or 0
    chat_id = msg.chat_id
    key = f"{chat_id}:{thread_id}"

    chat_histories.setdefault(key, [])
    chat_histories[key].append({"role": "user", "content": prompt})

    try:
        response = client.chat.completions.create(
            model="deepseek/deepseek-r1:free",
            messages=chat_histories[key]
        )

        reply = response.choices[0].message.content
        reply = reply.replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')

        chat_histories[key].append({"role": "assistant", "content": reply})

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("♻️ Повторить", callback_data=f"repeat:{key}"),
             InlineKeyboardButton("🧹 Очистить", callback_data=f"clear:{key}")]
        ])

        sent = await msg.reply_text(
            f"🧠 *DeepSeek говорит:*\n\n{reply}",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=keyboard,
            message_thread_id=thread_id
        )

        # Удалить через 120 сек
        asyncio.create_task(auto_delete(context.bot, sent.chat_id, sent.message_id, 120))

    except Exception as e:
        err_msg = await msg.reply_text(
            f"❌ Ошибка: `{str(e)}`",
            parse_mode=ParseMode.MARKDOWN_V2,
            message_thread_id=thread_id
        )
        # Удалить через 30 сек
        asyncio.create_task(auto_delete(context.bot, err_msg.chat_id, err_msg.message_id, 30))

# --- @all: упомянуть всех ---
async def handle_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or "@all" not in msg.text.lower():
        return

    thread_id = msg.message_thread_id
    members = MANUAL_MEMBERS

    chunks = [members[i:i+MAX_USERS] for i in range(0, len(members), MAX_USERS)]
    for chunk in chunks:
        text = " ".join(chunk)
        header = "📣 *Упоминание всех:*"
        extra_text = msg.text.split("@all", 1)[-1].strip()
        if extra_text:
            extra_text = escape_markdown(extra_text, version=2)
            text = f"{header}\n{text}\n\n_по запросу: {extra_text}_"
        else:
            text = f"{header}\n{text}"

        await msg.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN_V2,
            message_thread_id=thread_id
        )
        # ВНИМАНИЕ: @all сообщение НЕ удаляется

# --- Кнопки: Повтор / Очистить ---
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    action, key = data.split(":", 1)

    if action == "repeat":
        history = chat_histories.get(key, [])
        if not history:
            await query.edit_message_text("🕳 История пуста.")
            return

        try:
            response = client.chat.completions.create(
                model="deepseek/deepseek-r1:free",
                messages=history
            )
            reply = response.choices[0].message.content
            reply = reply.replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')

            chat_histories[key].append({"role": "assistant", "content": reply})

            await query.edit_message_text(
                f"🔁 *DeepSeek повторил:*\n\n{reply}",
                parse_mode=ParseMode.MARKDOWN_V2
            )

            # Повтор тоже удалим через 120 сек
            asyncio.create_task(auto_delete(context.bot, query.message.chat_id, query.message.message_id, 120))

        except Exception as e:
            await query.edit_message_text(
                f"❌ Ошибка: `{str(e)}`",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            asyncio.create_task(auto_delete(context.bot, query.message.chat_id, query.message.message_id, 30))

    elif action == "clear":
        chat_histories[key] = []
        await query.edit_message_text("🧹 Контекст очищен!")
        asyncio.create_task(auto_delete(context.bot, query.message.chat_id, query.message.message_id, 30))

# --- Старт бота ---
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.Regex("^deepseek:"), handle_deepseek))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_all))
    app.add_handler(CallbackQueryHandler(handle_buttons))

    print("🤖 Бот запущен и ждёт сообщений...")
    app.run_polling()

if __name__ == "__main__":
    main()