import requests
from io import BytesIO
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import re
import time

TOKEN = "8713009534:AAFolnEv5dlLzg_h-OUlFkcVsV-XLQsiGEU"

IPHONES = {
    "iPhone 2G": {"width": 320, "height": 480},
    "iPhone 3G": {"width": 320, "height": 480},
    "iPhone 3GS": {"width": 320, "height": 480},
    "iPhone 4": {"width": 640, "height": 960},
    "iPhone 4S": {"width": 640, "height": 960},
    "iPhone 5": {"width": 640, "height": 1136},
    "iPhone 5C": {"width": 640, "height": 1136},
    "iPhone 5S": {"width": 640, "height": 1136},
    "iPhone SE (1-го поколения)": {"width": 640, "height": 1136},
    "iPhone 6": {"width": 750, "height": 1334},
    "iPhone 6 Plus": {"width": 1080, "height": 1920},
    "iPhone 6S": {"width": 750, "height": 1334},
    "iPhone 6S Plus": {"width": 1080, "height": 1920},
    "iPhone SE (2-го поколения)": {"width": 750, "height": 1334},
    "iPhone 7": {"width": 750, "height": 1334},
    "iPhone 7 Plus": {"width": 1080, "height": 1920},
    "iPhone 8": {"width": 750, "height": 1334},
    "iPhone 8 Plus": {"width": 1080, "height": 1920},
    "iPhone X": {"width": 1125, "height": 2436},
    "iPhone XR": {"width": 828, "height": 1792},
    "iPhone XS": {"width": 1125, "height": 2436},
    "iPhone XS Max": {"width": 1242, "height": 2688},
    "iPhone 11": {"width": 828, "height": 1792},
    "iPhone 11 Pro": {"width": 1125, "height": 2436},
    "iPhone 11 Pro Max": {"width": 1242, "height": 2688},
    "iPhone SE (3-го поколения)": {"width": 750, "height": 1334},
    "iPhone 12 mini": {"width": 1080, "height": 2340},
    "iPhone 12": {"width": 1170, "height": 2532},
    "iPhone 12 Pro": {"width": 1170, "height": 2532},
    "iPhone 12 Pro Max": {"width": 1284, "height": 2778},
    "iPhone 13 mini": {"width": 1080, "height": 2340},
    "iPhone 13": {"width": 1170, "height": 2532},
    "iPhone 13 Pro": {"width": 1170, "height": 2532},
    "iPhone 13 Pro Max": {"width": 1284, "height": 2778},
    "iPhone 14": {"width": 1170, "height": 2532},
    "iPhone 14 Plus": {"width": 1284, "height": 2778},
    "iPhone 14 Pro": {"width": 1179, "height": 2556},
    "iPhone 14 Pro Max": {"width": 1290, "height": 2796},
    "iPhone 15": {"width": 1179, "height": 2556},
    "iPhone 15 Plus": {"width": 1290, "height": 2796},
    "iPhone 15 Pro": {"width": 1179, "height": 2556},
    "iPhone 15 Pro Max": {"width": 1290, "height": 2796},
    "iPhone 16": {"width": 1179, "height": 2556},
    "iPhone 16 Plus": {"width": 1290, "height": 2796},
    "iPhone 16 Pro": {"width": 1206, "height": 2622},
    "iPhone 16 Pro Max": {"width": 1320, "height": 2868},
}

