import os
import re
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SERPAPI_KEY = os.environ.get("SERPAPI_KEY")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9,tr;q=0.8,ar;q=0.7",
}


def extract_ref(text: str):
    match = re.search(r'_(\d{8})|\b(\d{8})\b', text)
    if match:
        return match.group(1) or match.group(2)
    return None


def serp_search(query: str):
    if not SERPAPI_KEY:
        return {}

    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_KEY,
        "hl": "en",
        "gl": "us",
        "num": 10,
    }

    try:
        r = requests.get("https://serpapi.com/search", params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}


def get_html(url: str):
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def parse_try_value(raw: str):
    raw = raw.strip().replace("\xa0", " ").replace(" ", "")
    raw = raw.replace("TL", "").replace("₺", "")

    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    else:
        raw = raw.replace(",", ".")

    try:
        return float(raw)
    except Exception:
        return None


def parse_iqd_value(raw: str):
    raw = raw.strip().replace("\xa0", " ").replace(" ", "")

    if "," in raw and "." in raw:
        if raw.rfind(".") > raw.rfind(","):
            raw = raw.replace(",", "")
            raw = raw.split(".")[0]
        else:
            raw = raw.replace(".", "")
            raw = raw.split(",")[0]
    else:
        if raw.count(",") == 1 and len(raw.split(",")[-1]) == 2:
            raw = raw.split(",")[0]
        elif raw.count(".") == 1 and len(raw.split(".")[-1]) == 2:
            raw = raw.split(".")[0]
        else:
            raw = raw.replace(",", "").replace(".", "")

    try:
        return int(raw)
    except Exception:
        return None


def turkey_to_iqd(price_try: float):
    return round((price_try / 4300) * 140000)


def flexible_base_load(diff: int):
    if diff <= 5000:
        return 0

    load = diff * 0.45
    return round(load / 1000) * 1000


def round_sale_price(raw_price: int):
    remainder = raw_price % 1000

    if remainder == 0:
        return raw_price + 500
    elif remainder <= 499:
        return raw_price + (500 - remainder)
    else:
        return raw_price + (1000 - remainder)


def calculate_quote(price_try: float, iraq_price: int):
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


def extract_turkey_price_from_serp(ref_code: str):
    queries = [
        f"Mango {ref_code} TL",
        f"site:shop.mango.com/tr/tr {ref_code} TL",
        f"{ref_code} Mango Türkiye fiyat",
    ]

    patterns = [
        r'(\d[\d\.]+,\d{2})\s*TL',
        r'(\d[\d\.]+)\s*TL',
        r'₺\s*(\d[\d\.,]+)',
    ]

    for query in queries:
        data = serp_search(query)
        if not data:
            continue

        text = str(data)

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                value = parse_try_value(str(m))
                if value and 10 <= value <= 100000:
                    return value

        for item in data.get("organic_results", []):
            snippet = f"{item.get('title', '')} {item.get('snippet', '')}"
            for pattern in patterns:
                matches = re.findall(pattern, snippet, re.IGNORECASE)
                for m in matches:
                    value = parse_try_value(str(m))
                    if value and 10 <= value <= 100000:
                        return value

    return None


def extract_iqd_price_from_html(html: str):
    patterns = [
        r'IQD\s*([0-9][0-9,\.]{2,})',
        r'([0-9][0-9,\.]{2,})\s*IQD',
    ]

    candidates = []

    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for m in matches:
            value = parse_iqd_value(m)
            if value and 5000 <= value <= 2000000:
                candidates.append(value)

    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            value = parse_iqd_value(m)
            if value and 5000 <= value <= 2000000:
                candidates.append(value)

    if not candidates:
        return None

    return min(candidates)


def extract_iraq_price_from_serp(ref_code: str):
    queries = [
        f"site:shop.mango.com/iq/en {ref_code} IQD",
        f"Mango {ref_code} IQD",
        f"{ref_code} Mango Iraq price",
    ]

    patterns = [
        r'IQD\s*([0-9][0-9,\.]{2,})',
        r'([0-9][0-9,\.]{2,})\s*IQD',
    ]

    for query in queries:
        data = serp_search(query)
        if not data:
            continue

        text = str(data)

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                value = parse_iqd_value(str(m))
                if value and 5000 <= value <= 2000000:
                    return value

        for item in data.get("organic_results", []):
            snippet = f"{item.get('title', '')} {item.get('snippet', '')}"
            for pattern in patterns:
                matches = re.findall(pattern, snippet, re.IGNORECASE)
                for m in matches:
                    value = parse_iqd_value(str(m))
                    if value and 5000 <= value <= 2000000:
                        return value

    return None


def search_iraq_price_by_ref(ref_code: str):
    serp_price = extract_iraq_price_from_serp(ref_code)
    if serp_price:
        return serp_price

    search_urls = [
        f"https://shop.mango.com/iq/en/search/{ref_code}",
        f"https://shop.mango.com/iq/en/search?q={ref_code}",
    ]

    for url in search_urls:
        try:
            html = get_html(url)
            price = extract_iqd_price_from_html(html)
            if price:
                return price
        except Exception:
            continue

    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "بوت تسعيرة Mango\n\n"
        "ارسل فقط:\n"
        "• رابط Mango تركيا\n"
        "أو\n"
        "• الريفيرانس\n\n"
        "وسيتم الفحص تلقائياً.\n\n"
        "أوامر إضافية:\n"
        "/iraq 27071311\n"
        "/quote 2000 74000 27071311"
    )


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong")


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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    if not text:
        return

    ref_code = extract_ref(text)

    if not ref_code:
        await update.message.reply_text("لم أستطع استخراج الريفيرانس")
        return

    await update.message.reply_text("جاري الفحص...")

    turkey_price = extract_turkey_price_from_serp(ref_code)
    iraq_price = search_iraq_price_by_ref(ref_code)

    if not iraq_price and not turkey_price:
        await update.message.reply_text(
            f"الريفيرانس: {ref_code}\n"
            "لم استطع جلب سعر تركيا ولا سعر العراق حالياً"
        )
        return

    if turkey_price and iraq_price:
        result = calculate_quote(turkey_price, iraq_price)

        await update.message.reply_text(
            f"الريفيرانس: {ref_code}\n\n"
            f"سعر تركيا: {int(turkey_price)} ليرة\n"
            f"التكلفة بالعراقي: {result['cost_iqd']}\n\n"
            f"سعر العراق: {result['iraq_price']}\n"
            f"الفرق: {result['diff']}\n\n"
            f"إجمالي التحميل: {result['total_load']}\n"
            f"سعر البيع: {result['sale_price']}"
        )
        return

    if turkey_price and not iraq_price:
        cost_iqd = turkey_to_iqd(turkey_price)
        await update.message.reply_text(
            f"الريفيرانس: {ref_code}\n\n"
            f"سعر تركيا: {int(turkey_price)} ليرة\n"
            f"التكلفة بالعراقي: {cost_iqd}\n\n"
            "لم استطع جلب سعر العراق حالياً"
        )
        return

    if iraq_price and not turkey_price:
        await update.message.reply_text(
            f"الريفيرانس: {ref_code}\n"
            f"سعر Mango العراق: {iraq_price}"
        )
        return


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("iraq", iraq))
    app.add_handler(CommandHandler("quote", quote))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot started...")
    app.run_polling()


main()
