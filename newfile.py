import telebot
from telebot import types
from datetime import datetime
import sqlite3
import json
import time
import shutil
import re
from threading import Timer, Thread
import os

# ================= CONFIG =================
API_TOKEN = "8245952972:AAF2mkwvxhNyM-mbloyS5yal-jsh62AMc5A"

bot = telebot.TeleBot(API_TOKEN)

PRIMARY_ADMIN_ID = 7683634420
WITHDRAW_ADMIN_ID = 5150723279
SUPPORT_USERNAME = "@Dogreceiversupport"
CHANNEL_LINK = "https://t.me/Dogreceiver"

LOG_CHANNEL_ID = -1003851577544

NUMBER_PROCESS_DELAY = 10
CODE_PROCESS_DELAY = 10
COUNTDOWN_TIME = 600
CODE_EXPIRY_TIME = 120

SPAM_INTERVAL = 3
SPAM_LIMIT = 5
TEMP_BLOCK_TIME = 300

# ================= DATABASE =================
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance REAL DEFAULT 0,
    accounts INTEGER DEFAULT 0,
    numbers TEXT DEFAULT '[]',
    countdowns TEXT DEFAULT '{}',
    stage TEXT DEFAULT '',
    last_message_time REAL DEFAULT 0,
    spam_count INTEGER DEFAULT 0,
    temp_block_until REAL DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS stats (
    id INTEGER PRIMARY KEY,
    total_users INTEGER DEFAULT 0,
    total_numbers INTEGER DEFAULT 0,
    total_confirmed INTEGER DEFAULT 0,
    total_cancelled INTEGER DEFAULT 0,
    total_expired INTEGER DEFAULT 0,
    total_withdrawals INTEGER DEFAULT 0,
    total_paid REAL DEFAULT 0
)
""")

cursor.execute("INSERT OR IGNORE INTO stats (id) VALUES (1)")
conn.commit()

# ================= LOG FUNCTION =================
def send_log(text):
    try:
        bot.send_message(LOG_CHANNEL_ID, f"📒 LOG\n\n{text}")
    except:
        pass

# ================= SPAM PROTECTION =================
def check_spam(user_id):
    cursor.execute("SELECT last_message_time, spam_count, temp_block_until FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if not row:
        return False

    last_time, spam_count, block_until = row

    if time.time() < block_until:
        return True

    if time.time() - last_time < SPAM_INTERVAL:
        spam_count += 1
    else:
        spam_count = 0

    if spam_count >= SPAM_LIMIT:
        block_until = time.time() + TEMP_BLOCK_TIME
        spam_count = 0
    else:
        block_until = 0

    cursor.execute("""
        UPDATE users 
        SET last_message_time=?, spam_count=?, temp_block_until=?
        WHERE user_id=?
    """, (time.time(), spam_count, block_until, user_id))
    conn.commit()

    return time.time() < block_until

# ================= COUNTRY VALIDATION =================
def validate_number(number):
    patterns = {
        "+880": r"^\+8801[3-9]\d{8}$",
        "+91": r"^\+91[6-9]\d{9}$",
        "+1": r"^\+1\d{10}$",
        "+374": r"^\+374\d{8}$",
        "+32": r"^\+32\d{8,9}$",
        "+86": r"^\+86\d{11}$",
        "+94": r"^\+94\d{9}$",
        "+41": r"^\+41\d{9}$",
        "+84": r"^\+84\d{9}$",
        "+972": r"^\+972\d{9}$",
        "+48": r"^\+48\d{9}$",
        "+591": r"^\+591\d{8}$",
        "+55": r"^\+55\d{10,11}$",
        "+60": r"^\+60\d{9,10}$",
        "+968": r"^\+968\d{8}$"
    }

    for code, pattern in patterns.items():
        if number.startswith(code):
            if re.match(pattern, number):
                return True, code
            else:
                return False, None

    return False, None

# ================= BASIC DB FUNCTIONS =================
def ensure_user(user_id):
    cursor.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        cursor.execute("UPDATE stats SET total_users = total_users + 1 WHERE id=1")
        conn.commit()

def get_user_field(user_id, field):
    cursor.execute(f"SELECT {field} FROM users WHERE user_id=?", (user_id,))
    return cursor.fetchone()[0]

def update_user_field(user_id, field, value):
    cursor.execute(f"UPDATE users SET {field}=? WHERE user_id=?", (value, user_id))
    conn.commit()
    # ================= COUNTRY PRICES =================
COUNTRY_PRICES = {
    "+880": 0.18,
    "+91": 0.20,
    "+1": 0.50,
    "+48": 0.20,
    "+374": 1.0,
    "+32": 1.5,
    "+86": 0.85,
    "+94": 0.6,
    "+41": 1.8,
    "+84": 0.18,
    "+972": 0.35,
    "+591": 1.1,
    "+55": 0.4,
    "+60": 0.5,
    "+968": 1.6,
}

# ================= COUNTDOWN =================
def start_countdown(user_id, number, country_code):
    cd = json.loads(get_user_field(user_id, "countdowns"))
    cd[number] = {
        "expiry": time.time() + COUNTDOWN_TIME,
        "code_expiry": time.time() + CODE_EXPIRY_TIME,
        "country_code": country_code,
        "confirmed": False,
        "admin_status": "pending"
    }
    update_user_field(user_id, "countdowns", json.dumps(cd))


# ================= COMMANDS =================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.chat.id
    ensure_user(user_id)

    try:
    bot.send_message(
        user_id,
        "🎉 Welcome aboard!\n\n📱 Enter your phone number to get started.\n\n🌍 You can also use /cap to explore available countries"
    )
except Exception as e:
    print("Send message error:", e)
    update_user_field(user_id, "stage", "number")


@bot.message_handler(commands=['cap'])
def cap_cmd(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🌍 Explore Countries", url=CHANNEL_LINK))
    bot.send_message(message.chat.id, "Click below to go directly to the channel:", reply_markup=markup)


@bot.message_handler(commands=['support'])
def support_cmd(message):
    bot.send_message(message.chat.id, f"📩 Contact Support:\n{SUPPORT_USERNAME}")


@bot.message_handler(commands=['stats'])
def stats_cmd(message):
    if message.chat.id != PRIMARY_ADMIN_ID:
        return

    cursor.execute("SELECT * FROM stats WHERE id=1")
    row = cursor.fetchone()

    text = f"""
