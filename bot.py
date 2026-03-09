import telebot
import sqlite3
import random
import time
import threading
import urllib.request
import csv
import io
from flask import Flask

# ⚠️ यहाँ अपना NAYA वाला Token डालें जो अभी BotFather से लिया था
TOKEN = '8632941188:AAFYQvnBUO8jhqvbE5MA_8M06q0daQ0_sjs' 
bot = telebot.TeleBot(TOKEN)

# अब TARGET_GROUP की कोई ज़रूरत नहीं!
PROMO_CHANNEL = '@authentic_info_2025'       
SHEET_CSV_URL = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vQaiENWJ4C_RDbkEpLbwcevoK-Zx7HMfWyMBTAXKSLdKz6o-jD8EYV9mxRVumnFO2ujzeQ-M2zOitjG/pub?output=csv'  # 👈 अपना CSV लिंक यहाँ डालें

# --- Web Server ---
app = Flask(__name__)
@app.route('/')
def home():
    return "Authentic Info Quiz Bot Zinda Hai!"

def run_server():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run_server)
    t.start()

# --- Database Setup ---
def setup_db():
    conn = sqlite3.connect('quiz_database.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT, score INTEGER)''')
    conn.commit()
    conn.close()

setup_db()

active_polls = {}
is_auto_posting = False 
current_question_index = 0
shuffled_questions = []

# 👈 NAYA JUGAD: जो ग्रुप में कमांड आएगा, बॉट उसकी ID यहाँ सेव कर लेगा
active_chat_id = None  

# --- Google Sheet Fetcher ---
def fetch_questions_from_sheet():
    questions_list = []
    try:
        response = urllib.request.urlopen(SHEET_CSV_URL)
        csv_data = response.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(csv_data))
        
        for row in reader:
            if not row['Question'].strip(): continue
            q = row['Question']
            opts = [row['Option1'], row['Option2'], row['Option3'], row['Option4']]
            corr_idx = int(row['CorrectOption']) - 1 
            exp = row['Explanation']
            
            questions_list.append({"question": q, "options": opts, "correct_index": corr_idx, "explanation": exp})
        print(f"✅ Sheet से {len(questions_list)} सवाल लोड हो गए!")
        return questions_list
    except Exception as e:
        print(f"❌ Sheet Error: {e}")
        return []

# --- Helper Functions ---
def is_user_admin(message):
    if message.from_user.username == 'GroupAnonymousBot': return True
    if message.sender_chat and message.sender_chat.id == message.chat.id: return True
    try:
        # 👈 अब बॉट फिक्स ग्रुप की जगह, करेंट ग्रुप (message.chat.id) में एडमिन चेक करेगा
        return bot.get_chat_member(message.chat.id, message.from_user.id).status in ['creator', 'administrator']
    except:
        return False

def send_leaderboard(chat_id):
    conn = sqlite3.connect('quiz_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 10")
    top_users = cursor.fetchall()
    conn.close()
    
    if not top_users:
        bot.send_message(chat_id, "अभी तक किसी ने सही उत्तर नहीं दिया है!")
        return
        
    text = f"🏆 **आज का फाइनल लीडरबोर्ड** 🏆\n👉 *Join: {PROMO_CHANNEL}*\n\n"
    for i, user in enumerate(top_users): text += f"{i+1}. {user[0]} : {user[1]} Points\n"
    bot.send_message(chat_id, text, parse_mode="Markdown")

# --- Admin Commands ---
@bot.message_handler(commands=['start_quiz'])
def start_auto_quiz(message):
    global is_auto_posting, current_question_index, shuffled_questions, active_chat_id
    
    if not is_user_admin(message): return bot.reply_to(message, "❌ Access Denied!")
    if is_auto_posting: return bot.reply_to(message, "⚠️ क्विज़ चालू है!")

    fresh_questions = fetch_questions_from_sheet()
    if not fresh_questions: return bot.reply_to(message, "❌ शीट खाली है या लिंक गलत है!")

    conn = sqlite3.connect('quiz_database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users")  
    conn.commit()
    conn.close()

    is_auto_posting = True
    current_question_index = 0
    
    # 👈 बॉट ने यहाँ चालू होने वाले ग्रुप की ID याद कर ली
    active_chat_id = message.chat.id  
    
    shuffled_questions = random.sample(fresh_questions, len(fresh_questions)) 
    bot.reply_to(message, f"✅ Auto-Quiz शुरू! कुल {len(shuffled_questions)} प्रश्न।\n\n📢 Join and Share: {PROMO_CHANNEL}")

@bot.message_handler(commands=['stop_quiz'])
def stop_auto_quiz(message):
    global is_auto_posting
    if not is_user_admin(message): return bot.reply_to(message, "❌ Access Denied!")
    is_auto_posting = False
    bot.reply_to(message, "🛑 Auto-Quiz रोक दिया गया है।")
    send_leaderboard(message.chat.id) # 👈 उसी ग्रुप में लीडरबोर्ड जाएगा

# --- Auto Post Function ---
def auto_send_quiz():
    global is_auto_posting, current_question_index, active_chat_id
    while True:
        if is_auto_posting and active_chat_id is not None:
            time.sleep(5)
            while is_auto_posting and current_question_index < len(shuffled_questions):
                try:
                    q_data = shuffled_questions[current_question_index]
                    promo_text = f"{q_data['explanation']}\n\n📢 Join {PROMO_CHANNEL}"
                    q_text = f"Q{current_question_index + 1}. {q_data['question']}"
                    
                    # 👈 फिक्स ग्रुप की जगह active_chat_id का इस्तेमाल
                    msg = bot.send_poll(chat_id=active_chat_id, question=q_text, options=q_data["options"], type='quiz', correct_option_id=q_data["correct_index"], explanation=promo_text, is_anonymous=False, open_period=30)
                    active_polls[msg.poll.id] = q_data["correct_index"]
                    current_question_index += 1
                except Exception as e:
                    print(e)
                for _ in range(30):
                    if not is_auto_posting: break
                    time.sleep(1)
                if is_auto_posting and current_question_index >= len(shuffled_questions):
                    is_auto_posting = False
                    bot.send_message(active_chat_id, "🏁 आज के सभी प्रश्न समाप्त हुए!")
                    send_leaderboard(active_chat_id)
                    break
        else: time.sleep(1)

# --- Poll Answer Handler ---
@bot.poll_answer_handler()
def handle_poll_answer(pollAnswer):
    if not pollAnswer.option_ids: return
    poll_id = pollAnswer.poll_id
    user_id = pollAnswer.user.id
    name = pollAnswer.user.first_name
    selected_option = pollAnswer.option_ids[0]

    if poll_id in active_polls and selected_option == active_polls[poll_id]:
        conn = sqlite3.connect('quiz_database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT score FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result: cursor.execute("UPDATE users SET score = ? WHERE user_id = ?", (result[0] + 1, user_id))
        else: cursor.execute("INSERT INTO users (user_id, name, score) VALUES (?, ?, ?)", (user_id, name, 1))
        conn.commit()
        conn.close()

# --- Start Everything ---
threading.Thread(target=auto_send_quiz, daemon=True).start()

keep_alive()

print("🌟 Smart 24/7 Bot Ready!")
bot.polling(none_stop=True, allowed_updates=['message', 'poll', 'poll_answer'])
