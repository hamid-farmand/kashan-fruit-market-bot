import os
from dotenv import load_dotenv

load_dotenv()

# توکن ربات بله رو از @BotFather بگیر و اینجا بذار
BOT_TOKEN = os.getenv("BOT_TOKEN", "توکن_ربات_بله_تو_اینجا")

# آیدی عددی ادمین (اختیاری - بعداً می‌تونی بذاری)
# برای پیدا کردن آیدی خودت، به @userinfobot پیام بده و عدد رو کپی کن
try:
    ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
except:
    ADMIN_CHAT_ID = 0  # یا هر عددی که دوست داری