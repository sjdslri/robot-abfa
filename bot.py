import os
import requests
import sqlite3
import datetime
import time
import json
import io
from keep_alive import keep_alive

#تنظیمات از متغیرهای محیطی
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise Exception("❌ توکن ربات پیدا نشد! متغیر محیطی BOT_TOKEN را تنظیم کنید.")

CHANNEL_ID = os.environ.get("CHANNEL_ID")
if not CHANNEL_ID:
    raise Exception("❌ شناسه کانال پیدا نشد! متغیر محیطی CHANNEL_ID را تنظیم کنید.")
else:
    CHANNEL_ID = int(CHANNEL_ID)

ADMIN_ID = int(os.environ.get("ADMIN_ID", "454792198"))

BASE_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}/"

# پایگاه داده
conn = sqlite3.connect('news.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS news
             (id INTEGER PRIMARY KEY, 
              news_text TEXT, 
              category TEXT, 
              link TEXT, 
              published_at TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS allowed_users
             (user_id INTEGER PRIMARY KEY, 
              added_at TEXT)''')

#اضافه کردن ادمین
c.execute("INSERT OR IGNORE INTO allowed_users (user_id, added_at) VALUES (?, ?)", 
          (ADMIN_ID, datetime.datetime.now().isoformat()))
conn.commit()

user_data = {}

#توابع

def is_allowed(user_id):
    c.execute("SELECT * FROM allowed_users WHERE user_id = ?", (user_id,))
    return c.fetchone() is not None

def add_user(user_id):
    try:
        c.execute("INSERT INTO allowed_users (user_id, added_at) VALUES (?, ?)", 
                  (user_id, datetime.datetime.now().isoformat()))
        conn.commit()
        return True
    except:
        return False

def remove_user(user_id):
    c.execute("DELETE FROM allowed_users WHERE user_id = ?", (user_id,))
    conn.commit()
    return c.rowcount > 0

def get_allowed_users():
    c.execute("SELECT user_id FROM allowed_users")
    return [row[0] for row in c.fetchall()]

def send_message(chat_id, text):
    url = BASE_URL + "sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    for attempt in range(5):
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200 and response.text:
                return response.json()
            else:
                print(f"[!] Send attempt {attempt+1} failed: {response.status_code}")
                time.sleep(2)
        except Exception as e:
            print(f"[!] Send attempt {attempt+1} error: {e}")
            time.sleep(2)
    return {"ok": False}

def get_updates(offset=None):
    url = BASE_URL + "getUpdates"
    payload = {"offset": offset, "timeout": 30}
    for attempt in range(5):
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200 and response.text:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    print(f"[!] Update attempt {attempt+1}: invalid JSON")
                    time.sleep(2)
                    continue
            else:
                print(f"[!] Update attempt {attempt+1} failed: {response.status_code}")
                time.sleep(2)
        except Exception as e:
            print(f"[!] Update attempt {attempt+1} error: {e}")
            time.sleep(2)
    return {"ok": False, "result": []}

def send_document(chat_id, file_data, filename):
    url = BASE_URL + "sendDocument"
    try:
        files = {'document': (filename, file_data, 'text/plain')}
        data = {'chat_id': chat_id}
        response = requests.post(url, data=data, files=files, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Error sending document: {e}")
        return {"ok": False}

def generate_report_file():
    try:
        c.execute("SELECT * FROM news ORDER BY category, published_at DESC")
        rows = c.fetchall()
        if not rows:
            return None, "هنوز هیچ خبری ذخیره نشده است."
        
        categories = {}
        for row in rows:
            news_id, news_text, category, link, published_at = row
            if category not in categories:
                categories[category] = []
            categories[category].append({
                'id': news_id,
                'text': news_text,
                'link': link,
                'date': published_at
            })
        
        content = "📊 گزارش دسته‌بندی اخبار\n"
        content += "=" * 50 + "\n"
        content += f"تاریخ تولید: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += "=" * 50 + "\n\n"
        
        for category, items in categories.items():
            content += f"🏷️ دسته‌بندی: {category}\n"
            content += "-" * 40 + "\n"
            for i, item in enumerate(items, 1):
                content += f"{i}. {item['text']}\n"
                content += f"   📎 لینک: {item['link']}\n"
                content += f"   📅 تاریخ: {item['date']}\n\n"
            content += "\n"
        
        content += f"📈 مجموع اخبار: {len(rows)} عدد\n"
        
        file_data = io.BytesIO(content.encode('utf-8'))
        filename = f"report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        return file_data, filename
        
    except Exception as e:
        return None, f"❌ خطا در تولید گزارش: {e}"

#حلقه اصلی

print("🤖 Robat dar hale ejra ast...")
print("[*] Dar hal entezar baraye daryaft update ha...")

last_update_id = 0

if __name__ == "__main__":
    keep_alive()
    while True:
        try:
            updates = get_updates(offset=last_update_id + 1)
            
            if updates.get("ok") and updates.get("result"):
                for update in updates["result"]:
                    last_update_id = update["update_id"]
                    message = update.get("message")
                    if not message:
                        continue
                    
                    if "from" in message:
                        user_id = message["from"]["id"]
                    else:
                        user_id = 0
                    
                    text = message.get("text", "")
                    
                    #بررسی دسترسی
                    if not is_allowed(user_id):
                        send_message(user_id, "⛔ شما دسترسی استفاده از این ربات را ندارید.")
                        continue
                    
                    print(f"[+] Payam daryaft shod az {user_id}: {text}")
                    
                    # --- Command /start ---
                    if text == "/start":
                        send_message(user_id,
                            "👋 سلام! من ربات مدیریت اخبار هستم.\n\n"
                            "برای ارسال خبر جدید: /sendnews\n"
                            "برای دریافت گزارش: /report\n\n"
                            "📌 دستورات مدیریتی (فقط ادمین):\n"
                            "/adduser [شناسه] - اضافه کردن کاربر\n"
                            "/removeuser [شناسه] - حذف کاربر\n"
                            "/users - لیست کاربران مجاز"
                        )
                    
                    #Command /sendnews
                    elif text == "/sendnews":
                        user_data[user_id] = {}
                        send_message(user_id, "📝 لطفاً **متن خبر** را ارسال کن:")
                    
                    #Command /report
                    elif text == "/report":
                        file_data, filename = generate_report_file()
                        if file_data:
                            result = send_document(user_id, file_data, filename)
                            if result.get("ok"):
                                send_message(user_id, "✅ فایل گزارش با موفقیت ارسال شد.")
                            else:
                                send_message(user_id, "❌ خطا در ارسال فایل گزارش.")
                        else:
                            send_message(user_id, filename)
                    
                    #دستورات مدیریتی (فقط ادمین)
                    elif text.startswith("/adduser") and user_id == ADMIN_ID:
                        parts = text.split()
                        if len(parts) == 2:
                            try:
                                new_user_id = int(parts[1])
                                if add_user(new_user_id):
                                    send_message(user_id, f"✅ کاربر {new_user_id} به لیست اضافه شد.")
                                else:
                                    send_message(user_id, f"❌ کاربر {new_user_id} در لیست وجود دارد.")
                            except ValueError:
                                send_message(user_id, "❌ لطفاً شناسه را به صورت عدد وارد کنید.")
                        else:
                            send_message(user_id, "❌ فرمت: /adduser [شناسه]")
                    
                    elif text.startswith("/removeuser") and user_id == ADMIN_ID:
                        parts = text.split()
                        if len(parts) == 2:
                            try:
                                remove_user_id = int(parts[1])
                                if remove_user(remove_user_id):
                                    send_message(user_id, f"✅ کاربر {remove_user_id} از لیست حذف شد.")
                                else:
                                    send_message(user_id, f"❌ کاربر {remove_user_id} در لیست وجود ندارد.")
                            except ValueError:
                                send_message(user_id, "❌ لطفاً شناسه را به صورت عدد وارد کنید.")
                        else:
                            send_message(user_id, "❌ فرمت: /removeuser [شناسه]")
                    
                    elif text == "/users" and user_id == ADMIN_ID:
                        users = get_allowed_users()
                        if users:
                            msg = "📋 لیست کاربران مجاز:\n" + "\n".join([f"- {u}" for u in users])
                        else:
                            msg = "📭 هیچ کاربری در لیست وجود ندارد."
                        send_message(user_id, msg)
                    
                    #دریافت متن و دسته‌بندی
                    elif user_id in user_data:
                        data = user_data[user_id]
                        
                        if 'text' not in data:
                            data['text'] = text
                            send_message(user_id, "🏷️  **دسته‌بندی** خبر را وارد کنید (مثلاً: سیاسی، ورزشی، فناوری):")
                        
                        elif 'category' not in data:
                            category = text
                            news_text = data['text']
                            
                            try:
                                result = send_message(CHANNEL_ID, news_text)
                                
                                if result.get("ok"):
                                    message_id = result["result"]["message_id"]
                                    post_link = f"https://ble.ir/c/{CHANNEL_ID}/{message_id}"
                                    
                                    now = datetime.datetime.now().isoformat()
                                    c.execute(
                                        "INSERT INTO news (news_text, category, link, published_at) VALUES (?, ?, ?, ?)",
                                        (news_text, category, post_link, now)
                                    )
                                    conn.commit()
                                    
                                    send_message(user_id,
                                        f"✅ خبر با موفقیت در کانال منتشر شد!\n\n"
                                        f"📎 لینک: {post_link}\n"
                                        f"🏷️ دسته‌بندی: {category}"
                                    )
                                else:
                                    send_message(user_id, "❌ خطا در ارسال خبر به کانال. مطمئن شوید ربات ادمین کانال است.")
                                
                            except Exception as e:
                                send_message(user_id, f"❌ خطا: {e}")
                            
                            del user_data[user_id]
            
            time.sleep(1)
            
        except Exception as e:
            print(f"Khata dar halghe asli: {e}")
            time.sleep(5)