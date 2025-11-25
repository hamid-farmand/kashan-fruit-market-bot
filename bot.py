from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ForceReply
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from database import get_db_connection, get_today_jalali, create_tables, seed_initial_data
import json
from khayyam import JalaliDatetime
from datetime import datetime
from config import BOT_TOKEN

create_tables()
seed_initial_data()

# ذخیره وضعیت
def save_state(uid, state, data=None):
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO user_states (chat_id, state, data) VALUES (?, ?, ?)",
                 (str(uid), state, json.dumps(data) if data else None))
    conn.commit()
    conn.close()

def get_state(uid):
    conn = get_db_connection()
    row = conn.execute("SELECT state, data FROM user_states WHERE chat_id = ?", (str(uid),)).fetchone()
    conn.close()
    if row:
        data = json.loads(row["data"]) if row["data"] else {}
        return row["state"], data
    return None, {}

# چک کردن غرفه‌دار
def get_vendor_id(uid):
    conn = get_db_connection()
    v = conn.execute("SELECT id, room_number, name FROM vendors WHERE chat_id = ?", (str(uid),)).fetchone()
    conn.close()
    return v

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    vendor = get_vendor_id(user_id)

    keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("دیدن قیمت غرفه‌ها")],
        [KeyboardButton("تغییرات قیمت نسبت به دیروز")],
        [KeyboardButton("ارزان‌ترین غرفه برای هر محصول")],
        [KeyboardButton("اشتراک قیمت روزانه"), KeyboardButton("لغو اشتراک")],
        [KeyboardButton("راهنما")]
    ], resize_keyboard=True)

    if vendor:
        keyboard.keyboard.insert(0, [KeyboardButton("ثبت قیمت امروز")])
        keyboard.keyboard.insert(1, [KeyboardButton("قیمت‌های غرفه من")])

    await update.message.reply_text(
        f"به ربات قیمت میدان میوه و تره‌بار کاشان خوش آمدید!\n\nامروز: {get_today_jalali()}",
        reply_markup=keyboard
    )
    save_state(user_id, "main")

