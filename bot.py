import os
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "بوت تسعيرة مانكو\n\n"
        "الاوامر:\n"
        "/check رابط أو ريفيرانس\n"
        "/quote سعر_تركيا سعر_العراق رابط_أو_ريفيرانس\n\n"
        "مثال:\n"
        "/quote 2000 74000 27071311"
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

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CommandHandler("quote", quote))

    print("Bot started...")
    app.run_polling()

main()
