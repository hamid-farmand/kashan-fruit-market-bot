import logging
from pybalebot import Bot, MessageHandler, CallbackQueryHandler, filters
from pybalebot.types import ReplyKeyboardMarkup, KeyboardButton, ForceReply, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_db_connection, get_today_jalali, create_tables, seed_initial_data
import json
from khayyam import JalaliDatetime
from config import BOT_TOKEN, ADMIN_CHAT_ID

logging.basicConfig(level=logging.INFO)
create_tables()
seed_initial_data()

bot = Bot(token=BOT_TOKEN)

def save_state(chat_id, state, data=None):
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO user_states (chat_id, state, data) VALUES (?, ?, ?)",
                 (str(chat_id), state, json.dumps(data) if data else None))
    conn.commit()
    conn.close()

def get_state(chat_id):
    conn = get_db_connection()
    row = conn.execute("SELECT state, data FROM user_states WHERE chat_id = ?", (str(chat_id),)).fetchone()
    conn.close()
    if row:
        return row['state'], json.loads(row['data']) if row['data'] else {}
    return None, {}

def clear_state(chat_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM user_states WHERE chat_id = ?", (str(chat_id),))
    conn.commit()
    conn.close()

def is_vendor(chat_id):
    conn = get_db_connection()
    vendor = conn.execute("SELECT * FROM vendors WHERE chat_id = ?", (str(chat_id),)).fetchone()
    conn.close()
    return vendor

def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🏪 انتخاب غرفه و دیدن قیمت‌ها")],
        [KeyboardButton("ℹ️ راهنما")]
    ], resize_keyboard=True)

def vendor_menu(vendor):
    return ReplyKeyboardMarkup([
        [KeyboardButton("📝 ثبت/ویرایش قیمت امروز")],
        [KeyboardButton("📋 مشاهده قیمت‌های امروز")],
        [KeyboardButton("🔙 بازگشت به منوی اصلی")]
    ], resize_keyboard=True)

