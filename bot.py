import os
import requests
import sqlite3
import datetime
import time
import json
import io

# ========== تنظیمات ==========
BOT_TOKEN = "1158952481:3X5SbDumn9F0zPMAY7CbbJXQAki9PBYyM3M"
CHANNEL_ID = 4723912971
# =============================

BASE_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}/"

# --- راه‌اندازی پایگاه داده ---
conn = sqlite3.connect('news.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS news
             (id INTEGER PRIMARY KEY, 
              news_text TEXT, 
              category TEXT, 
              link TEXT, 
              published_at TEXT)''')
conn.commit()

user_data = {}

# ==================== توابع ====================

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

def send_document(chat_id, file_data, filename):
    """ارسال فایل به کاربر"""
    url = BASE_URL + "sendDocument"
    try:
        files = {
            'document': (filename, file_data, 'text/plain')
        }
        data = {
            'chat_id': chat_id
        }
        response = requests.post(url, data=data, files=files, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Error sending document: {e}")
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

# ==================== تابع تولید گزارش فایل ====================

def generate_report_file():
    try:
        c.execute("SELECT * FROM news ORDER BY category, published_at DESC")
        rows = c.fetchall()
        
        if not rows:
            return None, "هنوز هیچ خبری ذخیره نشده است."
        
        # گروه‌بندی بر اساس دسته‌بندی
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
        
        # ساخت محتوای فایل (فرمت TXT)
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
        
        # تبدیل به فایل (UTF-8)
        file_data = io.BytesIO(content.encode('utf-8'))
        filename = f"report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        return file_data, filename
        
    except Exception as e:
        return None, f"❌ خطا در تولید گزارش: {e}"

# ==================== حلقه اصلی ====================

print("🤖 Robat dar hale ejra ast...")
print("[*] Dar hal entezar baraye daryaft update ha...")
print("[*] Baraye test, yek payam be robat bedeid.")

last_update_id = 0

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
                
                print(f"[+] Payam daryaft shod az {user_id}: {text}")
                
                # --- Command /start ---
                if text == "/start":
                    send_message(user_id,
                        "👋 Salam! Man robat modiriyat khabar hastam.\n\n"
                        "Baraye ersal khabar jadid: /sendnews\n"
                        "Baraye daryaft report: /report"
                    )
                
                # --- Command /sendnews ---
                elif text == "/sendnews":
                    user_data[user_id] = {}
                    send_message(user_id, "📝 lotfan **matn khabar** ro ersal kon:")
                
                # --- Command /report ---
                elif text == "/report":
                    file_data, filename = generate_report_file()
                    if file_data:
                        # ارسال فایل به کاربر
                        result = send_document(user_id, file_data, filename)
                        if result.get("ok"):
                            send_message(user_id, "✅ فایل گزارش با موفقیت ارسال شد.")
                        else:
                            send_message(user_id, "❌ خطا در ارسال فایل گزارش.")
                    else:
                        send_message(user_id, filename)  # filename در اینجا پیام خطا است
                
                # --- دریافت متن و دسته‌بندی ---
                elif user_id in user_data:
                    data = user_data[user_id]
                    
                    if 'text' not in data:
                        data['text'] = text
                        send_message(user_id, "🏷️ hala **daste bandi** khabar ro vared kon (masalan: siasi, varzeshi, fanavari):")
                    
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
                                    f"✅ Khabar ba movafaghiat dar channel montesher shod!\n\n"
                                    f"📎 Link: {post_link}\n"
                                    f"🏷️ Daste bandi: {category}"
                                )
                            else:
                                send_message(user_id, "❌ Khata dar ersal khabar be channel. Motmaen shavid robat admin channel ast.")
                            
                        except Exception as e:
                            send_message(user_id, f"❌ Khata: {e}")
                        
                        del user_data[user_id]
        
        time.sleep(1)
        
    except Exception as e:
        print(f"Khata dar halghe asli: {e}")
        time.sleep(5)