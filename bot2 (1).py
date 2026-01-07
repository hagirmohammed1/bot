from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from hijri_converter import convert
from datetime import datetime
import pytz
import json
import os
import asyncio

TOKEN = "8569656006:AAHuUzotAqOLsVoMMQL7csAv1OuYnDu_YCs"
DATA_FILE = "turns.json"

STATES = ["مستمع", "متأخر", "حاضر", "تم"]
STATE_EMOJIS = {"مستمع": "⏳", "متأخر": "⚠️", "حاضر": "✅", "تم": "✔️"}
active_messages = {}  # حفظ الرسائل الحالية في كل جروب

# ------------------- إدارة البيانات -------------------
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ------------------- التاريخ الرسمي + الساعة + اليوم -------------------
def current_dates():
    tz = pytz.timezone("Africa/Cairo")
    now = datetime.now(tz)
    days_ar = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
    day_name = days_ar[now.weekday()]
    miladi = now.strftime("%d/%m/%Y %H:%M")
    hijri = convert.Gregorian(now.year, now.month, now.day).to_hijri()
    hijri_str = f"{hijri.day:02d}/{hijri.month}/{hijri.year} هـ"
    return f"📆 التاريخ (القاهرة):\n• اليوم: {day_name}\n• ميلادي: {miladi}\n• هجري: {hijri_str}\n\n"

# ------------------- قائمة Menu -------------------
def main_menu():
    keyboard = [
        [KeyboardButton("/turns")],
        [KeyboardButton("/stop_turns"), KeyboardButton("/clear_turns")],
        [KeyboardButton("/menu")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📋 قائمة أوامر البوت:", reply_markup=main_menu())
    try:
        await asyncio.sleep(0.1)
        await update.message.delete()
    except:
        pass

# ------------------- بناء الرسالة الرسمية -------------------
def build_message(chat_id):
    data = load_data()
    turns = data.get(chat_id, {})

    header = current_dates()
    if not turns:
        return header + "📌 لا توجد تسجيلات حالياً."

    sections = {state: [] for state in STATES}
    max_turn = max([int(k) for k in turns.keys()], default=0)
    for i in range(1, max_turn + 1):
        if str(i) in turns:
            user, state = turns[str(i)]
            emoji = STATE_EMOJIS.get(state, "")
            sections[state].append(f"{i}. {emoji} {user}")

    msg = header + "📌 قائمة الأدوار الحالية:\n\n"
    for state in STATES:
        if sections[state]:
            msg += f"{state}:\n" + "\n".join(sections[state]) + "\n\n"

    return msg.strip()

# ------------------- بناء أزرار المستخدم -------------------
def build_keyboard(chat_id, username=None, state_menu=None):
    data = load_data()
    turns = data.get(chat_id, {})
    max_turn = max([int(k) for k in turns.keys()], default=0)
    keyboard = []

    if state_menu:
        for state in STATES:
            keyboard.append([InlineKeyboardButton(state, callback_data=f"setstate_{state_menu}_{state}")])
        keyboard.append([InlineKeyboardButton("الرجوع", callback_data="back")])
    else:
        user_has_role = any(v[0] == username for v in turns.values()) if username else False
        for i in range(1, max_turn + 2):
            if str(i) in turns:
                user, _ = turns[str(i)]
                if user == username:
                    keyboard.append([InlineKeyboardButton(f"تغيير حالة دوري {i}", callback_data=f"change_{i}")])
            else:
                if not user_has_role:
                    keyboard.append([InlineKeyboardButton(f"حجز دور جديد {i}", callback_data=f"take_{i}")])
        if user_has_role:
            keyboard.append([InlineKeyboardButton("إلغاء تسجيلي", callback_data="leave")])
        keyboard.append([InlineKeyboardButton("تحديث القائمة", callback_data="refresh")])

    return InlineKeyboardMarkup(keyboard)

# ------------------- أوامر البوت -------------------
async def turns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    username = update.effective_user.first_name

    # حذف رسالة المستخدم مع تأخير صغير للتأكد
    try:
        await asyncio.sleep(0.5)
        await update.message.delete()
    except:
        pass

    # حذف أي رسالة قائمة سابقة
    if chat_id in active_messages:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=active_messages[chat_id])
        except:
            pass

    # إرسال القائمة الجديدة
    sent_msg = await context.bot.send_message(
        chat_id=chat_id,
        text=build_message(chat_id),
        reply_markup=build_keyboard(chat_id, username=username)
    )
    active_messages[chat_id] = sent_msg.message_id

async def stop_turns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    try:
        await asyncio.sleep(0.1)
        await update.message.delete()
    except:
        pass

    if chat_id in active_messages:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=active_messages[chat_id])
            await context.bot.send_message(chat_id=chat_id, text="✅ تم حذف القائمة الحالية.")
        except:
            await context.bot.send_message(chat_id=chat_id, text="⚠️ لم أتمكن من حذف رسالة القائمة.")
        del active_messages[chat_id]
    else:
        await context.bot.send_message(chat_id=chat_id, text="⚠️ لا توجد رسالة قائمة حالياً.")

async def clear_turns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    try:
        await asyncio.sleep(0.1)
        await update.message.delete()
    except:
        pass

    data = load_data()
    data[chat_id] = {}
    save_data(data)
    await context.bot.send_message(chat_id=chat_id, text="✅ تم مسح جميع الأدوار وإعادة تعيين القائمة.")

# ------------------- التعامل مع الأزرار -------------------
async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat.id)
    username = query.from_user.first_name

    data = load_data()
    data.setdefault(chat_id, {})

    if query.data.startswith("take_"):
        if any(v[0] == username for v in data[chat_id].values()):
            await query.answer("⚠️ لا يمكنك حجز أكثر من دور واحد.", show_alert=True)
            return
        num = query.data.split("_")[1]
        data[chat_id][num] = [username, "مستمع"]
        save_data(data)

    elif query.data.startswith("change_"):
        num = query.data.split("_")[1]
        if num in data[chat_id] and data[chat_id][num][0] == username:
            await query.edit_message_text(
                "📌 اختر الحالة الجديدة:",
                reply_markup=build_keyboard(chat_id, username, state_menu=num)
            )
            return
        else:
            await query.answer("⚠️ لا يمكنك تعديل هذا الدور.", show_alert=True)

    elif query.data.startswith("setstate_"):
        _, num, new_state = query.data.split("_")
        if num in data[chat_id] and data[chat_id][num][0] == username:
            data[chat_id][num] = [username, new_state]
            save_data(data)
        else:
            await query.answer("⚠️ لا يمكنك تعديل هذا الدور.", show_alert=True)

    elif query.data == "leave":
        to_delete = None
        for k, v in data[chat_id].items():
            if v[0] == username:
                to_delete = k
                break
        if to_delete:
            del data[chat_id][to_delete]
            save_data(data)

    # حذف الرسالة القديمة وإرسال نسخة محدثة
    if chat_id in active_messages:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=active_messages[chat_id])
        except:
            pass

    sent_msg = await context.bot.send_message(
        chat_id=chat_id,
        text=build_message(chat_id),
        reply_markup=build_keyboard(chat_id, username=username)
    )
    active_messages[chat_id] = sent_msg.message_id

# ------------------- تسجيل الأوامر -------------------
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("menu", menu))
app.add_handler(CommandHandler("turns", turns))
app.add_handler(CommandHandler("stop_turns", stop_turns))
app.add_handler(CommandHandler("clear_turns", clear_turns))
app.add_handler(CallbackQueryHandler(handler))
app.run_polling()
