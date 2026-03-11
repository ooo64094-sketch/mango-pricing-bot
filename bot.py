import os
import re
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SERPAPI_KEY = os.environ.get("SERPAPI_KEY")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9,tr;q=0.8,ar;q=0.7",
}

def get_html(url):
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    return r.text

def extract_ref(text):
    match = re.search(r'_(\d{8})|\b(\d{8})\b', text)
    if match:
        return match.group(1) or match.group(2)
    return None

def parse_price(raw):
    raw = raw.replace(",", "").replace(".", "").strip()
    try:
        return int(raw)
    except:
        return None

def extract_turkey_price(html):
    patterns = [
        r'(\d[\d\.,]{1,})\s*TL',
        r'(\d[\d\.,]{1,})\s*₺'
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for m in matches:
            val = parse_price(m)
            if val:
                return val

    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            val = parse_price(m)
            if val:
                return val

    return None

def extract_iqd_price(html):
    patterns = [
        r'(\d[\d,\.]{1,})\s*IQD',
        r'IQD\s*(\d[\d,\.]{1,})'
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for m in matches:
            val = parse_price(m)
            if val:
                return val

    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            val = parse_price(m)
            if val:
                return val

    return None

def find_iraq_price(ref):
    params = {
        "engine": "google",
        "q": f"site:shop.mango.com/iq/en {ref}",
        "api_key": SERPAPI_KEY
    }

    try:
        r = requests.get("https://serpapi.com/search", params=params)
        data = r.json()

        results = data.get("organic_results", [])

        for res in results:
            link = res.get("link")

            if "shop.mango.com/iq" in link:
                try:
                    html = get_html(link)
                    price = extract_iqd_price(html)
                    if price:
                        return price
                except:
                    pass
    except:
        pass

    return None

def turkey_to_iqd(price_try):
    return round((price_try / 4300) * 140000)

def flexible_base_load(diff):
    if diff <= 5000:
        return 0

    load = diff * 0.45
    return round(load / 1000) * 1000

def round_sale_price(raw_price):
    remainder = raw_price % 1000

    if remainder == 0:
        return raw_price + 500
    elif remainder <= 499:
        return raw_price + (500 - remainder)
    else:
        return raw_price + (1000 - remainder)

def calculate(price_try, iraq_price):
    cost_iqd = turkey_to_iqd(price_try)

    diff = iraq_price - cost_iqd

    if diff <= 0:
        sale_price = round_sale_price(cost_iqd)
        total_load = sale_price - cost_iqd
    else:
        base_load = flexible_base_load(diff)
        raw_sale = cost_iqd + base_load
        sale_price = round_sale_price(raw_sale)
        total_load = sale_price - cost_iqd

    return cost_iqd, diff, total_load, sale_price

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "بوت تسعيرة مانكو\n\n"
        "استخدم:\n"
        "/check رابط المنتج التركي"
    )

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:
        await update.message.reply_text("ارسل رابط Mango تركيا بعد /check")
        return

    url = context.args[0]

    await update.message.reply_text("جاري الفحص...")

    try:

        html = get_html(url)

        ref = extract_ref(url)
        if not ref:
            ref = extract_ref(html)

        if not ref:
            await update.message.reply_text("لم استطع استخراج الريفيرانس")
            return

        turkey_price = extract_turkey_price(html)

        if not turkey_price:
            await update.message.reply_text("لم استطع جلب سعر تركيا")
            return

        iraq_price = find_iraq_price(ref)

        if not iraq_price:
            cost_iqd = turkey_to_iqd(turkey_price)

            await update.message.reply_text(
                f"الريفيرانس: {ref}\n\n"
                f"سعر تركيا: {turkey_price} ليرة\n"
                f"التكلفة بالعراقي: {cost_iqd}\n\n"
                "لم استطع جلب سعر العراق حالياً"
            )
            return

        cost_iqd, diff, load, sale = calculate(turkey_price, iraq_price)

        await update.message.reply_text(
            f"الريفيرانس: {ref}\n\n"
            f"سعر تركيا: {turkey_price} ليرة\n"
            f"التكلفة بالعراقي: {cost_iqd}\n\n"
            f"سعر العراق: {iraq_price}\n"
            f"الفرق: {diff}\n\n"
            f"إجمالي التحميل: {load}\n"
            f"سعر البيع: {sale}"
        )

    except Exception as e:
        await update.message.reply_text(f"خطأ:\n{str(e)}")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check))

    print("Bot started")

    app.run_polling()

main()