📊 BOT STATISTICS

👥 Total Users: {row[1]}
📱 Total Numbers: {row[2]}
✅ Confirmed: {row[3]}
❌ Cancelled: {row[4]}
⌛ Expired: {row[5]}
💸 Withdrawals: {row[6]}
💰 Total Paid: ${row[7]:.2f}
"""
    bot.send_message(PRIMARY_ADMIN_ID, text)


@bot.message_handler(commands=['withdrawal'])
def withdrawal_cmd(message):
    user_id = message.chat.id
    ensure_user(user_id)

    balance = get_user_field(user_id, "balance")
    accounts = get_user_field(user_id, "accounts")

    now = datetime.now().strftime("%H:%M:%S - %Y/%m/%d")

    text = f"🆔 User ID: {user_id}\n☑️ All Accounts: {accounts}\n💰 Balance: ${balance:.2f}\n⏰ Date & Time: {now}"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Settlement Request", callback_data="settlement_request"))

    bot.send_message(user_id, text, reply_markup=markup)


# ================= CALLBACK =================
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.message.chat.id
    data = call.data

    if data == "settlement_request":
        balance = get_user_field(user_id, "balance")

        if balance < 1.0:
            bot.answer_callback_query(call.id)
            bot.send_message(user_id, "🚫 You need at least $1.0 to request a payout.")
            return

        bot.answer_callback_query(call.id)
        bot.send_message(user_id,
            "🏦 Enter your leader code to continue with the settlement process.\n➔ /cancel")

        update_user_field(user_id, "stage", "withdraw")
        return


    if data.startswith("confirm_account:"):
        number = data.split(":")[1]
        cd = json.loads(get_user_field(user_id, "countdowns"))

        if number not in cd:
            bot.answer_callback_query(call.id)
            return

        info = cd[number]

        if info["admin_status"] != "approved":
            bot.answer_callback_query(call.id)
            return

        if info["confirmed"]:
            bot.answer_callback_query(call.id)
            return

        if time.time() < info["expiry"]:
            bot.answer_callback_query(call.id)
            return

        price = COUNTRY_PRICES.get(info["country_code"], 0)

        balance = get_user_field(user_id, "balance")
        accounts = get_user_field(user_id, "accounts")

        update_user_field(user_id, "balance", balance + price)
        update_user_field(user_id, "accounts", accounts + 1)

        cd[number]["confirmed"] = True
        update_user_field(user_id, "countdowns", json.dumps(cd))

        cursor.execute("""
            UPDATE stats 
            SET total_confirmed = total_confirmed + 1,
                total_paid = total_paid + ?
            WHERE id=1
        """, (price,))
        conn.commit()

        try:
            bot.delete_message(user_id, call.message.message_id)
        except:
            pass

        bot.send_message(
            user_id,
            f"🎉 Congratulations, {number} has been verified and ${price:.2f} have been added to your Balance!"
        )

        send_log(f"User {user_id} confirmed {number} | Earned ${price:.2f}")

        bot.answer_callback_query(call.id)
        return


    if data.startswith("admin_approve:") or data.startswith("admin_cancel:"):
        action, target_user_id, number = data.split(":")
        target_user_id = int(target_user_id)

        cd = json.loads(get_user_field(target_user_id, "countdowns"))

        if number not in cd:
            bot.answer_callback_query(call.id)
            return

        if action == "admin_approve":
            cd[number]["admin_status"] = "approved"
            send_log(f"Admin approved {number} for {target_user_id}")
        else:
            cd[number]["admin_status"] = "cancelled"
            cursor.execute("UPDATE stats SET total_cancelled = total_cancelled + 1 WHERE id=1")
            send_log(f"Admin cancelled {number} for {target_user_id}")

        update_user_field(target_user_id, "countdowns", json.dumps(cd))
        conn.commit()

        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.answer_callback_query(call.id)
        return


# ================= MAIN HANDLER =================
@bot.message_handler(func=lambda message: True)
def handle_all(message):
    user_id = message.chat.id
    ensure_user(user_id)

    if check_spam(user_id):
        return

    text = message.text.strip()
    stage = get_user_field(user_id, "stage")

    # NUMBER STAGE
    if stage == "number":
        valid, country_code = validate_number(text)

        if not valid:
            bot.reply_to(message, "❌ Wrong Number Format.")
            return

        cd = json.loads(get_user_field(user_id, "countdowns"))

        if text in cd:
            bot.reply_to(message, "❌ This number has already been submitted.")
            return

        start_countdown(user_id, text, country_code)

        cursor.execute("UPDATE stats SET total_numbers = total_numbers + 1 WHERE id=1")
        conn.commit()

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve:{user_id}:{text}"),
            types.InlineKeyboardButton("❌ Cancel", callback_data=f"admin_cancel:{user_id}:{text}")
        )

        bot.send_message(PRIMARY_ADMIN_ID,
            f"📩 New Number Submission\nUser: {user_id}\nNumber: {text}",
            reply_markup=markup)

        send_log(f"User {user_id} submitted number {text}")

        msg = bot.reply_to(message, "🔄 Please wait...")

        def after_number():
            bot.edit_message_text(
                f"📩 Enter the verification code we sent to {text}\n\n➔ /cancel",
                chat_id=user_id,
                message_id=msg.message_id
            )
            update_user_field(user_id, "stage", "code")

        Timer(NUMBER_PROCESS_DELAY, after_number).start()
        return
        # CODE STAGE
    if stage == "code":
        cd = json.loads(get_user_field(user_id, "countdowns"))
        pending = [n for n, info in cd.items() if not info["confirmed"]]

        if not pending:
            bot.reply_to(message, "❌ No pending number found.")
            update_user_field(user_id, "stage", "number")
            return

        last_number = pending[-1]
        info = cd[last_number]

        # Expired check
        if time.time() > info["code_expiry"]:
            del cd[last_number]
            update_user_field(user_id, "countdowns", json.dumps(cd))

            cursor.execute("UPDATE stats SET total_expired = total_expired + 1 WHERE id=1")
            conn.commit()

            bot.reply_to(message, "❌ Your code has expired.")
            send_log(f"User {user_id} code expired for {last_number}")

            update_user_field(user_id, "stage", "number")
            return

        if not text.isdigit() or len(text) != 5:
            bot.reply_to(message, "❌ Code must be 5 digits.")
            return

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve:{user_id}:{last_number}"),
            types.InlineKeyboardButton("❌ Cancel", callback_data=f"admin_cancel:{user_id}:{last_number}")
        )

        bot.send_message(PRIMARY_ADMIN_ID,
            f"🔐 New Code Submission\nUser: {user_id}\nCode: {text}\nNumber: {last_number}",
            reply_markup=markup)

        send_log(f"User {user_id} submitted code for {last_number}")

        msg = bot.reply_to(message, "⏳ Processing code...")

        def after_code():
            markup_user = types.InlineKeyboardMarkup()
            markup_user.add(
                types.InlineKeyboardButton(
                    "☑️ Confirm Account",
                    callback_data=f"confirm_account:{last_number}"
                )
            )

            bot.edit_message_text(
                f"🔐 Account {last_number} Received!\n\nFor final confirmation, select below. 👉(Automatic confirmation in 10 min)",
                chat_id=user_id,
                message_id=msg.message_id,
                reply_markup=markup_user
            )

            numbers = json.loads(get_user_field(user_id, "numbers"))
            numbers.append(last_number)
            update_user_field(user_id, "numbers", json.dumps(numbers))

            update_user_field(user_id, "stage", "number")

        Timer(CODE_PROCESS_DELAY, after_code).start()
        return

    # WITHDRAW STAGE
    if stage == "withdraw":
        if text == "/cancel":
            bot.send_message(user_id, "❌ Withdrawal process cancelled.")
            update_user_field(user_id, "stage", "")
            return

        balance = get_user_field(user_id, "balance")

        bot.send_message(
            WITHDRAW_ADMIN_ID,
            f"💸 Withdrawal Request\n\n👤 User: {user_id}\n💰 Amount: ${balance:.2f}\n🏦 Leader Code: {text}"
        )

        cursor.execute("UPDATE stats SET total_withdrawals = total_withdrawals + 1 WHERE id=1")
        conn.commit()

        send_log(f"User {user_id} requested withdrawal ${balance:.2f}")

        bot.send_message(user_id,
            f"💰 The settlement process for ${balance:.2f} has been initiated successfully.")

        update_user_field(user_id, "balance", 0)
        update_user_field(user_id, "accounts", 0)
        update_user_field(user_id, "stage", "")
        return


# ================= AUTO BACKUP SYSTEM =================
def daily_backup():
    while True:
        now = datetime.now()
        if now.hour == 0 and now.minute == 0:
            backup_name = f"backup_{now.strftime('%d_%m_%Y')}.db"
            shutil.copy("users.db", backup_name)

            try:
                bot.send_document(LOG_CHANNEL_ID, open(backup_name, "rb"))
                send_log("📦 Daily database backup sent.")
            except:
                pass

            time.sleep(60)
        time.sleep(20)


backup_thread = Thread(target=daily_backup)
backup_thread.daemon = True
backup_thread.start()


# ================= AUTO RECONNECT RUN =================

import logging

logging.basicConfig(level=logging.INFO)

def start_bot():
    while True:
        try:
            print("🚀 Bot Running...")
            bot.infinity_polling(
                timeout=20,
                long_polling_timeout=20,
                skip_pending=True
            )
        except Exception as e:
            print("⚠️ Bot Crashed:", e)
            print("🔄 Reconnecting in 5 seconds...")
            time.sleep(5)

keep_alive()
start_bot()
