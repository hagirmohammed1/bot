from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
)
from hijridate import Gregorian
from datetime import datetime
import pytz
import json
import os
import asyncio

# ================== الإعدادات ==================
TOKEN = os.environ.get("BOT_TOKEN")
DATA_FILE = "turns.json"
if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

STATES = ["مستمع", "متأخر", "حاضر", "تم"]
STATE_EMOJIS = {"مستمع": "⏳", "متأخر": "⚠️", "حاضر": "✅", "تم": "✔️"}
active_messages = {}

# ================== التحقق من المشرف ==================
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    if chat.type == "private":
        return True
    member = await context.bot.get_chat_member(chat.id, user.id)
    return member.status in ("administrator", "creator")

async def deny_non_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not await is_admin(update, context):
        try:
            await update.message.delete()
        except:
            pass
        try:
            warn = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ هذا الأمر مخصص للمشرفين فقط."
            )
            await asyncio.sleep(3)
            await warn.delete()
        except:
            pass
        return True
    return False

# ================== إدارة البيانات ==================
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ================== التاريخ ==================
def current_dates():
    tz = pytz.timezone("Africa/Cairo")
    now = datetime.now(tz)
    days_ar = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
    day_name = days_ar[now.weekday()]
    miladi = now.strftime("%d/%m/%Y %H:%M")
    hijri = Gregorian(now.year, now.month, now.day).to_hijri()
    hijri_str = f"{hijri.day:02d}/{hijri.month}/{hijri.year} هـ"
    return f"التاريخ (القاهرة):\nاليوم: {day_name}\nميلادي: {miladi}\nهجري: {hijri_str}\n\n"

# ================== القائمة ==================
def main_menu():
    keyboard = [[KeyboardButton("/turns")], [KeyboardButton("/stop_turns"), KeyboardButton("/clear_turns")], [KeyboardButton("/menu")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await deny_non_admin(update, context):
        return
    await update.message.reply_text("قائمة أوامر البوت:", reply_markup=main_menu())
    await update.message.delete()

# ================== بناء الرسالة ==================
def build_message(chat_id):
    data = load_data()
    turns = data.get(chat_id, {})
    header = current_dates()
    if not turns:
        return header + "لا توجد تسجيلات حالياً."
    sections = {state: [] for state in STATES}
    max_turn = max([int(k) for k in turns.keys()], default=0)
    for i in range(1, max_turn + 1):
        if str(i) in turns:
            user, state = turns[str(i)]
            emoji = STATE_EMOJIS.get(state, "")
            sections[state].append(f"{i}. {emoji} {user}")
    msg = header + "قائمة الأدوار الحالية:\n\n"
    for state in STATES:
        if sections[state]:
            msg += f"{state}:\n" + "\n".join(sections[state]) + "\n\n"
    return msg.strip()

# ================== الأزرار ==================
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

# ================== أوامر المشرف ==================
async def turns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await deny_non_admin(update, context):
        return
    chat_id = str(update.effective_chat.id)
    username = update.effective_user.first_name
    await update.message.delete()
    if chat_id in active_messages:
        await context.bot.delete_message(chat_id, active_messages[chat_id])
    sent = await context.bot.send_message(chat_id, build_message(chat_id), reply_markup=build_keyboard(chat_id, username))
    active_messages[chat_id] = sent.message_id

async def stop_turns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if aait deny_non_admin(update, context):
        return
    chat_id = str(update.effective_chat.id)
    await update.message.delete()
    if chat_id in active_messages:
        await context.bot.delete_message(chat_id, active_messages[chat_id])
        del active_messages[chat_id]
    await context.bot.send_message(chat_id, "تم إيقاف القائمة دون حذف الادوار .")

async def clear_turns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await deny_non_admin(update, context):
        return
    chat_id = str(update.effective_chat.id)
    data = load_data()
    data[chat_id] = {}
    save_data(data)
    await update.message.delete()
    await context.bot.send_message(chat_id, "تم مسح جميع الأدوار.")

# ================== الأزرار للجميع ==================
async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat.id)
    username = query.from_user.first_name
    data = load_data()
    data.setdefault(chat_id, {})
    if query.data.startswith("take_"):
        if any(v[0] == username for v in data[chat_id].values()):
            await query.answer("لديك دور بالفعل", show_alert=True)
            return
        num = query.data.split("_")[1]
        data[chat_id][num] = [username, "مستمع"]
    elif query.data.startswith("change_"):
        num = query.data.split("_")[1]
        await query.edit_message_text("اختر الحالة الجديدة:", reply_markup=build_keyboard(chat_id, username, state_menu=num))
        return
    elif query.data.startswith("setstate_"):
        _, num, state = query.data.split("_")
        data[chat_id][num] = [username, state]
    elif query.data == "leave":
        for k in list(data[chat_id].keys()):
            if data[chat_id][k][0] == username:
                del data[chat_id][k]
    save_data(data)
    if chat_id in active_messages:
        await context.bot.delete_message(chat_id, active_messages[chat_id])
    sent = await context.bot.send_message(chat_id, build_message(chat_id), reply_markup=build_keyboard(chat_id, username))
    active_messages[chat_id] = sent.message_id

# ================== التشغيل ==================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    # ✅ أوامر المشرف
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("turns", turns))
    app.add_handler(CommandHandler("stop_turns", stop_turns))
    app.add_handler(CommandHandler("clear_turns", clear_turns))

    # 🟢 الأزرار للجميع
    app.add_handler(CallbackQueryHandler(handler))

    app.run_polling(drop_pending_updates=True)
w
