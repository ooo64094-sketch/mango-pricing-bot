import os
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")

def extract_ref(text):
    match = re.search(r'_(\d{8})|\b(\d{8})\b', text)
    if match:
        return match.group(1) or match.group(2)
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("start ok")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ping ok")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("اكتب /check ثم الريفيرانس أو الرابط")
        return

    text = " ".join(context.args).strip()
    ref_code = extract_ref(text)

    if not ref_code:
        await update.message.reply_text("لم استطع استخراج الريفيرانس")
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
