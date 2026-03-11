import os
import re
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from playwright.async_api import async_playwright

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SERPAPI_KEY = os.environ.get("SERPAPI_KEY")

HEADERS = {
"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
"Accept-Language": "en-US,en;q=0.9,tr;q=0.8,ar;q=0.7",
}

def extract_ref(text: str):
match = re.search(r'_(\d{8})|\b(\d{8})\b', text)
if match:
return match.group(1) or match.group(2)
return None

def serp_search(query: str):
if not SERPAPI_KEY:
return []

params = {
"engine": "google",
"q": query,
"api_key": SERPAPI_KEY,
"hl": "en",
"gl": "us",
"num": 10,
}

r = requests.get("https://serpapi.com/search", params=params, timeout=30)
r.raise_for_status()
data = r.json()
return data.get("organic_results", [])

def parse_tr_price_text(text: str):
text = text.strip().replace("\xa0", " ").replace(" ", "")
text = text.replace("TL", "").replace("₺", "")
if "," in text and "." in text:
text = text.replace(".", "").replace(",", ".")
else:
text = text.replace(",", ".")
try:
return float(text)
except:
return None

def parse_iqd_price_text(text: str):
text = text.strip().replace("\xa0", " ").replace(" ", "")
text = text.replace("IQD", "")
text = text.replace(",", "")
text = text.split(".")[0]
try:
return int(text)
except:
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

async def dismiss_popups(page):
for txt in ["KABUL ET", "ACCEPT", "Accept", "Continue", "Tamam"]:
try:
loc = page.locator(f"text={txt}").first
if await loc.count() > 0:
await loc.click(timeout=2000)
await page.wait_for_timeout(1500)
break
except:
pass

async def get_body_text(page):
try:
return await page.locator("body").text_content() or ""
except:
return ""

async def collect_visible_turkey_prices(page):
selectors = [
"text=/[0-9][0-9\\.,]*\\s*TL/",
"text=/[0-9][0-9\\.,]*\\s*₺/",
]

candidates = []

for sel in selectors:
try:
loc = page.locator(sel)
count = await loc.count()
for i in range(min(count, 20)):
txt = await loc.nth(i).text_content()
if not txt:
continue
value = parse_tr_price_text(txt)
if value and 10 <= value <= 100000:
candidates.append(value)
except:
pass

return candidates

async def extract_visible_turkey_price(page):
candidates = await collect_visible_turkey_prices(page)
if candidates:
# نأخذ أصغر سعر منطقي ظاهر، لأنه غالبًا السعر الرئيسي وليس أسعار أخرى كبيرة
return min(candidates)

body_text = await get_body_text(page)
patterns = [
r'([0-9][0-9\.,]*)\s*TL',
r'([0-9][0-9\.,]*)\s*₺',
]
fallback = []
for pattern in patterns:
matches = re.findall(pattern, body_text, re.IGNORECASE)
for m in matches:
value = parse_tr_price_text(str(m))
if value and 10 <= value <= 100000:
fallback.append(value)

if fallback:
return min(fallback)

return None

async def get_h1_y(page):
try:
h1 = page.locator("h1").first
if await h1.count() > 0:
box = await h1.bounding_box()
if box:
return box["y"]
except:
pass
return None

async def collect_visible_iqd_prices(page):
selectors = [
"text=/IQD\\s*[0-9]/",
"text=/[0-9][0-9,\\.]*\\s*IQD/",
]

candidates = []
h1_y = await get_h1_y(page)

for sel in selectors:
try:
loc = page.locator(sel)
count = await loc.count()
for i in range(min(count, 20)):
item = loc.nth(i)
txt = await item.text_content()
if not txt:
continue

value = parse_iqd_price_text(txt)
if not value or not (5000 <= value <= 2000000):
continue

box = await item.bounding_box()
distance = 999999.0
if box and h1_y is not None:
distance = abs(box["y"] - h1_y)

