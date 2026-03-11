import os
import re
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

TOKEN = os.environ.get("BOT_TOKEN")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9,tr;q=0.8,ar;q=0.7",
}


# استخراج الريفيرانس
def extract_ref(text):
    match = re.search(r'_(\d{8})|\b(\d{8})\b', text)
    if match:
        return match.group(1) or match.group(2)
    return None


# جلب HTML
def get_html(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


# جلب سعر تركيا
def get_turkey_price(url):
    html = get_html(url)

    patterns = [
        r'(\d[\d\.]+,\d{2})\s*TL',
        r'(\d[\d\.]+)\s*TL'
    ]

    for p in patterns:
        m = re.search(p, html)
        if m:
            raw = m.group(1)
            raw = raw.replace(".", "").replace(",", ".")
            return float(raw)

    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)

    for p in patterns:
        m = re.search(p, text)
        if m:
            raw = m.group(1)
            raw = raw.replace(".", "").replace(",", ".")
            return float(raw)

    return None


# تحويل الليرة للعراقي
def turkey_to_iqd(price_try):
    return round((price_try / 4300) * 140000)


# حساب التحميل
def flexible_base_load(diff):
    if diff <= 5000:
        return 0
    load = diff * 0.45
    return round(load / 1000) * 1000


# تقريب السعر
def round_sale_price(raw_price):
    remainder = raw_price % 1000

    if remainder == 0:
        return raw_price + 500
    elif remainder <= 499:
        return raw_price + (500 - remainder)
    else:
        return raw_price + (1000 - remainder)


# حساب التسعيرة
def calculate_quote(price_try, iraq_price):
    cost_iqd = turkey_to_iqd(price_try)
    diff = iraq_price - cost_iqd

    if diff <= 0:
        sale_price = round_sale_price(cost_iqd)
        total_load = sale_price - cost_iqd
    else:
        base_load = flexible_base_load(diff)
        raw_sale_price = cost_iqd + base_load
        sale_price = round_sale_price(raw_sale_price)
        total_load = sale_price - cost_iqd

    return cost_iqd, diff, total_load, sale_price


# جلب سعر العراق
def get_iraq_price(ref):
    urls = [
        f"https://shop.mango.com/iq/en/search/{ref}",
        f"https://shop.mango.com/iq/en/search?q={ref}"
    ]

    patterns = [
        r'(\d[\d,\.]+)\s*IQD',
        r'IQD\s*(\d[\d,\.]+)'
    ]

    for url in urls:
        try:
            html = get_html(url)

            for p in patterns:
                m = re.findall(p, html)
                for price in m:
                    price = price.replace(",", "").replace(".", "")
                    return int(price)

            soup = BeautifulSoup(html, "lxml")
            text = soup.get_text(" ", strip=True)

            for p in patterns:
                m = re.findall(p, text)
                for price in m:
                    price = price.replace(",", "").replace(".", "")
                    return int(price)

        except:
            continue

    return None


# أمر البداية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "بوت تسعير Mango\n\n"
        "ارسل فقط:\n"
        "• رابط Mango تركيا\n"
        "أو\n"
        "• الريفيرانس\n\n"
        "وسيتم جلب السعر تلقائياً."
    )


# معالجة الرسائل
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text.strip()

    ref = extract_ref(text)

    if not ref:
        await update.message.reply_text("لم أستطع استخراج الريفيرانس")
        return

    await update.message.reply_text("جاري الفحص...")

    # سعر تركيا
    turkey_price = None
    if "mango.com" in text:
        turkey_price = get_turkey_price(text)

    # سعر العراق
    iraq_price = get_iraq_price(ref)

    if not iraq_price:
        await update.message.reply_text("لم أستطع جلب سعر Mango العراق")
        return

    if not turkey_price:
        await update.message.reply_text(
            f"الريفيرانس: {ref}\n"
            f"سعر العراق: {iraq_price}"
        )
        return

    cost_iqd, diff, load, sale_price = calculate_quote(turkey_price, iraq_price)

    msg = (
        f"الريفيرانس: {ref}\n\n"
        f"سعر تركيا: {int(turkey_price)} ليرة\n"
        f"التكلفة بالعراقي: {cost_iqd}\n\n"
        f"سعر العراق: {iraq_price}\n"
        f"الفرق: {diff}\n\n"
        f"إجمالي التحميل: {load}\n"
        f"سعر البيع: {sale_price}"
    )

    await update.message.reply_text(msg)


# تشغيل البوت
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot started...")
    app.run_polling()


main()
