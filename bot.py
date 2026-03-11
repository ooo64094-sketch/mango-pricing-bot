import os
import re
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9,tr;q=0.8,ar;q=0.7",
}


def extract_ref(text):
    match = re.search(r'_(\d{8})|\b(\d{8})\b', text)
    if match:
        return match.group(1) or match.group(2)
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

    return {
        "cost_iqd": cost_iqd,
        "iraq_price": iraq_price,
        "diff": diff,
        "total_load": total_load,
        "sale_price": sale_price
    }


def get_html(url):
    response = requests.get(url, headers=HEADERS, timeout=25)
    response.raise_for_status()
    return response.text


def parse_iqd_value(raw):
    raw = raw.strip()
    raw = raw.replace(",", "").replace(".", "")
    try:
        return int(raw)
    except:
        return None


def search_iraq_price_by_ref(ref_code):
    search_urls = [
        f"https://shop.mango.com/iq/en/search/{ref_code}",
        f"https://shop.mango.com/iq/en/search?q={ref_code}",
    ]

    patterns = [
        r'(\d[\d,\.]{2,})\s*IQD',
        r'IQD\s*(\d[\d,\.]{2,})',
    ]

    for url in search_urls:
        try:
            html = get_html(url)

            # 1) البحث في HTML الخام
            for pattern in patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                for m in matches:
                    value = parse_iqd_value(m)
                    if value:
                        return value

            # 2) البحث في النص الظاهر
            soup = BeautifulSoup(html, "lxml")
            text = soup.get_text(" ", strip=True)

            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for m in matches:
                    value = parse_iqd_value(m)
                    if value:
                        return value

        except:
            continue

    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "بوت تسعيرة مانكو\n\n"
        "الاوامر:\n"
        "/check رابط أو ريفيرانس\n"
        "/quote سعر_تركيا سعر_العراق رابط_أو_ريفيرانس\n"
        "/iraq ريفيرانس\n\n"
        "مثال:\n"
        "/iraq 27071311"
    )


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong")


async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ارسل الرابط أو الريفيرانس بعد /check")
        return

    text = " ".join(context.args).strip()
    ref_code = extract_ref(text)

    if not ref_code:
        await update.message.reply_text("لم استطع استخراج الريفيرانس")
        return

    await update.message.reply_text(f"الريفيرانس المستخرج:\n{ref_code}")


async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text(
            "استخدم:\n"
            "/quote سعر_تركيا سعر_العراق رابط_أو_ريفيرانس\n\n"
            "مثال:\n"
            "/quote 2000 74000 27071311"
        )
        return

    try:
        price_try = float(context.args[0])
        iraq_price = int(float(context.args[1]))
    except ValueError:
        await update.message.reply_text("سعر تركيا أو سعر العراق غير صحيح")
        return

    ref_input = " ".join(context.args[2:]).strip()
    ref_code = extract_ref(ref_input)

    if not ref_code:
        await update.message.reply_text("لم استطع استخراج الريفيرانس")
        return

    result = calculate_quote(price_try, iraq_price)

    await update.message.reply_text(
        f"الريفيرانس: {ref_code}\n\n"
        f"سعر تركيا: {int(price_try)} ليرة\n"
        f"التكلفة بالعراقي: {result['cost_iqd']}\n\n"
        f"سعر العراق: {result['iraq_price']}\n"
        f"الفرق: {result['diff']}\n\n"
        f"إجمالي التحميل: {result['total_load']}\n"
        f"سعر البيع: {result['sale_price']}"
    )


async def iraq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("استخدم:\n/iraq 27071311")
        return

    text = " ".join(context.args).strip()
    ref_code = extract_ref(text)

    if not ref_code:
        await update.message.reply_text("لم استطع استخراج الريفيرانس")
        return

    await update.message.reply_text("جاري البحث في Mango العراق...")

    iraq_price = search_iraq_price_by_ref(ref_code)

    if not iraq_price:
        await update.message.reply_text(
            f"الريفيرانس: {ref_code}\n"
            "لم استطع جلب سعر العراق حالياً"
        )
        return

    await update.message.reply_text(
        f"الريفيرانس: {ref_code}\n"
        f"سعر Mango العراق: {iraq_price}"
    )


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CommandHandler("quote", quote))
    app.add_handler(CommandHandler("iraq", iraq))

    print("Bot started...")
    app.run_polling()


main()