candidates.append({
"text": txt.strip(),
"value": value,
"distance": distance
})
except:
pass

return candidates

async def extract_visible_iqd_price(page):
candidates = await collect_visible_iqd_prices(page)

if not candidates:
return None

candidates.sort(key=lambda x: x["distance"])
best = candidates[0]

if len(candidates) > 1:
second = candidates[1]
if best["value"] != second["value"] and abs(best["distance"] - second["distance"]) < 120:
return None

return best["value"]

async def scrape_product_page(url: str, locale: str, mode: str):
async with async_playwright() as p:
browser = await p.chromium.launch(headless=True)
context = await browser.new_context(
locale=locale,
user_agent=HEADERS["User-Agent"]
)
page = await context.new_page()
await page.goto(url, wait_until="domcontentloaded", timeout=60000)
await page.wait_for_timeout(3500)
await dismiss_popups(page)

body_text = await get_body_text(page)
ref_code = extract_ref(url) or extract_ref(body_text)

if mode == "TR":
price = await extract_visible_turkey_price(page)
else:
price = await extract_visible_iqd_price(page)

await browser.close()
return {
"ref": ref_code,
"price": price
}

def find_turkey_links(ref_code: str, original_url: str = None):
links = []
seen = set()

if original_url and original_url.startswith("http") and "shop.mango.com/tr/" in original_url:
links.append(original_url)
seen.add(original_url)

queries = [
f'site:shop.mango.com/tr/tr "{ref_code}"',
f"site:shop.mango.com/tr/tr/p {ref_code} Mango",
]

for q in queries:
try:
results = serp_search(q)
for res in results:
link = res.get("link", "")
if "shop.mango.com/tr/" in link and link not in seen:
seen.add(link)
links.append(link)
except:
pass

return links

def find_iraq_links(ref_code: str):
queries = [
f'site:shop.mango.com/iq/en/p "{ref_code}"',
f'site:shop.mango.com/iq/en "{ref_code}" "IQD"',
f"site:shop.mango.com/iq/en/p {ref_code} Mango",
]

links = []
seen = set()

for q in queries:
try:
results = serp_search(q)
for res in results:
link = res.get("link", "")
if "shop.mango.com/iq/" in link and link not in seen:
seen.add(link)
links.append(link)
except:
pass

return links

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
turkey_links = find_turkey_links(ref_code, user_input if user_input.startswith("http") else None)
if not turkey_links:
await update.message.reply_text(
f"الريفيرانس: {ref_code}\n"
"لم استطع العثور على رابط تركيا"
)
return

turkey_data = None
for link in turkey_links[:5]:
try:
data = await scrape_product_page(link, "tr-TR", "TR")
if data["ref"] == ref_code and data["price"]:
turkey_data = data
break
except:
continue

if not turkey_data:
await update.message.reply_text(
f"الريفيرانس: {ref_code}\n"
"لم استطع جلب سعر تركيا"
)
return

iraq_links = find_iraq_links(ref_code)
iraq_data = None

for link in iraq_links[:8]:
try:
data = await scrape_product_page(link, "en-US", "IQ")
if data["ref"] == ref_code and data["price"]:
iraq_data = {
"url": link,
"price_iqd": data["price"]
}
break
except:
continue

if not iraq_data:
cost_iqd = turkey_to_iqd(turkey_data["price"])
await update.message.reply_text(
f"الريفيرانس: {ref_code}\n\n"
f"سعر تركيا: {int(turkey_data['price'])} ليرة\n"
f"التكلفة بالعراقي: {cost_iqd}\n\n"
"لم استطع جلب سعر العراق حالياً"
)
return

result = calculate_quote(turkey_data["price"], iraq_data["price_iqd"])

await update.message.reply_text(
f"الريفيرانس: {ref_code}\n\n"
f"سعر تركيا: {int(turkey_data['price'])} ليرة\n"
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
