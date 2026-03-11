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
        "بوت تسعيرة مانكو\n"
        "استخدم:\n"
        "/check رابط المنتج التركي"
    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("البوت يعمل بنجاح")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ارسل رابط المنتج أو الريفيرانس بعد /check")
        return

    user_text = " ".join(context.args).strip()

    ref_code, turkey_price = get_ref_and_turkey_price(user_text)

    if not ref_code:
        await update.message.reply_text("لم استطع استخراج الريفيرانس")
        return

    if not turkey_price:
        await update.message.reply_text(
            f"الريفيرانس المستخرج:\n{ref_code}\n\n"
            "استخرجت الريفيرانس لكن لم استطع جلب سعر تركيا.\n"
            "الأفضل أرسل رابط المنتج التركي المباشر."
        )
        return

    iraq_price = search_iraq_price_by_ref(ref_code)

    if not iraq_price:
        cost_iqd = turkey_to_iqd(turkey_price)
        await update.message.reply_text(
            f"الريفيرانس: {ref_code}\n"
            f"سعر تركيا: {int(turkey_price)} ليرة\n"
            f"التكلفة بالعراقي: {cost_iqd}\n\n"
            f"لم استطع جلب سعر العراق حالياً"
        )
        return

    result = calculate_final_prices(turkey_price, iraq_price)

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
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("check", check))

    print("Bot started...")
    app.run_polling()

main()
