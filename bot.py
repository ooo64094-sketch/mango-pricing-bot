import os
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")

def extract_ref(text):
    patterns = [
        r'_(\d{8})',      # الرقم بعد _
        r'\b(\d{8})\b'    # الرقم لوحده
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)

    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "اهلا بك في بوت Mango Pricing\n"
        "استخدم:\n"
        "/check ريفيرانس او رابط"
    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("البوت يعمل بنجاح")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ارسل الريفيرانس او الرابط بعد /check")
        return

    text = " ".join(context.args).strip()
    ref_code = extract_ref(text)

    if not ref_code:
        await update.message.reply_text("لم استطع استخراج REF من الرابط او النص")
        return

    await update.message.reply_text(f"الريفيرانس المستخرج:\n{ref_code}")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("check", check))

    print("Bot started...")
    app.run_polling()

main()
