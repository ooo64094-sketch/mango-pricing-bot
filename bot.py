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

def extract_ref_from_text(text):
    if not text:
        return None

    patterns = [
        r'REF\.?\s*[:\-]?\s*(\d{8})',
        r'Ref\.?\s*[:\-]?\s*(\d{8})',
        r'"reference"\s*:\s*"(\d{8})"',
        r'"productCode"\s*:\s*"(\d{8})"',
        r'"sku"\s*:\s*"(\d{8})"',
        r'\b(\d{8})\b',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    return None

def extract_ref_from_url_or_page(text):
    # أولاً: حاول استخراج الرقم من نفس النص أو الرابط
    ref_code = extract_ref_from_text(text)
    if ref_code:
        return ref_code

    # إذا النص ليس رابط، انتهى
    if not text.startswith("http"):
        return None

    # ثانياً: افتح الصفحة وابحث داخلها
    try:
        response = requests.get(text, headers=HEADERS, timeout=20)
        response.raise_for_status()
        html = response.text

        # ابحث في HTML الخام
        ref_code = extract_ref_from_text(html)
        if ref_code:
            return ref_code

        # ابحث في النص الظاهر
        soup = BeautifulSoup(html, "lxml")
        page_text = soup.get_text(" ", strip=True)
        ref_code = extract_ref_from_text(page_text)
        if ref_code:
            return ref_code

    except Exception:
        return None

    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "اهلا بك في بوت Mango Pricing\n"
        "استخدم:\n"
        "/check رابط او ريفيرانس"
    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("البوت يعمل بنجاح")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ارسل الرابط او الريفيرانس بعد الامر")
        return

    text = " ".join(context.args).strip()
    ref_code = extract_ref_from_url_or_page(text)

    if not ref_code:
        await update.message.reply_text("لم استطع استخراج الريفيرانس من الرابط او النص")
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
