import os
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")

def extract_ref(text):
    match = re.search(r'\d{8}', text)
    if match:
        return match.group(0)
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "اهلا بك في بوت Mango Pricing\n"
        "استخدم الامر:\n/check رابط او ريفيرانس"
    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("البوت يعمل بنجاح")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:
        await update.message.reply_text("ارسل الرابط او الريفيرانس بعد الامر")
        return

    text = context.args[0]

    ref = extract_ref(text)

    if not ref:
        await update.message.reply_text("لم استطع استخراج الريفيرانس")
        return

    await update.message.reply_text(f"الريفيرانس المستخرج:\n{ref}")

def main():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("check", check))

    print("Bot started...")

    app.run_polling()

main()
