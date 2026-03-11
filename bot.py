import os
import re
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

USD_TO_IQD = 1300

def extract_ref(text):
    match = re.search(r'\b(\d{8})\b', text)
    if match:
        return match.group(1)
    return None

def get_mango_price(ref):
    url = f"https://shop.mango.com/tr/search?q={ref}"

    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, "lxml")

        price_tag = soup.find("span", {"class": "price"})
        if price_tag:
            price_text = price_tag.text.strip()
            price = re.findall(r'\d+', price_text)[0]
            return int(price)

    except:
        return None

    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "بوت تسعير Mango\n"
        "استخدم:\n"
        "/check REF او رابط"
    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("البوت يعمل بنجاح")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:
        await update.message.reply_text("ارسل الريفيرانس او الرابط")
        return

    text = " ".join(context.args)

    ref = extract_ref(text)

    if not ref:
        await update.message.reply_text("لم استطع استخراج REF")
        return

    price_tr = get_mango_price(ref)

    if not price_tr:
        await update.message.reply_text(
            f"REF: {ref}\n"
            "لم استطع جلب السعر"
        )
        return

    price_usd = price_tr / 30
    price_iqd = int(price_usd * USD_TO_IQD)

    sell_price = int(price_iqd * 1.4)

    await update.message.reply_text(
        f"REF: {ref}\n\n"
        f"🇹🇷 سعر تركيا: {price_tr} TL\n"
        f"💵 السعر بالدولار: {round(price_usd,2)}\n"
        f"🇮🇶 التكلفة: {price_iqd} دينار\n\n"
        f"💰 سعر البيع المقترح:\n{sell_price} دينار"
    )

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("check", check))

    print("Bot running...")
    app.run_polling()

main()
