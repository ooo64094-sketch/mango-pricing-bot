import os
import re
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SERPAPI_KEY = os.environ.get("SERPAPI_KEY")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,tr;q=0.8,ar;q=0.7",
    "Connection": "keep-alive",
}

session = requests.Session()
session.headers.update(HEADERS)

def extract_ref(text: str):
    match = re.search(r'_(\d{8})|\b(\d{8})\b', text)
    if match:
        return match.group(1) or match.group(2)
    return None

def get_html(url: str):
    r = session.get(url, timeout=25, allow_redirects=True)
    r.raise_for_status()
    return r.text

def serp_search(query: str):
    if not SERPAPI_KEY:
        return []

    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_KEY,
        "hl": "en",
        "gl": "us",
    }

    r = requests.get("https://serpapi.com/search", params=params, timeout=25)
    r.raise_for_status()
    data = r.json()
    return data.get("organic_results", [])

def parse_int_number(raw: str):
    raw = raw.strip().replace("\xa0", " ").replace(" ", "")
    raw = raw.replace(",", "").replace(".", "")
    try:
        return int(raw)
    except:
        return None

def parse_tr_price(raw: str):
    raw = raw.strip().replace("\xa0", " ").replace(" ", "")
    raw = raw.replace("TL", "").replace("₺", "")

    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    else:
        raw = raw.replace(",", ".")

    try:
        return float(raw)
    except:
        return None

def extract_turkey_price(html: str):
    patterns = [
        r'(\d[\d\.,]{1,})\s*TL',
        r'(\d[\d\.,]{1,})\s*₺',
        r'"price"\s*:\s*"?(\\?\d[\d\.,]{0,})"?',
        r'"salePrice"\s*:\s*"?(\\?\d[\d\.,]{0,})"?',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for m in matches:
            value = parse_tr_price(m)
            if value and value > 0:
                return value

    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)

    for pattern in patterns[:2]:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            value = parse_tr_price(m)
            if value and value > 0:
                return value

    return None

def extract_iqd_price(html: str):
    patterns = [
        r'(\d[\d,\.]{1,})\s*IQD',
        r'IQD\s*(\d[\d,\.]{1,})',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for m in matches:
            value = parse_int_number(m)
            if value and value > 0:
                return value

    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            value = parse_int_number(m)
            if value and value > 0:
                return value

    return None

def find_turkey_page_and_price(ref_code: str, original_url: str = None):
    candidates = []

    if original_url and "shop.mango.com/tr/" in original_url:
        candidates.append(original_url)

    queries = [
        f'site:shop.mango.com/tr/tr "{ref_code}"',
        f"site:shop.mango.com/tr/tr/p {ref_code} Mango",
    ]

    for q in queries:
        try:
            results = serp_search(q)
            for res in results:
                link = res.get("link", "")
                if "shop.mango.com/tr/" in link:
                    candidates.append(link)
        except:
            pass

    seen = set()
    unique_candidates = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            unique_candidates.append(c)

    for link in unique_candidates[:8]:
        try:
            html = get_html(link)
            price = extract_turkey_price(html)
            if price:
                return {"url": link, "price_try": price}
        except:
            continue

    return None

def find_iraq_page_and_price(ref_code: str):
    queries = [
        f'site:shop.mango.com/iq/en/p "{ref_code}"',
        f'site:shop.mango.com/iq/en "{ref_code}" "IQD"',
        f"site:shop.mango.com/iq/en/p {ref_code} Mango",
    ]

    candidates = []

    for q in queries:
        try:
            results = serp_search(q)
            for res in results:
                link = res.get("link", "")
                if "shop.mango.com/iq/" in link:
                    candidates.append(link)
        except:
            pass

    seen = set()
    unique_candidates = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            unique_candidates.append(c)

    for link in unique_candidates[:10]:
        try:
            html = get_html(link)
            price = extract_iqd_price(html)
            if price:
                return {"url": link, "price_iqd": price}
        except:
            continue

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
        "diff": diff,
        "total_load": total_load,
        "sale_price": sale_price
    }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "بوت تسعيرة مانكو\n\n"
        "استخدم:\n"
        "/check رابط_تركيا أو ريفيرانس"
    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ارسل رابط Mango تركيا أو الريفيرانس بعد /check")
        return

    user_input = " ".join(context.args).strip()
    ref_code = extract_ref(user_input)

    if not ref_code:
        await update.message.reply_text("لم استطع استخراج الريفيرانس")
        return

    await update.message.reply_text("جاري الفحص...")

    try:
        turkey_data = find_turkey_page_and_price(
            ref_code,
            user_input if user_input.startswith("http") else None
        )

        if not turkey_data:
            await update.message.reply_text(
                f"الريفيرانس: {ref_code}\n"
                "لم استطع جلب سعر تركيا"
            )
            return

        iraq_data = find_iraq_page_and_price(ref_code)

        if not iraq_data:
            cost_iqd = turkey_to_iqd(turkey_data["price_try"])
            await update.message.reply_text(
                f"الريفيرانس: {ref_code}\n\n"
                f"سعر تركيا: {int(turkey_data['price_try'])} ليرة\n"
                f"التكلفة بالعراقي: {cost_iqd}\n\n"
                "لم استطع جلب سعر العراق حالياً"
            )
            return

        result = calculate_quote(turkey_data["price_try"], iraq_data["price_iqd"])

        await update.message.reply_text(
            f"الريفيرانس: {ref_code}\n\n"
            f"سعر تركيا: {int(turkey_data['price_try'])} ليرة\n"
            f"التكلفة بالعراقي: {result['cost_iqd']}\n\n"
            f"سعر العراق: {iraq_data['price_iqd']}\n"
            f"الفرق: {result['diff']}\n\n"
            f"إجمالي التحميل: {result['total_load']}\n"
            f"سعر البيع: {result['sale_price']}"
        )

    except Exception as e:
        await update.message.reply_text(f"خطأ:\n{str(e)}")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("check", check))

    print("Bot started...")
    app.run_polling()

main()