# ثبت غرفه‌دار جدید
async def register_vendor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_vendor_id(user_id):
        await update.message.reply_text("شما قبلاً ثبت‌نام کردید!")
        return
    save_state(user_id, "register_name")
    await update.message.reply_text("نام غرفه خود را وارد کنید:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    state, data = get_state(user_id)
    today = get_today_jalali()
    yesterday = (JalaliDatetime.now() - timedelta(days=1)).strftime('%Y/%m/%d')

    # ثبت‌نام غرفه‌دار
    if state == "register_name":
        save_state(user_id, "register_room", {"name": text})
        await update.message.reply_text("شماره غرفه خود را وارد کنید (مثلاً ۱۲):")
        return
    elif state == "register_room":
        if text.isdigit():
            room = int(text)
            conn = get_db_connection()
            existing = conn.execute("SELECT 1 FROM vendors WHERE room_number = ?", (room,)).fetchone()
            if existing:
                await update.message.reply_text("این شماره غرفه قبلاً ثبت شده! با ادمین تماس بگیرید.")
                conn.close()
                return
            conn.execute("INSERT INTO vendors (chat_id, name, room_number, active) VALUES (?, ?, ?, 1)",
                        (str(user_id), data["name"], room))
            conn.commit()
            conn.close()
            await update.message.reply_text(f"غرفه {data['name']} با شماره {room} ثبت شد!\nحالا می‌تونید قیمت ثبت کنید.")
            save_state(user_id, "main")
            await start(update, context)
        else:
            await update.message.reply_text("فقط عدد وارد کنید!")
        return

    # دیدن قیمت غرفه‌ها
    if text == "دیدن قیمت غرفه‌ها":
        conn = get_db_connection()
        vendors = conn.execute("SELECT room_number, name FROM vendors WHERE active = 1 ORDER BY room_number").fetchall()
        conn.close()
        if not vendors:
            await update.message.reply_text("هیچ غرفه‌ای ثبت نشده.")
            return
        buttons = [[KeyboardButton(f"غرفه {v['room_number']} - {v['name']}")] for v in vendors]
        buttons.append([KeyboardButton("بازگشت")])
        await update.message.reply_text("غرفه مورد نظر:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        save_state(user_id, "choosing_vendor")
        return

    # نمایش قیمت یک غرفه
    elif state == "choosing_vendor" and text.startswith("غرفه "):
        try:
            room = int(text.split()[1])
            conn = get_db_connection()
            vendor = conn.execute("SELECT name, id FROM vendors WHERE room_number = ?", (room,)).fetchone()
            prices = conn.execute("""
                SELECT p.name, pr.price, p.unit 
                FROM prices pr JOIN products p ON pr.product_id = p.id 
                WHERE pr.vendor_id = ? AND pr.date = ?
            """, (vendor["id"], today)).fetchall()
            conn.close()
            if not prices:
                await update.message.reply_text(f"غرفه {vendor['name']}\n\nامروز قیمتی ثبت نشده.")
            else:
                msg = f"قیمت‌های امروز غرفه {vendor['name']} ({today})\n\n"
                for p in prices:
                    msg += f"• {p['name']}: {p['price']:,} تومان {p['unit']}\n"
                await update.message.reply_text(msg)
        except:
            await update.message.reply_text("غرفه اشتباه!")
        return

    # تغییرات قیمت نسبت به دیروز
    elif text == "تغییرات قیمت نسبت به دیروز":
        conn = get_db_connection()
        changes = conn.execute("""
            SELECT p.name, t.price AS today, y.price AS yesterday
            FROM prices t
            JOIN prices y ON t.product_id = y.product_id AND t.vendor_id = y.vendor_id
            JOIN products p ON t.product_id = p.id
            WHERE t.date = ? AND y.date = ?
        """, (today, yesterday)).fetchall()
        conn.close()
        if not changes:
            await update.message.reply_text("تغییری نسبت به دیروز ثبت نشده.")
        else:
            msg = "تغییرات قیمت نسبت به دیروز:\n\n"
            for c in changes:
                diff = c['today'] - c['yesterday']
                if diff > 0:
                    msg += f"{c['name']}: ↑ {diff:,} تومان\n"
                elif diff < 0:
                    msg += f"{c['name']}: ↓ {abs(diff):,} تومان\n"
                else:
                    msg += f"{c['name']}: بدون تغییر\n"
            await update.message.reply_text(msg)
        return

    # ارزان‌ترین غرفه برای هر محصول
    elif text == "ارزان‌ترین غرفه برای هر محصول":
        conn = get_db_connection()
        cheapest = conn.execute("""
            SELECT p.name, pr.price, v.room_number, v.name AS vendor_name
            FROM prices pr
            JOIN products p ON pr.product_id = p.id
            JOIN vendors v ON pr.vendor_id = v.id
            WHERE pr.date = ? AND pr.price = (
                SELECT MIN(price) FROM prices WHERE product_id = p.id AND date = ?
            )
            ORDER BY p.name
        """, (today, today)).fetchall()
        conn.close()
        if not cheapest:
            await update.message.reply_text("امروز قیمتی ثبت نشده.")
        else:
            msg = "ارزان‌ترین غرفه‌ها امروز:\n\n"
            seen = set()
            for c in cheapest:
                key = (c['name'], c['price'])
                if key not in seen:
                    seen.add(key)
                    msg += f"• {c['name']}: {c['price']:,} تومان ← غرفه {c['room_number']} ({c['vendor_name']})\n"
            await update.message.reply_text(msg)
        return

    # ثبت قیمت امروز (فقط غرفه‌دار خودش)
    elif text == "ثبت قیمت امروز":
        vendor = get_vendor_id(user_id)
        if not vendor:
            await update.message.reply_text("ابتدا با /register ثبت‌نام کنید.")
            return
        conn = get_db_connection()
        products = conn.execute("SELECT name FROM products ORDER BY name").fetchall()
        conn.close()
        buttons = [[KeyboardButton(p["name"])] for p in products]
        buttons.append([KeyboardButton("بازگشت")])
        await update.message.reply_text("محصول را انتخاب کنید:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        save_state(user_id, "vendor_select_product", {"vendor_id": vendor["id"]})
        return

    # انتخاب محصول برای ثبت قیمت
    elif state == "vendor_select_product":
        if text == "بازگشت":
            await start(update, context)
            return
        save_state(user_id, "vendor_waiting_price", {"product_name": text, "vendor_id": data["vendor_id"]})
        await update.message.reply_text(f"قیمت امروز «{text}» را وارد کنید:", reply_markup=ForceReply())
        return

    # ثبت قیمت نهایی
    elif state == "vendor_waiting_price" and update.message.reply_to_message:
        if text.isdigit():
            price = int(text)
            conn = get_db_connection()
            conn.execute("""
                INSERT OR REPLACE INTO prices (vendor_id, product_id, price, date)
                VALUES (?, (SELECT id FROM products WHERE name=?), ?, ?)
            """, (data["vendor_id"], data["product_name"], price, today))
            conn.commit()
            conn.close()
            await update.message.reply_text(f"قیمت {data['product_name']} ثبت شد: {price:,} تومان")
            save_state(user_id, "main")
        else:
            await update.message.reply_text("فقط عدد!")
        return

    # قیمت‌های غرفه من
    elif text == "قیمت‌های غرفه من":
        vendor = get_vendor_id(user_id)
        if not vendor:
            await update.message.reply_text("شما غرفه‌دار نیستید.")
            return
        conn = get_db_connection()
        prices = conn.execute("""
            SELECT p.name, pr.price, p.unit 
            FROM prices pr JOIN products p ON pr.product_id = p.id 
            WHERE pr.vendor_id = ? AND pr.date = ?
        """, (vendor["id"], today)).fetchall()
        conn.close()
        if not prices:
            await update.message.reply_text("امروز قیمتی ثبت نکردید.")
        else:
            msg = f"قیمت‌های غرفه شما ({today})\n\n"
            for p in prices:
                msg += f"• {p['name']}: {p['price']:,} تومان {p['unit']}\n"
            await update.message.reply_text(msg)
        return

    # اشتراک/لغو اشتراک
    elif text == "اشتراک قیمت روزانه":
        conn = get_db_connection()
        conn.execute("INSERT OR IGNORE INTO subscribers (chat_id) VALUES (?)", (str(user_id),))
        conn.commit()
        conn.close()
        await update.message.reply_text("اشتراک فعال شد! هر روز صبح قیمت‌ها براتون میاد")
        return
    elif text == "لغو اشتراک":
        conn = get_db_connection()
        conn.execute("DELETE FROM subscribers WHERE chat_id = ?", (str(user_id),))
        conn.commit()
        conn.close()
        await update.message.reply_text("اشتراک لغو شد.")
        return

    # بازگشت و راهنما
    elif text == "بازگشت":
        await start(update, context)
    elif text == "راهنما":
        await update.message.reply_text("ربات قیمت میدان میوه کاشان\n\nبهترین قیمت‌ها رو با ما داشته باشید!")

# ارسال خودکار صبح‌ها
async def daily_broadcast(context: ContextTypes.DEFAULT_TYPE):
    today = get_today_jalali()
    conn = get_db_connection()
    subs = conn.execute("SELECT chat_id FROM subscribers").fetchall()
    prices = conn.execute("""
        SELECT p.name, MIN(pr.price) as price
        FROM prices pr JOIN products p ON pr.product_id = p.id
        WHERE pr.date = ? GROUP BY p.name
    """, (today,)).fetchall()
    conn.close()

    msg = f"قیمت‌های امروز میدان کاشان ({today})\n\n"
    if prices:
        for p in prices:
            msg += f"{p['name']}: {p['price']:,} تومان\n"
        msg += "\nبرای جزئیات به ربات مراجعه کنید!"
    else:
        msg += "هنوز قیمتی ثبت نشده."

    for sub in subs:
        try:
            await context.bot.send_message(chat_id=sub["chat_id"], text=msg)
        except:
            pass

if __name__ == "__main__":
    from datetime import timedelta
    print("ربات قیمت کاشان — نسخه کامل و نهایی فعال شد!")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register_vendor))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # ارسال روزانه ساعت ۸ صبح
    app.job_queue.run_daily(daily_broadcast, time=datetime.strptime("08:00", "%H:%M").time())

    app.run_polling(drop_pending_updates=True)