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

def get_html(url):
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    return r.text

def parse_number(raw):
    raw = raw.strip()
    raw = raw.replace("\xa0", " ")
    raw = raw.replace(",", "").replace(" ", "")
    try:
        return int(float(raw))
    except:
        return None

def parse_price_float(raw):
    raw = raw.strip()
    raw = raw.replace("\xa0", " ")
    raw = raw.replace("TL", "").replace("₺", "").strip()

    # إذا الرقم مثل 1.999,99
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    else:
        raw = raw.replace(",", ".")

    try:
        return float(raw)
    except:
        return None

def extract_turkey_price(html):
    patterns = [
        r'"salePrice"\s*:\s*"?(\\d+[\\.,]?\\d*)"?',
        r'"price"\s*:\s*"?(\\d+[\\.,]?\\d*)"?',
        r'(\d[\d\.,]{1,})\s*TL',
        r'(\d[\d\.,]{1,})\s*₺',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for m in matches:
            price = parse_price_float(m)
            if price and price > 0:
                return price

    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            price = parse_price_float(m)
            if price and price > 0:
                return price

    return None

def extract_iqd_price(html):
    patterns = [
        r'(\d[\d,\.]{1,})\s*IQD',
        r'IQD\s*(\d[\d,\.]{1,})',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for m in matches:
            value = parse_number(m.replace(".", "").replace(",", ""))
            if value and value > 0:
                return value

    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            value = parse_number(m.replace(".", "").replace(",", ""))
            if value and value > 0:
                return value

    return None

def find_iraq_price(ref_code):
    # 1) محاولة البحث داخل مانكو العراق مباشرة
    search_urls = [
        f"https://shop.mango.com/iq/en/search/{ref_code}",
        f"https://shop.mango.com/iq/en/search?q={ref_code}",
    ]

    for url in search_urls:
        try:
            html = get_html(url)
            price = extract_iqd_price(html)
            if price:
                return price
        except:
            pass

    # 2) محاولة البحث عبر DuckDuckGo HTML عن صفحة Mango Iraq
    try:
        ddg_url = "https://html.duckduckgo.com/html/"
        params = {"q": f"site:shop.mango.com/iq/en {ref_code} Mango"}
        r = requests.get(ddg_url, params=params, headers=HEADERS, timeout=25)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")

        links = []
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if "shop.mango.com/iq/en" in href:
                links.append(href)

        seen = set()
        clean_links = []
        for link in links:
            if link not in seen:
                seen.add(link)
                clean_links.append(link)

        for link in clean_links[:5]:
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

def get_ref_and_turkey_price_from_url(url):
    html = get_html(url)

    ref_code = extract_ref(url)
    if not ref_code:
        ref_code = extract_ref(html)

    price_try = extract_turkey_price(html)

    return ref_code, price_try

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "بوت تسعيرة مانكو\n\n"
        "استخدم:\n"
        "/check رابط_تركيا\n\n"
        "مثال:\n"
        "/check https://shop.mango.com/tr/tr/p/..."
    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ارسل رابط المنتج التركي بعد /check")
        return

    url = " ".join(context.args).strip()

    if not url.startswith("http"):
        await update.message.reply_text("ارسل رابط Mango تركيا كامل")
        return

    await update.message.reply_text("جاري الفحص...")

    try:
        ref_code, turkey_price = get_ref_and_turkey_price_from_url(url)

        if not ref_code:
            await update.message.reply_text("لم استطع استخراج الريفيرانس من الرابط")
            return

        if not turkey_price:
            await update.message.reply_text(
                f"الريفيرانس: {ref_code}\n"
                "استخرجت الريفيرانس لكن لم استطع جلب سعر تركيا"
            )
            return

        iraq_price = find_iraq_price(ref_code)

        if not iraq_price:
            cost_iqd = turkey_to_iqd(turkey_price)
            await update.message.reply_text(
                f"الريفيرانس: {ref_code}\n\n"
                f"سعر تركيا: {int(turkey_price)} ليرة\n"
                f"التكلفة بالعراقي: {cost_iqd}\n\n"
                "لم استطع جلب سعر العراق حالياً"
            )
            return

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

    except Exception as e:
        await update.message.reply_text(f"صار خطأ أثناء الفحص:\n{str(e)}")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("check", check))

    print("Bot started...")
    app.run_polling()

main()