user_phone = {}
user_query = {}
user_urls = {}
user_index = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    row = []
    for i, model in enumerate(sorted(IPHONES.keys())):
        row.append(InlineKeyboardButton(model, callback_data=model))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    await update.message.reply_text(
        "📱 *Выбери модель iPhone:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def select_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_phone[q.from_user.id] = q.data
    size = IPHONES[q.data]
    await q.edit_message_text(
        f"✅ *{q.data}*\n📐 {size['width']}×{size['height']}\n\n🔍 *Напиши запрос:*",
        parse_mode="Markdown"
    )

async def search_vertical_images(query):
    try:
        url = f"https://www.bing.com/images/search?q={query}&aspect=tall&size=wallpaper"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.get(url, headers=headers, timeout=15)
        
        pattern = r'murl&quot;:&quot;(https://[^&]+\.(jpg|jpeg|png))'
        matches = re.findall(pattern, r.text)
        
        urls = []
        for match in matches:
            url = match[0].replace('\\', '')
            if url not in urls:
                urls.append(url)
        
        return urls[:30]
    except Exception as e:
        print(f"Ошибка: {e}")
        return []

def resize_to_fit(img, target_width, target_height):
    img_ratio = img.width / img.height
    target_ratio = target_width / target_height
    
    if img_ratio > target_ratio:
        new_height = target_height
        new_width = int(target_height * img_ratio)
        img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        left = (new_width - target_width) // 2
        img_cropped = img_resized.crop((left, 0, left + target_width, target_height))
    else:
        new_width = target_width
        new_height = int(target_width / img_ratio)
        img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        top = (new_height - target_height) // 2
        img_cropped = img_resized.crop((0, top, target_width, top + target_height))
    
    return img_cropped

async def send_photos(msg, uid, count):
    urls = user_urls.get(uid, [])
    idx = user_index.get(uid, 0)
    phone = user_phone.get(uid)
    size = IPHONES.get(phone, {"width": 1170, "height": 2532})
    query = user_query.get(uid, "")
    
    sent = 0
    for i in range(count):
        pos = idx + i
        if pos < len(urls):
            try:
                url = urls[pos]
                resp = requests.get(url, timeout=20, headers={'User-Agent': 'Mozilla/5.0'})
                img = Image.open(BytesIO(resp.content))
                
                if img.width > img.height:
                    continue
                
                img_fixed = resize_to_fit(img, size['width'], size['height'])
                
                out = BytesIO()
                img_fixed.save(out, format='JPEG', quality=90)
                out.seek(0)
                
                await msg.reply_photo(photo=out, caption=f"🎨 *{query}*\n📱 *{phone}*")
                sent += 1
                time.sleep(0.3)
            except Exception as e:
                print(f"Ошибка {pos}: {e}")
    
    user_index[uid] = idx + sent

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if uid not in user_phone:
        await update.message.reply_text("⚠️ /start")
        return
    
    query = update.message.text
    user_query[uid] = query
    
    status = await update.message.reply_text(f"🔍 Ищу '{query}'...")
    
    urls = await search_vertical_images(query)
    
    if urls:
        user_urls[uid] = urls
        user_index[uid] = 0
        
        await status.delete()
        await send_photos(update.message, uid, 2)
        
        keyboard = [
            [InlineKeyboardButton("🔄 Ещё 2", callback_data="more")],
            [InlineKeyboardButton("🆕 Новый запрос", callback_data="new_query")]
        ]
        await update.message.reply_text(
            f"✅ Найдено {len(urls)} фото",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await status.edit_text("❌ Ничего не найдено. Попробуй другой запрос.")

async def more(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    uid = q.from_user.id
    if uid not in user_urls:
        await q.edit_message_text("❌ Напиши новый запрос")
        return
    
    await q.edit_message_text("🔍 Загружаю ещё...")
    await send_photos(q.message, uid, 2)
    
    remaining = len(user_urls[uid]) - user_index.get(uid, 0)
    if remaining > 0:
        keyboard = [
            [InlineKeyboardButton("🔄 Ещё 2", callback_data="more")],
            [InlineKeyboardButton("🆕 Новый запрос", callback_data="new_query")]
        ]
        await q.message.reply_text(
            f"✅ Осталось {remaining} фото",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await q.message.reply_text("😔 Всё. Напиши новый запрос.")

async def new_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    uid = q.from_user.id
    
    if uid in user_query:
        del user_query[uid]
    if uid in user_urls:
        del user_urls[uid]
    if uid in user_index:
        del user_index[uid]
    
    phone = user_phone.get(uid)
    if phone:
        size = IPHONES[phone]
        await q.edit_message_text(
            f"✅ *{phone}*\n📐 {size['width']}×{size['height']}\n\n🔍 *Напиши новый запрос:*",
            parse_mode="Markdown"
        )
    else:
        await q.edit_message_text("📱 *Напиши /start для выбора модели*", parse_mode="Markdown")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(select_phone))
    app.add_handler(CallbackQueryHandler(more, pattern="more"))
    app.add_handler(CallbackQueryHandler(new_query, pattern="new_query"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    
    print("✅ Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
