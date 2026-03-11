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
        r'"\s*reference\s*"\s*:\s*"(\d{8})"',
        r'"\s*productCode\s*"\s*:\s*"(\d{8})"',
        r'"\s*sku\s*"\s*:\s*"(\d{8})"',
        r'\b(\d{8})\b',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    return None

def get_ref_from_input(user_text):
    user_text = user_text.strip()

    # إذا المستخدم أرسل ريفيرانس مباشرة
    direct_ref = re.fullmatch(r'\d{8}', user_text)
    if direct_ref:
        return direct_ref.group(0)

    # إذا المستخدم أرسل رابط
    if user_text.startswith("http"):
        try:
            response = requests.get(user_text, headers=HEADERS, timeout=20)
            response.raise_for_status()

            html = response.text

            # 1) نحاول من HTML الخام
            ref_code = extract_ref_from_text(html)
            if ref_code:
                return ref_code

            # 2) نحاول من النص الظاهر
            soup = BeautifulSoup(html, "lxml")
            page_text = soup.get_text(" ", strip=True)
            ref_code = extract_ref_from_text(page_text)
            if ref_code:
                return ref_code

            # 3) نحاول من سكربتات الصفحة
            scripts_text = " ".join(script.get_text(" ", strip=True) for script in soup.find_all("script"))
            ref_code = extract_ref_from_text(scripts_text)
            if ref_code:
                return ref_code

        except Exception:
            return None

    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "بوت Mango Pricing\n"
        "استخدم:\n"
        "/check ريفيرانس أو رابط"
    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("البوت يعمل بنجاح")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ارسل الريفيرانس أو الرابط بعد /check")
        return

    user_text = " ".join(context.args).strip()
    ref_code = get_ref_from_input(user_text)

    if not ref_code:
        await update.message.reply_text("لم استطع استخراج REF من الرابط أو النص")
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
