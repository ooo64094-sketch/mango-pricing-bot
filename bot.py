import os
import re
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SERPAPI_KEY = os.environ.get("SERPAPI_KEY")


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
    raw = raw.replace("IQD", "")

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


def collect_turkey_price_candidates(ref_code: str):
    queries = [
        f'Mango {ref_code} TL',
        f'site:shop.mango.com/tr/tr {ref_code} TL',
        f'{ref_code} Mango Türkiye fiyat',
    ]

    patterns = [
        r'(\d[\d\.]+,\d{2})\s*TL',
        r'(\d[\d\.]+)\s*TL',
        r'₺\s*(\d[\d\.,]+)',
    ]

    candidates = []

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
                    candidates.append(round(value, 2))

        for item in data.get("organic_results", []):
            snippet = f"{item.get('title', '')} {item.get('snippet', '')}"
            for pattern in patterns:
                matches = re.findall(pattern, snippet, re.IGNORECASE)
                for m in matches:
                    value = parse_try_value(str(m))
                    if value and 10 <= value <= 100000:
                        candidates.append(round(value, 2))

    return candidates


def get_safe_turkey_price(ref_code: str):
    candidates = collect_turkey_price_candidates(ref_code)
    if not candidates:
        return None

    # إزالة التكرار مع تقريب بسيط
    normalized = {}
    for c in candidates:
        key = int(round(c))
        normalized[key] = normalized.get(key, 0) + 1

    # إذا عندنا مرشح واحد واضح أو مرشح مكرر أكثر من غيره
    sorted_items = sorted(normalized.items(), key=lambda x: x[1], reverse=True)

    best_price, best_count = sorted_items[0]

    # إذا هناك أكثر من سعر مختلف ومفيش إجماع كافٍ، نرفض
    if len(sorted_items) > 1 and best_count == sorted_items[1][1]:
        return None

    return float(best_price)


def collect_iraq_price_candidates(ref_code: str):
    queries = [
        f'site:shop.mango.com/iq/en {ref_code} IQD',
        f'Mango {ref_code} IQD',
        f'{ref_code} Mango Iraq price',
    ]

    patterns = [
        r'IQD\s*([0-9][0-9,\.]{2,})',
        r'([0-9][0-9,\.]{2,})\s*IQD',
    ]

    candidates = []

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
                    candidates.append(value)

        for item in data.get("organic_results", []):
            snippet = f"{item.get('title', '')} {item.get('snippet', '')}"
            for pattern in patterns:
                matches = re.findall(pattern, snippet, re.IGNORECASE)
                for m in matches:
                    value = parse_iqd_value(str(m))
                    if value and 5000 <= value <= 2000000:
                        candidates.append(value)

    return candidates


def get_safe_iraq_price(ref_code: str, turkey_price: float | None = None):
    candidates = collect_iraq_price_candidates(ref_code)
    if not candidates:
        return None

    counts = {}
    for c in candidates:
        counts[c] = counts.get(c, 0) + 1

    sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    best_price, best_count = sorted_items[0]

    # إذا لا يوجد إجماع وكان عندنا أكثر من سعر قوي، نرفض
    if len(sorted_items) > 1 and best_count == sorted_items[1][1]:
        return None

    # فلتر منطقي مقارنة بسعر تركيا إذا موجود
    if turkey_price:
        cost_iqd = turkey_to_iqd(turkey_price)

        # إذا السعر العراقي أقل بكثير من التكلفة أو أكبر جدًا بشكل غير منطقي، نرفض
        if best_price < cost_iqd * 0.7:
            return None
        if best_price > cost_iqd * 3.0:
            return None

    return best_price


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "بوت تسعيرة Mango - نسخة أمان\n\n"
        "ارسل فقط:\n"
        "• رابط Mango\n"
        "أو\n"
        "• الريفيرانس\n\n"
        "إذا كان السعر مؤكداً سيرسله.\n"
        "إذا لم يكن مؤكداً سيقول لك ذلك."
    )


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    if not text:
        return

    ref_code = extract_ref(text)

    if not ref_code:
        await update.message.reply_text("لم أستطع استخراج الريفيرانس")
        return

    await update.message.reply_text("جاري الفحص...")

    turkey_price = get_safe_turkey_price(ref_code)
    iraq_price = get_safe_iraq_price(ref_code, turkey_price)

    if not turkey_price and not iraq_price:
        await update.message.reply_text(
            f"الريفيرانس: {ref_code}\n"
            "لم أستطع تأكيد سعر تركيا ولا سعر العراق"
        )
        return

    if turkey_price and not iraq_price:
        cost_iqd = turkey_to_iqd(turkey_price)
        await update.message.reply_text(
            f"الريفيرانس: {ref_code}\n\n"
            f"سعر تركيا: {int(turkey_price)} ليرة\n"
            f"التكلفة بالعراقي: {cost_iqd}\n\n"
            "لم أستطع تأكيد سعر العراق"
        )
        return

    if iraq_price and not turkey_price:
        await update.message.reply_text(
            f"الريفيرانس: {ref_code}\n"
            f"سعر Mango العراق: {iraq_price}\n\n"
            "لم أستطع تأكيد سعر تركيا"
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


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot started...")
    app.run_polling()


main()