def product_list_keyboard():
    conn = get_db_connection()
    products = conn.execute("SELECT name FROM products ORDER BY name").fetchall()
    conn.close()
    buttons = [[KeyboardButton(p['name'])] for p in products]
    buttons.append([KeyboardButton("🔙 منوی غرفه")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

@bot.message_handler(filters.Command("start"))
async def start_handler(message):
    user = message.from_user
    chat_id = user.id
    vendor = is_vendor(chat_id)
    if vendor:
        await message.reply(f"🍎 خوش آمدید {vendor['name']}!\n\nپنل مدیریت غرفه", reply_markup=vendor_menu(vendor))
        save_state(chat_id, "vendor_menu", {"vendor_id": vendor['id']})
    else:
        await message.reply("🍎 به ربات قیمت میوه و تره‌بار کاشان خوش آمدید!\n\nلطفاً گزینه مورد نظر را انتخاب کنید:", reply_markup=main_menu())
        save_state(chat_id, "main_menu")

@bot.message_handler(filters.Text("🏪 انتخاب غرفه و دیدن قیمت‌ها"))
async def select_vendor(message):
    conn = get_db_connection()
    vendors = conn.execute("SELECT room_number, name FROM vendors WHERE active = 1 ORDER BY room_number").fetchall()
    conn.close()
    if not vendors:
        await message.reply("هیچ غرفه فعالی یافت نشد.")
        return
    buttons = [[KeyboardButton(f"غرفه {v['room_number']} - {v['name']}")] for v in vendors]
    buttons.append([KeyboardButton("🔙 بازگشت")])
    keyboard = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    await message.reply("غرفه مورد نظر را انتخاب کنید:", reply_markup=keyboard)
    save_state(message.from_user.id, "selecting_vendor")

@bot.message_handler(filters.Regex(r"^غرفه \d+"))
async def show_prices(message):
    try:
        room_number = int(message.text.split()[1])
        conn = get_db_connection()
        vendor = conn.execute("SELECT name FROM vendors WHERE room_number = ?", (room_number,)).fetchone()
        if not vendor:
            await message.reply("غرفه یافت نشد.")
            return
        today = get_today_jalali()
        prices = conn.execute("""
            SELECT p.name, pr.price, p.unit 
            FROM prices pr JOIN products p ON pr.product_id = p.id 
            WHERE pr.vendor_id = (SELECT id FROM vendors WHERE room_number = ?) AND pr.date = ?
        """, (room_number, today)).fetchall()
        conn.close()
        if not prices:
            text = f"📌 برای غرفه {vendor['name']} هنوز قیمتی ثبت نشده ({today})."
        else:
            text = f"📌 قیمت‌های امروز غرفه {vendor['name']} ({today}):\n\n"
            for p in prices:
                text += f"🔹 {p['name']}: {p['price']:,} تومان ({p['unit']})\n"
            text += f"\n⏰ آخرین بروزرسانی: {JalaliDatetime.now().strftime('%H:%M')}"
        await message.reply(text)
    except Exception as e:
        await message.reply("خطا در بارگیری قیمت‌ها. دوباره تلاش کنید.")

@bot.message_handler(filters.Text("📝 ثبت/ویرایش قیمت امروز"))
async def start_price_entry(message):
    state, data = get_state(message.from_user.id)
    if not data.get("vendor_id"):
        await message.reply("دسترسی غیرمجاز.")
        return
    await message.reply("محصولی که می‌خواهید قیمت آن را ثبت کنید انتخاب کنید:", reply_markup=product_list_keyboard())
    save_state(message.from_user.id, "selecting_product", data)

@bot.message_handler(filters.Text("🔙 منوی غرفه"))
async def back_to_vendor(message):
    chat_id = message.from_user.id
    vendor = is_vendor(chat_id)
    if vendor:
        await message.reply(f"پنل غرفه {vendor['name']}", reply_markup=vendor_menu(vendor))
        save_state(chat_id, "vendor_menu", {"vendor_id": vendor['id']})

@bot.message_handler(func=lambda m: get_state(m.from_user.id)[0] == "selecting_product")
async def select_product(message):
    state, data = get_state(message.from_user.id)
    product_name = message.text.strip()
    conn = get_db_connection()
    product = conn.execute("SELECT id, name FROM products WHERE name = ?", (product_name,)).fetchone()
    conn.close()
    if not product:
        await message.reply("محصول یافت نشد. دوباره انتخاب کنید.")
        return
    save_state(message.from_user.id, "waiting_for_price", {
        "vendor_id": data["vendor_id"],
        "product_id": product["id"],
        "product_name": product["name"]
    })
    await message.reply(f"قیمت «{product['name']}» را به تومان وارد کنید (مثال: 45000):", reply_markup=ForceReply())

@bot.message_handler(filters.Reply)
async def enter_price(message):
    state, data = get_state(message.from_user.id)
    if state != "waiting_for_price" or not message.text.isdigit():
        return
    price = int(message.text)
    today = get_today_jalali()
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO prices (vendor_id, product_id, price, date)
        VALUES (?, ?, ?, ?) ON CONFLICT(vendor_id, product_id, date) 
        DO UPDATE SET price = excluded.price, updated_at = CURRENT_TIMESTAMP
    """, (data["vendor_id"], data["product_id"], price, today))
    conn.commit()
    conn.close()
    await message.reply(f"✅ قیمت {data['product_name']} ثبت شد: {price:,} تومان ({today})")
    await message.reply("محصول بعدی را انتخاب کنید:", reply_markup=product_list_keyboard())
    save_state(message.from_user.id, "selecting_product", {"vendor_id": data["vendor_id"]})

@bot.message_handler(filters.Text("📋 مشاهده قیمت‌های امروز"))
async def view_prices(message):
    state, data = get_state(message.from_user.id)
    vendor_id = data.get("vendor_id")
    if not vendor_id:
        return
    today = get_today_jalali()
    conn = get_db_connection()
    prices = conn.execute("""
        SELECT p.name, pr.price FROM prices pr 
        JOIN products p ON pr.product_id = p.id 
        WHERE pr.vendor_id = ? AND pr.date = ?
    """, (vendor_id, today)).fetchall()
    conn.close()
    if not prices:
        await message.reply(f"برای امروز ({today}) قیمتی ثبت نشده.")
    else:
        text = f"قیمت‌های ثبت‌شده ({today}):\n\n"
        for p in prices:
            text += f"🔹 {p['name']}: {p['price']:,} تومان\n"
        await message.reply(text)

@bot.message_handler(filters.Text("🔙 بازگشت به منوی اصلی"))
async def back_main(message):
    await message.reply("منوی اصلی:", reply_markup=main_menu())
    clear_state(message.from_user.id)
    save_state(message.from_user.id, "main_menu")

@bot.message_handler(filters.Text("ℹ️ راهنما"))
async def help_handler(message):
    await message.reply(
        "🍎 راهنمای ربات قیمت میوه و تره‌بار کاشان:\n\n"
        "👥 مشتریان: غرفه انتخاب کنید و قیمت‌ها رو ببینید.\n"
        "🏪 غرفه‌داران: با /start وارد پنل بشید و قیمت ثبت کنید.\n\n"
        "ساخته شده با ❤️ برای کاشان | GitHub: [لینک ریپو]"
    )

if __name__ == "__main__":
    print("🚀 ربات قیمت کاشان راه‌اندازی شد!")
    bot.run()