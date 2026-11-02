import asyncio
import io
import json
import math
import os
import random
import time
import traceback
import uuid
from datetime import datetime, timezone, timedelta

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    ForceReply,
    Message,
    CallbackQuery,
    Bot,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters,
    ChatMemberHandler,
)
from telegram.error import BadRequest, RetryAfter
import re

# =========================================================
# АВТОМАТИЧЕСКАЯ ЗАЩИТА ОТ ОШИБОК ДЕКОРАТИВНЫХ ЭМОДЗИ (Document_invalid)
# =========================================================

def strip_tg_emojis(text: str) -> str:
    """Безопасно удаляет теги <tg-emoji>, оставляя только стандартные эмодзи-плейсхолдеры."""
    if not isinstance(text, str):
        return text
    return re.sub(r'<tg-emoji[^>]*>(.*?)</tg-emoji>', r'\1', text)

def patch_telegram_methods():
    orig_reply_text = Message.reply_text
    async def safe_reply_text(self, text, *args, **kwargs):
        try:
            return await orig_reply_text(self, text, *args, **kwargs)
        except BadRequest as e:
            if "document_invalid" in str(e).lower():
                clean_text = strip_tg_emojis(text)
                return await orig_reply_text(self, clean_text, *args, **kwargs)
            raise e
    Message.reply_text = safe_reply_text

    orig_edit_message_text = CallbackQuery.edit_message_text
    async def safe_edit_message_text(self, text, *args, **kwargs):
        try:
            return await orig_edit_message_text(self, text, *args, **kwargs)
        except BadRequest as e:
            if "document_invalid" in str(e).lower():
                clean_text = strip_tg_emojis(text)
                return await orig_edit_message_text(self, clean_text, *args, **kwargs)
            raise e
    CallbackQuery.edit_message_text = safe_edit_message_text

    orig_send_message = Bot.send_message
    async def safe_send_message(self, chat_id, text, *args, **kwargs):
        try:
            return await orig_send_message(self, chat_id, text, *args, **kwargs)
        except BadRequest as e:
            if "document_invalid" in str(e).lower():
                clean_text = strip_tg_emojis(text)
                return await orig_send_message(self, chat_id, clean_text, *args, **kwargs)
            raise e
    Bot.send_message = safe_send_message

    orig_edit_message_text_bot = Bot.edit_message_text
    async def safe_edit_message_text_bot(self, chat_id=None, message_id=None, inline_message_id=None, text=None, *args, **kwargs):
        try:
            return await orig_edit_message_text_bot(self, chat_id=chat_id, message_id=message_id, inline_message_id=inline_message_id, text=text, *args, **kwargs)
        except BadRequest as e:
            if "document_invalid" in str(e).lower():
                clean_text = strip_tg_emojis(text)
                return await orig_edit_message_text_bot(self, chat_id=chat_id, message_id=message_id, inline_message_id=inline_message_id, text=clean_text, *args, **kwargs)
            raise e
    Bot.edit_message_text = safe_edit_message_text_bot

patch_telegram_methods()


# =========================================================
# НАСТРОЙКИ ПРЕМИУМ ЭМОДЗИ
# =========================================================

def make_emoji(emoji_id: str, fallback: str) -> str:
    if emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'
    return fallback


EMOJI_GEM_ID    = "5377620962390857342"  # 💎 Кристалл / Валюта / Баланс
EMOJI_MONEY_ID  = "5445353829304387411"  # 💰 Деньги
EMOJI_FIRE_ID   = "5204025161744945363"  # 🔥 Победа / Салют
EMOJI_BOMB_ID   = "5469913852462242978"  # 💣 Мины
EMOJI_CHEST_ID  = "5373305540447385960"  # 📦 Клад / Сундук
EMOJI_STAR_ID   = "5373204900593439999"  # ⭐️ Звёзды / Донат
EMOJI_GUN_ID    = "5368322695530328905"  # 🔫 Дуэль
EMOJI_OK_ID     = "5314322825304120778"  # ✅ ОК
EMOJI_NO_ID     = "5314432686272587491"
EMOJI_TIME_ID   = "5255971360965930740"  # ⏳ TIME
EMOJI_BA_ID     = "5332455502917949981"  # 🏦 Банк
EMOJI_BAN_ID    = "5417924076503062111"
EMOJI_BANK_ID   = "5382164415019768638"  # 🏛 Казна
EMOJI_RANG_ID   = "5424746623462823358"
EMOJI_CHAT_ID   = "5461150493865483163"
EMOJI_LOW_ID    = "5429312151619859239"
EMOJI_PLAYER_ID = "5440648336149325993"
EMOJI_UP_ID     = "5334902521880141643"
EMOJI_NOUP_ID   = "5334898085178925407"
EMOJI_PAY_ID    = "5201873447554145566"
EMOJI_RULET_ID  = "5017339507666584402"
EMOJI_VIN_ID    = "5204025161744945363"
EMOJI_BOT_ID    = "5323772371830588991"
EMOJI_PUMPKIN_ID = "5852446300091453921"  # 🎃 Тыква: вставь сюда id премиум-эмодзи

EMOJI_GEM   = make_emoji(EMOJI_GEM_ID, "💎")
EMOJI_MONEY = make_emoji(EMOJI_MONEY_ID, "💰")
EMOJI_FIRE  = make_emoji(EMOJI_FIRE_ID, "🔥")
EMOJI_BOMB  = make_emoji(EMOJI_BOMB_ID, "💣")
EMOJI_CHEST = make_emoji(EMOJI_CHEST_ID, "📦")
EMOJI_STAR  = make_emoji(EMOJI_STAR_ID, "⭐️")
EMOJI_GUN   = make_emoji(EMOJI_GUN_ID, "🔫")
EMOJI_OK    = make_emoji(EMOJI_OK_ID, "✅")
EMOJI_NO    = make_emoji(EMOJI_NO_ID, "❌")
EMOJI_TIME  = make_emoji(EMOJI_TIME_ID, "⏳")
EMOJI_BA    = make_emoji(EMOJI_BA_ID, "🏦")
EMOJI_BAN   = make_emoji(EMOJI_BAN_ID, "🎟")
EMOJI_BANK  = make_emoji(EMOJI_BANK_ID, "🏛")
EMOJI_RANG  = make_emoji(EMOJI_RANG_ID, "🏅")
EMOJI_CHAT  = make_emoji(EMOJI_CHAT_ID, "💬")
EMOJI_LOW   = make_emoji(EMOJI_LOW_ID, "👇")
EMOJI_PLAYER= make_emoji(EMOJI_PLAYER_ID, "👤")
EMOJI_UP    = make_emoji(EMOJI_UP_ID, "📈")
EMOJI_NOUP  = make_emoji(EMOJI_NOUP_ID, "📉")
EMOJI_PAY   = make_emoji(EMOJI_PAY_ID, "💸")
EMOJI_RULET = make_emoji(EMOJI_RULET_ID, "🎡")
EMOJI_VIN   = make_emoji(EMOJI_VIN_ID, "🎉")
EMOJI_BOT   = make_emoji(EMOJI_BOT_ID, "🤖")
EMOJI_PUMPKIN = make_emoji(EMOJI_PUMPKIN_ID, "🎃")

# =========================================================
# НАСТРОЙКИ
# =========================================================

TOKEN = os.getenv("BOT_TOKEN", "").strip()

if not TOKEN:
    raise SystemExit(
        "BOT_TOKEN is empty: set it in the dashboard (Env tab) before starting the bot."
    )
PROVIDER_TOKEN = "" 

START_BALANCE = 2000
OWNER_ID = 5984555148  

BET_WAIT_SECONDS = 10
ROULETTE_TIMEOUT_SECONDS = 300
SPIN_SECONDS = 4
MAX_BETS_PER_GAME = 150

DUEL_MULTIPLIER = 2.0
TREASURY_COST = 100_000
INVITE_REWARD = 1_500
STARS_EXCHANGE_RATE = 3_000

BOT_START_TIME = time.time()

# =========================================================
# СПИСОК ЧАТОВ БОТА
# =========================================================
COMMUNITY_CHATS = [
    {"name": "Trade TON | GARANT ⛩", "url": "t.me/garantchatton"},
    {"name": "TON NEWS", "url": "https://t.me/toncasionews"},
    {"name": "𝑮𝒂𝒏𝑬𝒅𝒆𝒏 | Игровой", "url": "https://t.me/GanEden_Game"},
    {"name": "TON-Casino🎰", "url": "https://t.me/casiotongame"},
    {"name": "PiarChat | TON📌", "url": "https://t.me/piarchattonchik"},
]

BALANCES_FILE = "balances.json"
LOG_FILE = "roulette_log.json"
TREASURIES_FILE = "treasuries.json"
STATS_FILE = "stats.json"
GAME_STATS_FILE = "game_stats.json" 
BONUS_FILE = "bonus_times.json"
PROMOS_FILE = "promos.json"
PROMO_USES_FILE = "promo_uses.json"
HISTORY_FILE = "history.json"
BANK_FILE = "bank.json"
DISABLED_CHATS_FILE = "disabled_chats.json"
PENDING_BETS_FILE = "pending_bets.json"
CHAT_MEMBERS_FILE = "chat_members.json"
TOURNAMENT_FILE = "tournament.json"

TOURNAMENT_PRIZES = [100_000, 50_000, 25_000]  # призы за 1, 2, 3 места
TOURNAMENT_TOP_SIZE = 10

MSK_TZ = timezone(timedelta(hours=3))

# =========================================================
# РУЛЕТКА И БЛЭКДЖЕК КАРТЫ
# =========================================================

RED = {
    1, 3, 5, 7, 9,
    12, 14, 16, 18,
    19, 21, 23, 25, 27,
    30, 32, 34, 36
}

BLACK = set(range(1, 37)) - RED

BJ_CARDS = [
    ('2', 2), ('3', 3), ('4', 4), ('5', 5), ('6', 6), ('7', 7), ('8', 8), ('9', 9), ('10', 10),
    ('J', 10), ('Q', 10), ('K', 10), ('A', 11)
]
BJ_SUITS = ['♠️', '♥️', '♦️', '♣️']

# =========================================================
# БАШНЯ (TOWER) НАСТРОЙКИ
# =========================================================
TOWER_LEVELS = [
    {"mult": 1.40, "bombs": 1},
    {"mult": 2.00, "bombs": 1},
    {"mult": 2.80, "bombs": 1},
    {"mult": 4.00, "bombs": 1},
    {"mult": 5.80, "bombs": 1},
    {"mult": 8.50, "bombs": 1},
    {"mult": 12.5, "bombs": 1},
    {"mult": 19.0, "bombs": 1},
]

# =========================================================
# ФОРМАТИРОВАНИЕ ЧИСЕЛ
# =========================================================

def fmt(num) -> str:
    try:
        val = int(round(float(num)))
        return f"{val:,}".replace(",", " ")
    except (ValueError, TypeError):
        return str(num)

# =========================================================
# РАБОТА С ФАЙЛАМИ JSON
# =========================================================

def load_json(filename, default):
    if not os.path.exists(filename):
        return default
    try:
        with open(filename, "r", encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, type(default)):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return default


def save_json(filename, data):
    temp_file = filename + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temp_file, filename)


balances = load_json(BALANCES_FILE, {})

for k, v in list(balances.items()):
    try:
        balances[k] = int(round(float(v)))
    except Exception:
        balances[k] = START_BALANCE

roulette_log = load_json(LOG_FILE, {})
treasuries = load_json(TREASURIES_FILE, {})
user_stats = load_json(STATS_FILE, {})
game_stats = load_json(GAME_STATS_FILE, {}) 

bonus_times = load_json(BONUS_FILE, {})
promos = load_json(PROMOS_FILE, {})
promos.setdefault("test", {"reward": 15000, "limit": 20, "used": 0})
save_json(PROMOS_FILE, promos)

promo_uses = load_json(PROMO_USES_FILE, {})
promo_uses.setdefault("test", [])
save_json(PROMO_USES_FILE, promo_uses)

history_data = load_json(HISTORY_FILE, {})

bank_data = load_json(BANK_FILE, {"accounts": {}, "last_interest_date": ""})
bank_data.setdefault("accounts", {})
bank_data.setdefault("last_interest_date", "")

disabled_chats = load_json(DISABLED_CHATS_FILE, [])
pending_bets = load_json(PENDING_BETS_FILE, {})
chat_members_store = load_json(CHAT_MEMBERS_FILE, {})


def save_balances():
    save_json(BALANCES_FILE, balances)


def save_log():
    save_json(LOG_FILE, roulette_log)


def save_treasuries():
    save_json(TREASURIES_FILE, treasuries)


def save_stats():
    save_json(STATS_FILE, user_stats)

def save_game_stats():
    save_json(GAME_STATS_FILE, game_stats)


def save_bonus_times():
    save_json(BONUS_FILE, bonus_times)


def save_promos():
    save_json(PROMOS_FILE, promos)


def save_promo_uses():
    save_json(PROMO_USES_FILE, promo_uses)


def save_history():
    save_json(HISTORY_FILE, history_data)


def save_bank():
    save_json(BANK_FILE, bank_data)

def save_pending_bets():
    save_json(PENDING_BETS_FILE, pending_bets)

def save_chat_members():
    save_json(CHAT_MEMBERS_FILE, chat_members_store)


# =========================================================
# ТУРНИР ПО РУЛЕТКЕ (ежедневный, приз выплачивается в 23:59 МСК)
# =========================================================

tournament_data = load_json(TOURNAMENT_FILE, {})
tournament_data.setdefault("day", "")
tournament_data.setdefault("scores", {})


def save_tournament():
    save_json(TOURNAMENT_FILE, tournament_data)


def tournament_current_day(now_msk=None) -> str:
    """Дата, в которую будет выплата текущего турнира (после 23:59 — уже следующая)."""
    now_msk = now_msk or datetime.now(MSK_TZ)
    if now_msk.hour == 23 and now_msk.minute >= 59:
        return (now_msk.date() + timedelta(days=1)).isoformat()
    return now_msk.date().isoformat()


def tournament_add_win(user_id: str, raw_name: str, net_win: int):
    """Добавляет чистый выигрыш (выигрыш минус ставка) в турнир."""
    if net_win <= 0:
        return
    if not tournament_data.get("day"):
        tournament_data["day"] = tournament_current_day()
    uid = str(user_id)
    entry = tournament_data["scores"].setdefault(uid, {"name": raw_name, "score": 0})
    entry["name"] = raw_name
    entry["score"] = int(entry.get("score", 0)) + int(round(net_win))
    save_tournament()


def tournament_sorted():
    items = [
        (uid, d) for uid, d in tournament_data.get("scores", {}).items()
        if int(d.get("score", 0)) > 0
    ]
    items.sort(key=lambda it: int(it[1].get("score", 0)), reverse=True)
    return items


def render_tournament(viewer_id=None) -> str:
    top = tournament_sorted()
    medals = ["🥇", "🥈", "🥉"]

    lines = ["🏆 <b>ТУРНИР ПО РУЛЕТКЕ</b>", "<i>Лучшие выигрыши за сутки</i>", "———————————————"]

    if not top:
        lines.append("Пока никто ничего не выиграл. Стань первым!")
    else:
        for idx, (uid, d) in enumerate(top[:TOURNAMENT_TOP_SIZE], start=1):
            medal = medals[idx - 1] if idx <= 3 else f"<b>{idx}.</b>"
            name = get_user_link_quiet(uid, d.get("name") or f"Игрок {uid}")
            lines.append(f"{medal} {name} — <b>+{fmt(d['score'])}</b> TON")

        if viewer_id is not None:
            viewer_id = str(viewer_id)
            for pos, (uid, d) in enumerate(top, start=1):
                if uid == viewer_id and pos > TOURNAMENT_TOP_SIZE:
                    lines.append("...")
                    lines.append(f"<b>{pos}.</b> Вы — <b>+{fmt(d['score'])}</b> TON")
                    break

    lines.append("———————————————")
    lines.append("🎁 <b>Призы:</b>")
    for i, prize in enumerate(TOURNAMENT_PRIZES, start=1):
        lines.append(f"{medals[i - 1]} {i} место — <b>{fmt(prize)}</b> TON")

    now_msk = datetime.now(MSK_TZ)
    end = now_msk.replace(hour=23, minute=59, second=0, microsecond=0)
    if now_msk >= end:
        end += timedelta(days=1)
    left = int((end - now_msk).total_seconds())
    h, m = left // 3600, (left % 3600) // 60
    lines.append(f"\n{EMOJI_TIME} До подведения итогов: <b>{h} ч {m} мин</b>")
    lines.append("<i>Считается чистый выигрыш в рулетке: поставил 100, выиграл 120 — в турнир идёт 20.\n"
                 "Итоги — в 23:59 МСК.</i>")
    return "\n".join(lines)


async def show_tournament(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_msg = update.message if update.message else (
        update.callback_query.message if update.callback_query else None
    )
    if not target_msg:
        return
    viewer = update.effective_user.id if update.effective_user else None
    await target_msg.reply_text(render_tournament(viewer), parse_mode="HTML")


async def tournament_payout(bot: Bot):
    top = tournament_sorted()[:len(TOURNAMENT_PRIZES)]
    tournament_data["scores"] = {}
    save_tournament()

    for place, (uid, d) in enumerate(top, start=1):
        prize = TOURNAMENT_PRIZES[place - 1]
        balances[uid] = int(round(float(balances.get(uid, START_BALANCE)))) + prize
        add_history(uid, "Доход (Турнир)", prize, f"{place} место в турнире по рулетке")
    if top:
        save_balances()

    for place, (uid, d) in enumerate(top, start=1):
        prize = TOURNAMENT_PRIZES[place - 1]
        try:
            await bot.send_message(
                chat_id=int(uid),
                text=(
                    f"🏆 <b>Турнир по рулетке завершён!</b>\n\n"
                    f"Вы забрали <b>{place} место</b> и выиграли <b>{fmt(prize)}</b> TON {EMOJI_GEM}\n"
                    f"Ваш результат: +{fmt(d.get('score', 0))} TON\n\n"
                    f"Приз уже зачислен на баланс."
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            print(f"Не удалось отправить уведомление о турнире {uid}: {e}")

    print(f"[{datetime.now(MSK_TZ).isoformat()}] Турнир завершён, призёров: {len(top)}")


async def tournament_task(application: Application):
    """Каждые 20 сек проверяет время; в 23:59 МСК подводит итоги.
    Если бот был выключен в 23:59 — выплатит сразу после запуска."""
    while True:
        try:
            now_msk = datetime.now(MSK_TZ)
            today = now_msk.date().isoformat()
            day = tournament_data.get("day") or ""

            if not day:
                tournament_data["day"] = tournament_current_day(now_msk)
                save_tournament()
            else:
                due = day < today or (
                    day == today and (now_msk.hour, now_msk.minute) >= (23, 59)
                )
                if due:
                    await tournament_payout(application.bot)
                    tournament_data["day"] = tournament_current_day(datetime.now(MSK_TZ))
                    save_tournament()
            await asyncio.sleep(20)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Ошибка в задаче турнира: {e}")
            traceback.print_exc()
            await asyncio.sleep(30)


def get_bank_account(user_id):
    return bank_data["accounts"].setdefault(str(user_id), {
        "balance": 0,
        "lots": [],
        "last_withdrawal": 0
    })


def bank_total():
    return sum(int(a.get("balance", 0)) for a in bank_data["accounts"].values())


def add_history(user_id: str, action_type: str, amount: int, details: str = ""):
    user_id = str(user_id)
    if user_id not in history_data:
        history_data[user_id] = []
    history_data[user_id].append({
        "type": action_type,
        "amount": amount,
        "details": details,
        "timestamp": datetime.now(MSK_TZ).strftime("%d.%m.%Y %H:%M:%S")
    })
    history_data[user_id] = history_data[user_id][-100:]
    save_history()

# =========================================================
# СИСТЕМА УЧЕТА ИГРОВОЙ СТАТИСТИКИ
# =========================================================
def add_game_loss(user_id: str, amount: int):
    if amount <= 0:
        return
    user_id = str(user_id)
    if user_id not in game_stats:
        game_stats[user_id] = {"won": 0, "lost": 0}
    game_stats[user_id]["lost"] = int(game_stats[user_id].get("lost", 0)) + int(round(amount))
    save_game_stats()

def add_game_net_win(user_id: str, net_amount: int):
    if net_amount <= 0:
        return
    user_id = str(user_id)
    if user_id not in game_stats:
        game_stats[user_id] = {"won": 0, "lost": 0}
    game_stats[user_id]["won"] = int(game_stats[user_id].get("won", 0)) + int(round(net_amount))
    save_game_stats()

# =========================================================
# ПОЛЬЗОВАТЕЛИ И СТАТИСТИКА
# =========================================================

def get_user_display_name(user) -> str:
    name = (user.first_name or "").strip()
    if not name:
        name = f"Игрок {user.id}"
    name = name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<a href="tg://user?id={user.id}">{name}</a>'


def get_user_link_quiet(user_id: str, raw_name: str) -> str:
    """Ссылка на профиль по нику (https://t.me/ник) — выглядит как обычная ссылка,
    но НЕ пингует человека. Если ника нет — просто имя без ссылки."""
    safe_name = str(raw_name).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    uname = (user_stats.get(str(user_id), {}).get("username") or "").strip().lstrip("@")
    if uname and re.fullmatch(r"[A-Za-z0-9_]{4,32}", uname):
        return f'<a href="https://t.me/{uname}">{safe_name}</a>'
    return safe_name


def get_user_link(user_id: str, raw_name: str) -> str:
    safe_name = str(raw_name).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<a href="tg://user?id={user_id}">{safe_name}</a>'


def get_user(user):
    user_id = str(user.id)
    if user_id not in balances:
        balances[user_id] = START_BALANCE
        save_balances()

    disp_name = get_user_display_name(user)
    username_raw = (user.username or "").lower()

    if user_id not in user_stats:
        user_stats[user_id] = {
            "name": disp_name,
            "username": username_raw,
            "win": 0
        }
        save_stats()
    else:
        updated = False
        if user_stats[user_id].get("name") != disp_name:
            user_stats[user_id]["name"] = disp_name
            updated = True
        if user_stats[user_id].get("username") != username_raw:
            user_stats[user_id]["username"] = username_raw
            updated = True
        if updated:
            save_stats()

    return user_id


def record_game_win(user_id: str, win_amount: int):
    if win_amount <= 0:
        return
    if user_id not in user_stats:
        user_stats[user_id] = {"name": f"Игрок {user_id}", "username": "", "win": 0}
    user_stats[user_id]["win"] = int(user_stats[user_id].get("win", 0)) + int(round(win_amount))
    save_stats()

# =========================================================
# СОСТОЯНИЕ ИГР
# =========================================================

roulette_ready_time = {}
roulette_start_time = {}
roulette_running = {}
active_mines_games = {}
active_blackjack_games = {}  
round_saved_bets = {}
active_tower_games = {}

pending_duels = {}
open_duels = {}
active_duels = {}
duel_id_counter = 1

active_treasure_games = {}
waiting_for_custom_stars = {}
bank_waiting = {}  

def record_chat_member_activity(chat_id, user, win_amount=0):
    chat_id = str(chat_id)
    if chat_id not in chat_members_store:
        chat_members_store[chat_id] = {}
    uid = str(user.id)
    disp_name = get_user_display_name(user)
    if uid not in chat_members_store[chat_id]:
        chat_members_store[chat_id][uid] = {"name": disp_name, "win": 0}
    else:
        chat_members_store[chat_id][uid]["name"] = disp_name
    
    if win_amount > 0:
        chat_members_store[chat_id][uid]["win"] += int(round(win_amount))
    save_chat_members()

# =========================================================
# ФОНОВЫЙ СБРОС ТОПОВ И ТАЙМАУТЫ
# =========================================================

async def daily_reset_task():
    while True:
        try:
            now_msk = datetime.now(MSK_TZ)
            next_midnight = (now_msk + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            wait_seconds = (next_midnight - now_msk).total_seconds()
            await asyncio.sleep(max(1.0, wait_seconds))

            for uid in user_stats:
                user_stats[uid]["win"] = 0
            save_stats()

            chat_members_store.clear()
            save_chat_members()

            today = now_msk.date().isoformat()
            if bank_data.get("last_interest_date") != today:
                now_ts = time.time()
                for uid, acc in bank_data["accounts"].items():
                    if acc.get("last_withdrawal", 0) > 0 and now_ts - acc["last_withdrawal"] < 24 * 60 * 60:
                        continue
                    eligible = sum(
                        int(lot["amount"])
                        for lot in acc.get("lots", [])
                        if now_ts - float(lot["since"]) >= 4 * 3600
                    )
                    interest = eligible // 100
                    if interest > 0:
                        acc["balance"] = int(acc.get("balance", 0)) + interest
                        acc.setdefault("lots", []).append({"amount": interest, "since": now_ts})
                        balances[uid] = int(round(float(balances.get(uid, START_BALANCE)))) + interest
                        add_history(uid, "Доход (Банк)", interest, "Ежедневный процент 1%")
                bank_data["last_interest_date"] = today
                save_bank()
                save_balances()

            print(f"[{datetime.now(MSK_TZ).isoformat()}] Топ выигрышей пользователей и топы чатов сброшены, проценты банка начислены.")
            await asyncio.sleep(2)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Ошибка в сбросе топов/банка: {e}")
            await asyncio.sleep(60)


async def monitor_timeouts_loop(application: Application):
    while True:
        try:
            await asyncio.sleep(3)
            now = time.time()
            try:
                _mk_expire_all()
            except Exception as _e:
                print('[market] expire error:', _e)

            for chat_key in list(pending_bets.keys()):
                bets = pending_bets.get(chat_key, [])
                if not bets:
                    continue

                try:
                    chat_id_int = int(chat_key)
                except ValueError:
                    continue

                if roulette_running.get(chat_id_int, False):
                    continue

                first_bet_time = roulette_start_time.get(chat_id_int)
                if first_bet_time is None:
                    roulette_start_time[chat_id_int] = now
                    continue

                if now - first_bet_time >= ROULETTE_TIMEOUT_SECONDS:
                    user_refunds = {}
                    user_names = {}
                    for b in bets:
                        uid = str(b["user_id"])
                        amt = b["amount"]
                        user_refunds[uid] = user_refunds.get(uid, 0) + amt
                        user_names[uid] = b.get("raw_name") or f"Игрок {uid}"

                    for uid, refund_amount in user_refunds.items():
                        balances[uid] = int(round(balances.get(uid, START_BALANCE))) + refund_amount
                        add_history(uid, "Возврат (Рулетка)", refund_amount, "Автоотмена по таймауту (2 мин)")

                    save_balances()
                    pending_bets.pop(chat_key, None)
                    save_pending_bets()
                    roulette_ready_time.pop(chat_id_int, None)
                    roulette_start_time.pop(chat_id_int, None)

                    refund_lines = []
                    for uid, refund_amount in user_refunds.items():
                        u_tag = get_user_link(uid, user_names[uid])
                        refund_lines.append(f"• {u_tag}: <b>+{fmt(refund_amount)} TON {EMOJI_GEM}</b>")

                    refund_text = "\n".join(refund_lines)
                    try:
                        await application.bot.send_message(
                            chat_id=chat_id_int,
                            text=(
                                f"{EMOJI_TIME} <b>ВРЕМЯ ОЖИДАНИЯ ВЫШЛО!</b>\n\n"
                                f"Никто не запустил рулетку командой «гоу».\n"
                                f"Все сделанные ставки были автоматически отменены, а средства полностью возвращены:\n\n"
                                f"{refund_text}"
                            ),
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        print(f"Ошибка отправки уведомления об автоотмене рулетки: {e}")

            for uid, game in list(active_mines_games.items()):
                if now - game.get("last_action", 0) > 60:
                    active_mines_games.pop(uid, None)  # сначала снимаем игру — выплата не повторится
                    chat_id = game["chat_id"]
                    bet = game["bet"]
                    opened_count = len(game["opened"])
                    user_mention = get_user_link(uid, game.get("raw_name", "Игрок"))

                    if opened_count == 0:
                        balances[uid] = int(round(balances.get(uid, START_BALANCE))) + bet
                        save_balances()
                        add_history(uid, "Возврат (Мины)", bet, "Отмена по неактивности")
                        try:
                            await application.bot.send_message(
                                chat_id=chat_id,
                                text=f"{EMOJI_TIME} {user_mention}, время ожидания хода в Минах вышло (1 мин). Игра отменена, ставка <b>{fmt(bet)} TON</b> полностью возвращена.",
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass
                    else:
                        mult = get_mines_multiplier(opened_count, game.get("mines_count", 3))
                        win_amount = int(round(bet * mult))
                        balances[uid] = int(round(balances.get(uid, START_BALANCE))) + win_amount
                        save_balances()
                        record_game_win(uid, win_amount)
                        
                        net_win = win_amount - bet
                        if net_win > 0:
                            add_game_net_win(uid, net_win)
                            if game.get("chat_type") in ("group", "supergroup"):
                                record_chat_member_activity(chat_id, game.get("user_obj"), net_win)
                        elif net_win < 0:
                            add_game_loss(uid, abs(net_win))

                        add_history(uid, "Доход (Мины)", win_amount, "Автовывод по таймауту")
                        try:
                            await application.bot.send_message(
                                chat_id=chat_id,
                                text=f"{EMOJI_TIME} {user_mention}, время ожидания хода в Минах вышло (1 мин). Зафиксирован автоматический вывод: <b>+{fmt(win_amount)} TON {EMOJI_GEM}</b> (x{mult})",
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass

                    active_mines_games.pop(uid, None)

            # Таймаут для игры Башня (1 минута)
            for uid, game in list(active_tower_games.items()):
                if now - game.get("last_action", 0) > 60:
                    chat_id = game["chat_id"]
                    bet = game["bet"]
                    current_level = game.get("level", 0)
                    user_mention = get_user_link(uid, game.get("raw_name", "Игрок"))

                    if current_level == 0:
                        balances[uid] = int(round(balances.get(uid, START_BALANCE))) + bet
                        save_balances()
                        add_history(uid, "Возврат (Башня)", bet, "Отмена по неактивности")
                        try:
                            await application.bot.send_message(
                                chat_id=chat_id,
                                text=f"{EMOJI_TIME} {user_mention}, время ожидания хода в Башне вышло (1 мин). Игра отменена, ставка <b>{fmt(bet)} TON</b> возвращена.",
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass
                    else:
                        mult = TOWER_LEVELS[current_level - 1]["mult"]
                        win_amount = int(round(bet * mult))
                        balances[uid] = int(round(balances.get(uid, START_BALANCE))) + win_amount
                        save_balances()
                        record_game_win(uid, win_amount)

                        net_win = win_amount - bet
                        if net_win > 0:
                            add_game_net_win(uid, net_win)
                            if game.get("chat_type") in ("group", "supergroup"):
                                record_chat_member_activity(chat_id, game.get("user_obj"), net_win)
                        elif net_win < 0:
                            add_game_loss(uid, abs(net_win))

                        add_history(uid, "Доход (Башня)", win_amount, "Автовывод по таймауту")
                        try:
                            await application.bot.send_message(
                                chat_id=chat_id,
                                text=f"{EMOJI_TIME} {user_mention}, время ожидания хода в Башне вышло (1 мин). Зафиксирован автоматический вывод: <b>+{fmt(win_amount)} TON {EMOJI_GEM}</b> (x{mult})",
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass

                    active_tower_games.pop(uid, None)

            for duel_id, duel in list(pending_duels.items()):
                if now - duel["created_at"] > 60:
                    chat_id = duel["chat_id"]
                    pending_duels.pop(duel_id, None)
                    try:
                        await application.bot.send_message(
                            chat_id=chat_id,
                            text=f"{EMOJI_TIME} Время ожидания ответа на дуэль между {duel['challenger_name']} и {duel['opponent_name']} вышло. Предложение отменено.",
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass

            for duel_id, duel in list(open_duels.items()):
                if now - duel["created_at"] > 60:
                    chat_id = duel["chat_id"]
                    msg_id = duel.get("message_id")
                    open_duels.pop(duel_id, None)
                    if msg_id:
                        try:
                            await application.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                        except Exception:
                            try:
                                await application.bot.edit_message_text(
                                    chat_id=chat_id,
                                    message_id=msg_id,
                                    text=f"{EMOJI_TIME} Предложение дуэли от {duel['challenger_name']} на {fmt(duel['amount'])} TON отменено по таймауту.",
                                    parse_mode="HTML"
                                )
                            except Exception:
                                pass

        except Exception as e:
            print(f"Ошибка в мониторе таймаутов: {e}")

# =========================================================
# ЛОГИКА МИН (СБАЛАНСИРОВАННАЯ ФОРМУЛА, ОТ 3 ДО 24 МИН)
# =========================================================

def get_mines_multiplier(opened_count, mines_count=3, total_cells=25):
    if opened_count <= 0:
        return 1.0

    safe_cells = total_cells - mines_count
    if safe_cells <= 0:
        return 1.0

    mult = 1.0
    for i in range(opened_count):
        mult *= (total_cells - i) / (safe_cells - i)

    result = round(mult * 0.94, 2)
    return max(1.05, min(result, 25.0))


def build_mines_keyboard(game_data, game_over=False, won=False):
    opened = game_data["opened"]
    mines = game_data["mines"]
    keyboard = []

    for row in range(5):
        row_buttons = []
        for col in range(5):
            idx = row * 5 + col
            if idx in opened:
                text = "💎"
            elif game_over and idx in mines:
                text = "💣"
            else:
                text = " "

            cb_data = f"mine_click_{idx}" if not game_over else "mine_ignore"
            row_buttons.append(InlineKeyboardButton(text, callback_data=cb_data))
        keyboard.append(row_buttons)

    if not game_over:
        opened_count = len(opened)
        mult = get_mines_multiplier(opened_count, game_data.get("mines_count", 3))
        win_amount = int(round(game_data["bet"] * mult))

        if opened_count == 0:
            keyboard.append([
                InlineKeyboardButton("❌ Отменить игру", callback_data="mine_cancel")
            ])
        else:
            cashout_text = f"💰 Забрать {fmt(win_amount)} TON (x{mult})"
            keyboard.append([InlineKeyboardButton(cashout_text, callback_data="mine_cashout")])

    return InlineKeyboardMarkup(keyboard)

# =========================================================
# ЛОГИКА ИГРЫ БАШНЯ (🏰)
# =========================================================

def build_tower_keyboard(game_data, game_over=False, exploded_cell=None):
    current_lvl = game_data["level"]
    history = game_data["history"]
    keyboard = []

    total_levels = len(TOWER_LEVELS)
    for lvl in range(total_levels - 1, -1, -1):
        mult = TOWER_LEVELS[lvl]["mult"]
        row_buttons = []

        is_passed = lvl < current_lvl
        is_current = lvl == current_lvl and not game_over
        is_exploded_lvl = game_over and (lvl == current_lvl) and (exploded_cell is not None)

        for col in range(3):
            if is_passed:
                chosen_col = history.get(lvl)
                text = "💎" if col == chosen_col else "▪️"
                cb = "tower_ignore"
            elif is_exploded_lvl:
                if col == exploded_cell:
                    text = "💣"
                else:
                    text = "▫️"
                cb = "tower_ignore"
            elif is_current:
                text = "❓"
                cb = f"tower_step_{lvl}_{col}"
            else:
                text = "▫️"
                cb = "tower_ignore"

            row_buttons.append(InlineKeyboardButton(text, callback_data=cb))

        prefix = "👉 " if is_current else ""
        row_buttons.append(InlineKeyboardButton(f"{prefix}x{mult}", callback_data="tower_ignore"))
        keyboard.append(row_buttons)

    if not game_over:
        control_row = []
        if current_lvl == 0:
            control_row.append(InlineKeyboardButton("❌ Отменить", callback_data="tower_cancel"))
        else:
            curr_mult = TOWER_LEVELS[current_lvl - 1]["mult"]
            curr_win = int(round(game_data["bet"] * curr_mult))
            control_row.append(InlineKeyboardButton(f"💰 Забрать {fmt(curr_win)} TON (x{curr_mult})", callback_data="tower_cashout"))
        keyboard.append(control_row)

    return InlineKeyboardMarkup(keyboard)


async def handle_tower_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = get_user(update.effective_user)
    parts = update.message.text.split()

    if len(parts) < 2:
        await update.message.reply_text(
            "🏰 <b>ИГРА В БАШНЮ</b>\n\n"
            "Укажи ставку для игры:\n"
            "Пример: <code>башня 500</code>\n\n"
            "<b>Правила:</b>\n"
            "• В Башне 8 этажей, на каждом этаже 3 ячейки.\n"
            "• В 1 из 3 ячеек спрятана бомба 💣, а в 2 — кристалл 💎.\n"
            "• С каждым этажом коэффициент растёт (до x19.0)!\n"
            "• Можно забрать выигрыш на любом пройденном этаже.",
            parse_mode="HTML"
        )
        return

    try:
        bet = int(parts[1].replace(" ", ""))
    except ValueError:
        await update.message.reply_text("❌ Ставка должна быть целым числом.")
        return

    if bet <= 0:
        await update.message.reply_text("❌ Ставка должна быть больше 0.")
        return

    if user_id in active_tower_games:
        await update.message.reply_text("⚠️ У вас уже есть активная игра в Башню! Завершите её.")
        return

    current_bal = int(round(balances.get(user_id, 0)))
    if current_bal < bet:
        await update.message.reply_text(
            f"{EMOJI_NO} Недостаточно TON для игры!\nТвой баланс: <b>{fmt(current_bal)} TON {EMOJI_GEM}</b>",
            parse_mode="HTML"
        )
        return

    balances[user_id] -= bet
    save_balances()
    add_history(user_id, "Расход (Башня)", bet, "Инициация игры")

    bombs_map = {lvl: random.randint(0, 2) for lvl in range(len(TOWER_LEVELS))}

    game_data = {
        "bet": bet,
        "level": 0,
        "bombs": bombs_map,
        "history": {},
        "chat_id": update.effective_chat.id,
        "user_id": user_id,
        "raw_name": update.effective_user.first_name or f"Игрок {user_id}",
        "last_action": time.time(),
        "chat_type": update.effective_chat.type,
        "user_obj": update.effective_user
    }

    active_tower_games[user_id] = game_data
    reply_markup = build_tower_keyboard(game_data)

    await update.message.reply_text(
        f"🏰 <b>ИГРА В БАШНЮ</b>\n\n"
        f"{EMOJI_MONEY} Ставка: <b>{fmt(bet)} TON {EMOJI_GEM}</b>\n"
        f"🪜 Этаж: <b>1/{len(TOWER_LEVELS)}</b>\n"
        f"📈 Множитель этажа: <b>x{TOWER_LEVELS[0]['mult']}</b>\n\n"
        f"👇 Выбери одну из 3 ячеек на первом этаже:",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


async def tower_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    data = query.data
    user_id = str(query.from_user.id)

    if data == "tower_ignore":
        await query.answer()
        return

    if user_id not in active_tower_games:
        await query.answer("⚠️ Это не ваша игра или она уже завершена!", show_alert=True)
        return

    game_data = active_tower_games[user_id]
    game_data["last_action"] = time.time()

    if data == "tower_cancel":
        if game_data["level"] > 0:
            await query.answer("Нельзя отменить начатую игру!", show_alert=True)
            return

        bet = game_data["bet"]
        balances[user_id] = int(round(balances[user_id])) + bet
        save_balances()
        add_history(user_id, "Возврат (Башня)", bet, "Отмена игры игроком")

        active_tower_games.pop(user_id, None)

        await query.edit_message_text(
            f"{EMOJI_NO} Игра в Башню отменена.\n"
            f"{EMOJI_MONEY} На баланс возвращено: <b>{fmt(bet)} TON</b>\n"
            f"{EMOJI_MONEY} Баланс: <b>{fmt(balances[user_id])} TON {EMOJI_GEM}</b>",
            parse_mode="HTML"
        )
        await query.answer("Игра отменена, ставка возвращена!")
        return

    if data == "tower_cashout":
        current_lvl = game_data["level"]
        if current_lvl == 0:
            await query.answer("Сделайте ход на первом этаже!", show_alert=True)
            return

        mult = TOWER_LEVELS[current_lvl - 1]["mult"]
        win_amount = int(round(game_data["bet"] * mult))

        balances[user_id] = int(round(balances[user_id])) + win_amount
        save_balances()

        record_game_win(user_id, win_amount)
        net_win = win_amount - game_data["bet"]
        add_game_net_win(user_id, net_win)

        chat_id = query.message.chat.id if query.message and query.message.chat else None
        if chat_id and query.message.chat.type in ("group", "supergroup"):
            record_chat_member_activity(chat_id, query.from_user, net_win)

        add_history(user_id, "Доход (Башня)", win_amount, f"Забрал куш на x{mult}")

        reply_markup = build_tower_keyboard(game_data, game_over=True)

        await query.edit_message_text(
            f"🎉 <b>ПОБЕДА В БАШНЕ!</b>\n\n"
            f"🪜 Пройдено этажей: <b>{current_lvl}/{len(TOWER_LEVELS)}</b>\n"
            f"🏆 Множитель: <b>x{mult}</b>\n"
            f"💰 Выигрыш: <b>+{fmt(win_amount)} TON {EMOJI_GEM}</b>\n"
            f"{EMOJI_MONEY} Твой баланс: <b>{fmt(balances[user_id])} TON {EMOJI_GEM}</b>",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

        active_tower_games.pop(user_id, None)
        await query.answer("Выигрыш успешно зачислен!")
        return

    if data.startswith("tower_step_"):
        parts = data.split("_")
        step_lvl = int(parts[2])
        col = int(parts[3])

        current_lvl = game_data["level"]
        if step_lvl != current_lvl:
            await query.answer("Сделайте ход на текущем этаже!", show_alert=True)
            return

        bomb_col = game_data["bombs"][current_lvl]

        if col == bomb_col:
            reply_markup = build_tower_keyboard(game_data, game_over=True, exploded_cell=col)
            add_game_loss(user_id, game_data["bet"])

            await query.edit_message_text(
                f"💥 <b>БАХ! ВЫ ПОДОРВАЛИСЬ НА БОМБЕ!</b>\n\n"
                f"🪜 Башня разрушилась на {current_lvl + 1} этаже.\n"
                f"💸 Потеряно: <b>{fmt(game_data['bet'])} TON</b>\n"
                f"{EMOJI_MONEY} Твой баланс: <b>{fmt(balances[user_id])} TON {EMOJI_GEM}</b>",
                reply_markup=reply_markup,
                parse_mode="HTML"
            )

            active_tower_games.pop(user_id, None)
            await query.answer("Бум! Бомба 💥")
            return

        game_data["history"][current_lvl] = col
        game_data["level"] += 1
        new_lvl = game_data["level"]

        if new_lvl >= len(TOWER_LEVELS):
            final_mult = TOWER_LEVELS[-1]["mult"]
            win_amount = int(round(game_data["bet"] * final_mult))

            balances[user_id] = int(round(balances[user_id])) + win_amount
            save_balances()

            record_game_win(user_id, win_amount)
            net_win = win_amount - game_data["bet"]
            add_game_net_win(user_id, net_win)

            chat_id = query.message.chat.id if query.message and query.message.chat else None
            if chat_id and query.message.chat.type in ("group", "supergroup"):
                record_chat_member_activity(chat_id, query.from_user, net_win)

            add_history(user_id, "Доход (Башня)", win_amount, "Полное покорение Башни!")

            reply_markup = build_tower_keyboard(game_over=True, game_data=game_data)

            await query.edit_message_text(
                f"👑 <b>ПОЛНОЕ ПОКОРЕНИЕ БАШНИ!</b> 🎉\n\n"
                f"Ты успешно дошёл до вершины (8/8)!\n"
                f"🏆 Максимальный множитель: <b>x{final_mult}</b>\n"
                f"🎉 Выигрыш: <b>+{fmt(win_amount)} TON {EMOJI_GEM}</b>\n"
                f"{EMOJI_MONEY} Твой баланс: <b>{fmt(balances[user_id])} TON {EMOJI_GEM}</b>",
                reply_markup=reply_markup,
                parse_mode="HTML"
            )

            active_tower_games.pop(user_id, None)
            await query.answer("Вершина покорена! 👑")
            return

        curr_mult = TOWER_LEVELS[new_lvl - 1]["mult"]
        curr_win = int(round(game_data["bet"] * curr_mult))
        next_mult = TOWER_LEVELS[new_lvl]["mult"]

        reply_markup = build_tower_keyboard(game_data)

        await query.edit_message_text(
            f"🏰 <b>ИГРА В БАШНЮ</b>\n\n"
            f"{EMOJI_MONEY} Ставка: <b>{fmt(game_data['bet'])} TON {EMOJI_GEM}</b>\n"
            f"🪜 Этаж: <b>{new_lvl + 1}/{len(TOWER_LEVELS)}</b> (следующий x{next_mult})\n"
            f"{EMOJI_UP} Доступный выигрыш: <b>{fmt(curr_win)} TON {EMOJI_GEM}</b> (x{curr_mult})\n\n"
            f"Выбери ячейку на следующем этаже или забери выигрыш:",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        await query.answer("Успешно! Кристалл 💎")

# =========================================================
# ЛОГИКА ИГРЫ КУБЫ (🎲)
# =========================================================

async def handle_dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = get_user(update.effective_user)
    parts = update.message.text.split()

    if len(parts) < 3:
        await update.message.reply_text(
            "🎲 <b>ИГРА В КУБЫ</b>\n\n"
            "Формат команды: <code>кубы [ставка] [выбор]</code>\n\n"
            "<b>Варианты ставок и коэффициенты:</b>\n"
            "• <b>Число (1-6)</b>: коэффициент <b>x4.0</b>\n"
            "  Пример: <code>кубы 100 5</code>\n"
            "• <b>Чет / Нечет</b>: коэффициент <b>x1.5</b>\n"
            "  Пример: <code>кубы 500 чет</code>\n"
            "• <b>Больше (4-6) / Меньше (1-3)</b>: коэффициент <b>x1.5</b>\n"
            "  Пример: <code>кубы 300 больше</code>",
            parse_mode="HTML"
        )
        return

    try:
        bet = int(parts[1].replace(" ", ""))
    except ValueError:
        await update.message.reply_text("❌ Ставка должна быть целым числом.")
        return

    if bet <= 0:
        await update.message.reply_text("❌ Ставка должна быть больше 0.")
        return

    choice = parts[2].lower()
    valid_choices = {"1", "2", "3", "4", "5", "6", "чет", "чёт", "нечет", "больше", "меньше"}

    if choice not in valid_choices:
        await update.message.reply_text("❌ Неверный выбор! Используй число 1-6, 'чет', 'нечет', 'больше' или 'меньше'.", parse_mode="HTML")
        return

    current_bal = int(round(balances.get(user_id, 0)))
    if current_bal < bet:
        await update.message.reply_text(
            f"{EMOJI_NO} Недостаточно TON!\nБаланс: <b>{fmt(current_bal)} TON {EMOJI_GEM}</b>",
            parse_mode="HTML"
        )
        return

    balances[user_id] -= bet
    save_balances()
    add_history(user_id, "Расход (Кубы)", bet, f"Ставка на {choice}")

    msg = await update.message.reply_dice(emoji="🎲")
    await asyncio.sleep(3.5)

    value = msg.dice.value if msg and msg.dice else random.randint(1, 6)

    won = False
    multiplier = 0.0

    if choice.isdigit():
        if int(choice) == value:
            won = True
            multiplier = 4.0
    elif choice in {"чет", "чёт"}:
        if value % 2 == 0:
            won = True
            multiplier = 1.5
    elif choice == "нечет":
        if value % 2 != 0:
            won = True
            multiplier = 1.5
    elif choice == "больше":
        if value >= 4:
            won = True
            multiplier = 1.5
    elif choice == "меньше":
        if value <= 3:
            won = True
            multiplier = 1.5

    user_name = get_user_display_name(update.effective_user)
    chat_id = update.effective_chat.id

    if won:
        win_amount = int(round(bet * multiplier))
        balances[user_id] += win_amount
        save_balances()
        record_game_win(user_id, win_amount)
        net_win = win_amount - bet
        add_game_net_win(user_id, net_win)
        
        if update.effective_chat.type in ("group", "supergroup"):
            record_chat_member_activity(chat_id, update.effective_user, net_win)
        add_history(user_id, "Доход (Кубы)", win_amount, f"Победа x{multiplier}")

        result_text = (
            f"🎲 <b>КУБЫ — ПОБЕДА! 🎉</b>\n\n"
            f"{EMOJI_PLAYER} Игрок: {user_name}\n"
            f"🎯 Выпало число: <b>{value}</b>\n"
            f"💰 Твоя ставка: <b>{fmt(bet)} TON</b> на <b>{choice}</b>\n\n"
            f"🏆 Множитель: <b>x{multiplier}</b>\n"
            f"🎉 Выигрыш: <b>+{fmt(win_amount)} TON {EMOJI_GEM}</b>\n"
            f"{EMOJI_MONEY} Новый баланс: <b>{fmt(balances[user_id])} TON {EMOJI_GEM}</b>"
        )
    else:
        record_game_win(user_id, 0)
        add_game_loss(user_id, bet)
        result_text = (
            f"🎲 <b>КУБЫ — ПРОИГРЫШ</b>\n\n"
            f"{EMOJI_PLAYER} Игрок: {user_name}\n"
            f"🎯 Выпало число: <b>{value}</b>\n"
            f"💰 Твоя ставка: <b>{fmt(bet)} TON</b> на <b>{choice}</b>\n\n"
            f"❌ Ставка не сыграла.\n"
            f"💸 Потеряно: <b>{fmt(bet)} TON</b>\n"
            f"{EMOJI_MONEY} Баланс: <b>{fmt(balances[user_id])} TON {EMOJI_GEM}</b>"
        )

    await update.message.reply_text(result_text, parse_mode="HTML")

# =========================================================
# ЛОГИКА СЛОТОВ (🎰)
# =========================================================

async def handle_slot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = get_user(update.effective_user)
    parts = update.message.text.split()

    if len(parts) < 2:
        await update.message.reply_text(
            "🎰 <b>ИГРА В СЛОТЫ</b>\n\n"
            "Укажи ставку для игры в слоты:\n"
            "Пример: <code>слот 500</code> или <code>слоты 1000</code>",
            parse_mode="HTML"
        )
        return

    try:
        bet = int(parts[1].replace(" ", ""))
    except ValueError:
        await update.message.reply_text("❌ Ставка должна быть целым числом.")
        return

    if bet <= 0:
        await update.message.reply_text("❌ Ставка должна быть больше 0.")
        return

    current_bal = int(round(balances.get(user_id, 0)))
    if current_bal < bet:
        await update.message.reply_text(
            f"{EMOJI_NO} Недостаточно TON для игры!\nТвой баланс: <b>{fmt(current_bal)} TON {EMOJI_GEM}</b>",
            parse_mode="HTML"
        )
        return

    balances[user_id] -= bet
    save_balances()
    add_history(user_id, "Расход (Слоты)", bet, "Инициация игры")

    msg = await update.message.reply_dice(emoji="🎰")
    await asyncio.sleep(3.5)

    value = msg.dice.value if msg and msg.dice else 1

    multiplier = 0.0
    win_type = "lose"

    if value == 64:
        multiplier = 10.0
        win_type = "jackpot"
    elif value in {1, 22, 43}:
        multiplier = 3.0
        win_type = "win"
    elif value in {16, 32, 48}:
        multiplier = 1.5
        win_type = "small_win"

    user_name = get_user_display_name(update.effective_user)
    chat_id = update.effective_chat.id

    if multiplier > 0:
        win_amount = int(round(bet * multiplier))
        balances[user_id] += win_amount
        save_balances()
        record_game_win(user_id, win_amount)
        net_win = win_amount - bet
        add_game_net_win(user_id, net_win)
        
        if update.effective_chat.type in ("group", "supergroup"):
            record_chat_member_activity(chat_id, update.effective_user, net_win)
        add_history(user_id, "Доход (Слоты)", win_amount, f"Выигрыш x{multiplier}")

        if win_type == "jackpot":
            result_text = (
                f"🎰 <b>СЛОТЫ — ДЖЕКПОТ! 🎉</b>\n\n"
                f"👤 Игрок: {user_name}\n"
                f"{EMOJI_MONEY} Ставка: <b>{fmt(bet)} TON {EMOJI_GEM}</b>\n\n"
                f"💎 <b>ТРИ СЕМЁРКИ (7 7 7)! МЕГА-КУШ!</b>\n"
                f"🏆 Множитель: <b>x10</b>\n"
                f"🎉 Выигрыш: <b>+{fmt(win_amount)} TON {EMOJI_GEM}</b>\n"
                f"{EMOJI_MONEY} Новый баланс: <b>{fmt(balances[user_id])} TON {EMOJI_GEM}</b>"
            )
        else:
            result_text = (
                f"🎰 <b>СЛОТЫ — ПОБЕДА!</b>\n\n"
                f"👤 Игрок: {user_name}\n"
                f"{EMOJI_MONEY} Ставка: <b>{fmt(bet)} TON {EMOJI_GEM}</b>\n\n"
                f"🏆 Множитель: <b>x{multiplier}</b>\n"
                f"🎉 Выигрыш: <b>+{fmt(win_amount)} TON {EMOJI_GEM}</b>\n"
                f"{EMOJI_MONEY} Новый баланс: <b>{fmt(balances[user_id])} TON {EMOJI_GEM}</b>"
            )
    else:
        record_game_win(user_id, 0)
        add_game_loss(user_id, bet)
        result_text = (
            f"🎰 <b>СЛОТЫ — ПРОИГРЫШ</b>\n\n"
            f"👤 Игрок: {user_name}\n"
            f"{EMOJI_MONEY} Ставка: <b>{fmt(bet)} TON {EMOJI_GEM}</b>\n\n"
            f"❌ Комбинация не сыграла.\n"
            f"💸 Потеряно: <b>{fmt(bet)} TON</b>\n"
            f"{EMOJI_MONEY} Баланс: <b>{fmt(balances[user_id])} TON {EMOJI_GEM}</b>"
        )

    await update.message.reply_text(result_text, parse_mode="HTML")

# =========================================================
# ЛОГИКА БЛЭКДЖЕКА (21)
# =========================================================

def draw_card():
    card, value = random.choice(BJ_CARDS)
    suit = random.choice(BJ_SUITS)
    return {"name": f"{card}{suit}", "value": value, "rank": card}


def calculate_score(hand):
    score = sum(card["value"] for card in hand)
    aces = sum(1 for card in hand if card["rank"] == 'A')
    while score > 21 and aces > 0:
        score -= 10
        aces -= 1
    return score


def format_hand(hand):
    return ", ".join(card["name"] for card in hand)


async def handle_blackjack_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = get_user(update.effective_user)
    parts = update.message.text.split()

    if len(parts) < 2:
        await update.message.reply_text(
            "🃏 <b>Блэкджек (21)</b>\n\n"
            "Укажи ставку для игры в Блэкджек:\n"
            "Пример: <code>бд 500</code> или <code>блекджек 1000</code>",
            parse_mode="HTML"
        )
        return

    try:
        bet = int(parts[1].replace(" ", ""))
    except ValueError:
        await update.message.reply_text("❌ Ставка должна быть целым числом.")
        return

    if bet <= 0:
        await update.message.reply_text("❌ Ставка должна быть больше 0.")
        return

    current_bal = int(round(balances.get(user_id, 0)))
    if current_bal < bet:
        await update.message.reply_text(
            f"{EMOJI_NO} Недостаточно TON для игры!\nТвой баланс: <b>{fmt(current_bal)} TON {EMOJI_GEM}</b>",
            parse_mode="HTML"
        )
        return

    if user_id in active_blackjack_games:
        await update.message.reply_text("⚠️ У тебя уже запущена игра в Блэкджек! Заверши её сначала.")
        return

    balances[user_id] -= bet
    save_balances()
    add_history(user_id, "Расход (Блэкджек)", bet, "Инициация игры")

    player_will_win = (random.random() < 0.46)

    player_hand = [draw_card(), draw_card()]
    dealer_hand = [draw_card(), draw_card()]

    player_score = calculate_score(player_hand)
    
    game_data = {
        "bet": bet,
        "player_hand": player_hand,
        "dealer_hand": dealer_hand,
        "chat_id": update.effective_chat.id,
        "user_id": user_id,
        "username": get_user_display_name(update.effective_user),
        "processing": False,
        "pre_win": player_will_win
    }

    if player_score == 21:
        dealer_full_score = calculate_score(dealer_hand)
        if dealer_full_score == 21 or not player_will_win:
            win_amount = bet
            balances[user_id] += win_amount
            save_balances()
            add_history(user_id, "Возврат (Блэкджек)", win_amount, "Ничья (у обоих блэкджек)")
            await update.message.reply_text(
                f"🃏 <b>Блэкджек (21)</b>\n\n"
                f"Твои карты: {format_hand(player_hand)} (<b>21</b>)\n"
                f"Карты дилера: {format_hand(dealer_hand)} (<b>21</b>)\n\n"
                f"🤝 <b>Ничья!</b> У обоих Блэкджек! Ставка возвращена: <b>{fmt(bet)} TON</b>",
                parse_mode="HTML"
            )
            return
        else:
            win_amount = int(round(bet * 2.5))
            balances[user_id] += win_amount
            save_balances()
            record_game_win(user_id, win_amount)
            net_win = win_amount - bet
            add_game_net_win(user_id, net_win)
            
            if update.effective_chat.type in ("group", "supergroup"):
                record_chat_member_activity(update.effective_chat.id, update.effective_user, net_win)
            add_history(user_id, "Доход (Блэкджек)", win_amount, "Натуральный Блэкджек")
            await update.message.reply_text(
                f"🃏 <b>Блэкджек (21)</b>\n\n"
                f"Твои карты: {format_hand(player_hand)} (<b>21</b>)\n"
                f"Карты дилера: {dealer_hand[0]['name']} + 🎴\n\n"
                f"🎉 {EMOJI_FIRE} <b>НАТУРАЛЬНЫЙ БЛЭКДЖЕК!</b> Ты сорвал куш!\n"
                f"💰 Выигрыш (x2.5): <b>+{fmt(win_amount)} TON {EMOJI_GEM}</b>",
                parse_mode="HTML"
            )
            return

    active_blackjack_games[user_id] = game_data

    keyboard = [
        [
            InlineKeyboardButton("🃏 Взять еще", callback_data=f"bj_hit_{user_id}"),
            InlineKeyboardButton("🛑 Хватит", callback_data=f"bj_stand_{user_id}")
        ]
    ]

    await update.message.reply_text(
        f"🃏 <b>БЛЭКДЖЕК (21)</b>\n\n"
        f"👤 Игрок: {game_data['username']}\n"
        f"{EMOJI_MONEY} Ставка: <b>{fmt(bet)} TON {EMOJI_GEM}</b>\n\n"
        f"🫵 <b>Твоя рука:</b>\n"
        f"» {format_hand(player_hand)}\n"
        f"» Очки: <b>{player_score}</b>\n\n"
        f"🤖 <b>Рука дилера:</b>\n"
        f"» {dealer_hand[0]['name']} + 🎴\n"
        f"» Очки: <b>{dealer_hand[0]['value']}</b>\n\n"
        f"<i>Выбери действие: Взять еще одну карту или остановиться?</i>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )


async def blackjack_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    data = query.data
    user_id = str(query.from_user.id)
    parts = data.split("_")
    action = parts[1]  
    target_user_id = parts[2]

    if user_id != target_user_id:
        await query.answer("Это не твоя игра в Блэкджек!", show_alert=True)
        return

    game = active_blackjack_games.get(user_id)
    if not game:
        await query.answer("Игра не найдена или уже завершена.", show_alert=True)
        return

    if game.get("processing", False):
        await query.answer("Ход обрабатывается, подожди...", show_alert=True)
        return
    game["processing"] = True

    try:
        player_hand = game["player_hand"]
        dealer_hand = game["dealer_hand"]
        bet = game["bet"]
        username = game["username"]
        pre_win = game.get("pre_win", False)

        if action == "hit":
            player_hand.append(draw_card())
            player_score = calculate_score(player_hand)

            if player_score > 21:
                active_blackjack_games.pop(user_id, None)
                dealer_score = calculate_score(dealer_hand)
                record_game_win(user_id, 0)
                add_game_loss(user_id, bet)

                text = (
                    f"🃏 <b>БЛЭКДЖЕК (ПЕРЕБОР)</b>\n\n"
                    f"👤 Игрок: {username}\n"
                    f"{EMOJI_MONEY} Ставка: <b>{fmt(bet)} TON {EMOJI_GEM}</b>\n\n"
                    f"🫵 <b>Твоя рука:</b>\n"
                    f"» {format_hand(player_hand)}\n"
                    f"» Очки: <b>{player_score}</b>\n\n"
                    f"🤖 <b>Рука дилера:</b>\n"
                    f"» {format_hand(dealer_hand)}\n"
                    f"» Очки: <b>{dealer_score}</b>\n\n"
                    f"💥 <b>Перебор!</b> Ты набрал {player_score} очков и проиграл.\n"
                    f"💸 Потеряно: <b>{fmt(bet)} TON</b>\n"
                    f"{EMOJI_MONEY} Твой баланс: <b>{fmt(balances[user_id])} TON {EMOJI_GEM}</b>"
                )
                await query.edit_message_text(text=text, parse_mode="HTML")
                await query.answer("Перебор! Проигрыш.")
                return

            game["processing"] = False  
            keyboard = [
                [
                    InlineKeyboardButton("🃏 Взять еще", callback_data=f"bj_hit_{user_id}"),
                    InlineKeyboardButton("🛑 Хватит", callback_data=f"bj_stand_{user_id}")
                ]
            ]
            text = (
                f"🃏 <b>БЛЭКДЖЕК (21)</b>\n\n"
                f"👤 Игрок: {username}\n"
                f"{EMOJI_MONEY} Ставка: <b>{fmt(bet)} TON {EMOJI_GEM}</b>\n\n"
                f"🫵 <b>Твоя рука:</b>\n"
                f"» {format_hand(player_hand)}\n"
                f"» Очки: <b>{player_score}</b>\n\n"
                f"🤖 <b>Рука дилера:</b>\n"
                f"» {dealer_hand[0]['name']} + 🎴\n"
                f"» Очки: <b>{dealer_hand[0]['value']}</b>\n\n"
                f"<i>Выбери действие: Взять еще одну карту или остановиться?</i>"
            )
            await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            await query.answer("Вы взяли карту!")

        elif action == "stand":
            player_score = calculate_score(player_hand)
            dealer_score = calculate_score(dealer_hand)

            if not pre_win:
                while dealer_score < 17 or dealer_score < player_score:
                    c = draw_card()
                    if dealer_score + c["value"] > 21 and dealer_score < player_score:
                        low_candidates = [card for card in BJ_CARDS if card[1] <= (21 - dealer_score)]
                        if low_candidates:
                            pick = random.choice(low_candidates)
                            c = {"name": f"{pick[0]}{random.choice(BJ_SUITS)}", "value": pick[1], "rank": pick[0]}
                    dealer_hand.append(c)
                    dealer_score = calculate_score(dealer_hand)
                    if dealer_score >= player_score and dealer_score <= 21:
                        break
            else:
                while dealer_score < 17:
                    dealer_hand.append(draw_card())
                    dealer_score = calculate_score(dealer_hand)

            win_amount = 0
            chat_id = update.effective_chat.id if update.effective_chat else (query.message.chat.id if query.message else None)

            if dealer_score > 21:
                win_amount = bet * 2
                balances[user_id] = int(round(balances.get(user_id, 0))) + win_amount
                save_balances()
                record_game_win(user_id, win_amount)
                net_win = win_amount - bet
                add_game_net_win(user_id, net_win)
                
                if chat_id and update.effective_chat and update.effective_chat.type in ("group", "supergroup"):
                    record_chat_member_activity(chat_id, query.from_user, net_win)
                add_history(user_id, "Доход (Блэкджек)", win_amount, "Победа (дилер перебор)")

                result_text = (
                    f"🎉 {EMOJI_FIRE} <b>ПОБЕДА!</b> Дилер перебрал!\n"
                    f"💰 Выигрыш (x2.0): <b>+{fmt(win_amount)} TON {EMOJI_GEM}</b>"
                )
            elif player_score > dealer_score:
                win_amount = bet * 2
                balances[user_id] = int(round(balances.get(user_id, 0))) + win_amount
                save_balances()
                record_game_win(user_id, win_amount)
                net_win = win_amount - bet
                add_game_net_win(user_id, net_win)
                
                if chat_id and update.effective_chat and update.effective_chat.type in ("group", "supergroup"):
                    record_chat_member_activity(chat_id, query.from_user, net_win)
                add_history(user_id, "Доход (Блэкджек)", win_amount, "Победа по очкам")

                result_text = (
                    f"{EMOJI_FIRE} <b>ПОБЕДА!</b> У тебя больше очков!\n"
                    f"💰 Выигрыш (x2.0): <b>+{fmt(win_amount)} TON {EMOJI_GEM}</b>"
                )
            elif player_score < dealer_score:
                record_game_win(user_id, 0)
                add_game_loss(user_id, bet)
                result_text = (
                    f"❌ <b>Вы проиграли!</b> У дилера больше очков.\n"
                    f"💸 Потеряно: <b>{fmt(bet)} TON</b>"
                )
            else:
                win_amount = bet
                balances[user_id] = int(round(balances.get(user_id, 0))) + win_amount
                save_balances()
                add_history(user_id, "Возврат (Блэкджек)", win_amount, "Ничья")

                result_text = (
                    f"🤝 <b>Ничья!</b> Очки равны.\n"
                    f"🔙 Ставка возвращена: <b>{fmt(bet)} TON</b>"
                )

            text = (
                f"🃏 <b>БЛЭКДЖЕК — РЕЗУЛЬТАТЫ</b>\n\n"
                f"👤 Игрок: {username}\n"
                f"{EMOJI_MONEY} Ставка: <b>{fmt(bet)} TON {EMOJI_GEM}</b>\n\n"
                f"🫵 <b>Твоя рука:</b>\n"
                f"» {format_hand(player_hand)}\n"
                f"» Очки: <b>{player_score}</b>\n\n"
                f"🤖 <b>Рука дилера:</b>\n"
                f"» {format_hand(dealer_hand)}\n"
                f"» Очки: <b>{dealer_score}</b>\n\n"
                f"{result_text}\n"
                f"{EMOJI_MONEY} Твой баланс: <b>{fmt(balances[user_id])} TON {EMOJI_GEM}</b>"
            )
            
            await query.edit_message_text(text=text, parse_mode="HTML")
            await query.answer("Игра завершена!")
            
            active_blackjack_games.pop(user_id, None)

    except Exception as e:
        game["processing"] = False  
        print(f"❌ Ошибка в blackjack_callback_handler: {e}")
        traceback.print_exc()
        await query.answer("⚠️ Произошла ошибка во время обработки хода.", show_alert=True)

# =========================================================
# РАЗБОР СТАВКИ РУЛЕТКИ
# =========================================================

def parse_bet(bet):
    bet = bet.lower()

    if bet in {"к", "красное"}:
        return RED, 2.0, "красное"

    if bet in {"ч", "черное", "чёрное"}:
        return BLACK, 2.0, "чёрное"

    if bet in {"чет", "чёт"}:
        numbers = {n for n in range(1, 37) if n % 2 == 0}
        return numbers, 2.0, "чёт"

    if bet == "нечет":
        numbers = {n for n in range(1, 37) if n % 2 != 0}
        return numbers, 2.0, "нечет"

    if "-" in bet:
        parts = bet.split("-", 1)
        if len(parts) != 2:
            return None
        try:
            start_num = int(parts[0])
            end_num = int(parts[1])
        except ValueError:
            return None

        if not (0 <= start_num <= end_num <= 36):
            return None

        numbers = set(range(start_num, end_num + 1))
        coefficient = 36 / len(numbers)
        return (numbers, coefficient, f"{start_num}-{end_num}")

    try:
        number = int(bet)
    except ValueError:
        return None

    if not 0 <= number <= 36:
        return None

    return ({number}, 36.0, f"{number}")

# =========================================================
# START И МЕНЮ КНОПКИ В ЛС
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = get_user(update.effective_user)
    
    if context.args and context.args[0] == "donate":
        await show_donate_menu(update, context)
        return

    chat_type = update.effective_chat.type

    reply_markup = None
    if chat_type == "private":
        keyboard = [
            [KeyboardButton("🎁 Забрать бонус"), KeyboardButton("🎮 Игры")],
            [KeyboardButton("📜 Команды"), KeyboardButton("⭐️ Донат")],
            [KeyboardButton("👤 Профиль"), KeyboardButton("🏦 Банк")],
            [KeyboardButton("💬 Чаты"), KeyboardButton("🏆 Турниры")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "🎰 Виртуальное казино\n\n"
        f"{EMOJI_MONEY} Баланс: {fmt(balances[user_id])} TON {EMOJI_GEM}\n"
        f"{EMOJI_PUMPKIN} Тыкв: {fmt(pumpkin_get(user_id))}\n\n"
        "Используй кнопки внизу или команды:\n"
        "• <b>профиль</b> — ваша статистика и баланс\n"
        "• <b>банк</b> — вклад под 1% в сутки\n"
        "• <b>биржа</b> — биржа тыкв (<b>тыква инфо</b>)\n"
        "• <b>игры</b> — список доступных игр\n"
        "• <b>команды</b> — справка по командам бота\n"
        "• <b>история</b> — история ваших переводов и начислений\n"
        "• <b>чаты</b> — официальные чаты сообщества\n"
        "• <b>донат</b> — пополнить баланс за Telegram Stars ⭐️",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

# =========================================================
# ЧАТЫ СООБЩЕСТВА
# =========================================================

async def show_community_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_msg = update.message if update.message else (update.callback_query.message if update.callback_query else None)
    if not target_msg:
        return

    keyboard = []
    for chat_item in COMMUNITY_CHATS:
        keyboard.append([InlineKeyboardButton(chat_item["name"], url=chat_item["url"])])

    text = (
        f"{EMOJI_CHAT} <b>ЧАТЫ И КАНАЛЫ</b>\n\n"
        f"Присоединяйтесь к нашим сообществам, чтобы играть с другими участниками, "
        f"участвовать в дуэлях, следить за акциями и промокодами!\n\n"
        f"{EMOJI_LOW} <i>Выберите чат для перехода:</i>"
    )

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    if update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")


# =========================================================
# СПРАВКИ: КОМАНДЫ И ИГРЫ
# =========================================================

async def show_commands_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    text = (
        "📜 <b>СПРАВКА ПО КОМАНДАМ БОТА:</b>\n\n"
        "👤 <b>Профиль и Банк:</b>\n"
        "• <b>профиль</b> — посмотреть свой профиль и статистику\n"
        "• <b>банк</b> — депозит под 1% в сутки\n"
        "• <b>чаты</b> — список официальных чатов проекта\n\n"
        "🎲 <b>Кубы:</b>\n"
        "• <code>кубы [сумма] [выбор]</code> — сыграть в кости (число x4.0, чет/нечет x1.5, больше/меньше x1.5)\n\n"
        "🎡 <b>Рулетка:</b>\n"
        "• <code>р [сумма] [ставка]</code> — сделать ставку (например: <code>р 100 к</code>)\n"
        "• <b>гоу</b> — запустить рулетку (после ставки)\n"
        "• <b>отмена</b> — отменить свои ставки в текущем раунде\n"
        "• <b>ставки</b> — посмотреть список твоих сделанных ставок\n"
        "• <b>логи</b> — результаты рулетки\n\n"
        "🃏 <b>Блэкджек:</b>\n"
        "• <code>бд [сумма]</code> — сыграть в Блэкджек (21)\n\n"
        "🎰 <b>Слоты:</b>\n"
        "• <code>слот [сумма]</code> — сыграть в официальные слоты (x1.5, x3, x10 Джекпот)\n\n"
        "📦 <b>Клад:</b>\n"
        "• <code>клад [сумма]</code> — сундуки (0х, 1х, 2х)\n\n"
        "💣 <b>Мины:</b>\n"
        "• <code>мины [сумма]</code> — игра в Мины (по умолчанию 3 мины)\n"
        "• <code>мины [сумма] [3-24]</code> — выбор любого количества мин (от 3 до 24)\n\n"
        "🤠 <b>Дуэли:</b>\n"
        "• <code>дуэль [сумма]</code> (ответом)\n"
        "• <code>кто дуэль [сумма]</code> — открытый вызов в чат\n\n"
        "🏛 <b>Казна чата:</b>\n"
        "• <b>купить казну</b> — покупка казны (100 000 TON)\n"
        "• <code>пополнить казну [сумма]</code>\n"
        "• <b>казна</b> — статус и баланс казны\n\n"
        "🎃 <b>Тыквы:</b>\n"
        "• <b>биржа</b> — график и цена тыкв\n"
        "• <b>тыква инфо</b> — все команды тыкв\n\n"
        "👤 <b>Прочее:</b>\n"
        "• <b>бот</b> — проверить пинг и работоспособность\n"
        "• <b>б</b> или <b>баланс</b> — узнать свой баланс\n"
        "• <b>история</b> — история ваших переводов, донатов и промокодов\n"
        "• <b>топ</b> — таблица лидеров\n"
        "• <b>турнир</b> — ежедневный турнир по рулетке с призами\n"
        "• <code>д [сумма] @username [комментарий]</code> — передать TON\n"
        "• <b>донат</b> — пополнение за звезды ⭐️"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def show_games_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    text = (
        "🎮 <b>ДОСТУПНЫЕ ИГРЫ В КАЗИНО:</b>\n\n"
        "1️⃣ <b>Кубы 🎲</b>\n"
        "Бросай анимированный кубик! Ставь на число (x4.0), чет/нечет (x1.5) или больше/меньше (x1.5).\n"
        "📌 <i>Команда:</i> <code>кубы 500 больше</code>\n\n"
        "2️⃣ <b>Рулетка 🎡</b>\n"
        "Классическая европейская рулетка (0-36). Ставки на цвета (к/ч), чёт/нечет, числа и диапазоны.\n"
        "📌 <i>Команда:</i> <code>р 100 к</code>, затем <b>гоу</b>\n\n"
        "3️⃣ <b>Клад 📦</b>\n"
        "Испытай удачу в 3 сундуках! В одном пусто, во втором возврат (x1), в третьем куш (x2).\n"
        "📌 <i>Команда:</i> <code>клад 500</code>\n\n"
        "4️⃣ <b>Мины 💣</b>\n"
        "Открывай безопасные кристаллы на поле 5х5 и забирай растущий коэффициент!\n"
        "Можно выбрать от 3 до 24 мин.\n"
        "📌 <i>Команда:</i> <code>мины 200</code> или <code>мины 200 10</code>\n\n"
        "5️⃣ <b>Дуэли 🤠</b>\n"
        "Постреляйся с реальным игроком один на один с коэффициентом x2!\n"
        "📌 <i>Команда:</i> <code>дуэль 1000</code> (ответом) или <code>кто дуэль 1000</code>\n\n"
        "6️⃣ <b>Блэкджек 🃏</b>\n"
        "Классическая карточная игра «21». Набери больше очков, чем дилер, но не превысь 21!\n"
        "📌 <i>Команда:</i> <code>бд 500</code> или <code>блекджек 500</code>\n\n"
        "7️⃣ <b>Слоты 🎰</b>\n"
        "Официальный анимированный слот Telegram! Собери три семёрки и сорви джекпот x10.\n"
        "📌 <i>Команда:</i> <code>слот 500</code> или <code>слоты 500</code>\n"
    )
    await update.message.reply_text(text, parse_mode="HTML")

# =========================================================
# ПРОФИЛЬ ИГРОКА
# =========================================================

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_msg = update.message if update.message else (update.callback_query.message if update.callback_query else None)
    if not target_msg:
        return

    user = update.effective_user
    user_id = get_user(user)
    name = get_user_display_name(user)
    bal = int(round(float(balances[user_id])))
    u_game_stats = game_stats.get(user_id, {"won": 0, "lost": 0})
    total_wins_sum = u_game_stats.get("won", 0)
    total_losses_sum = u_game_stats.get("lost", 0)

    text = (
        f"{EMOJI_PLAYER} <b>ЛИЧНЫЙ ПРОФИЛЬ</b>\n\n"
        f"• Игрок: {name}\n"
        f"• ID: <code>{user.id}</code>\n"
        f"\n"
        f"{EMOJI_MONEY} Баланс: <b>{fmt(bal)} TON {EMOJI_GEM}</b>\n"
        f"{EMOJI_PUMPKIN} Тыкв: <b>{fmt(pumpkin_get(user_id))}</b>\n"
        f"{EMOJI_UP} Выиграно: <b>+{fmt(total_wins_sum)} TON {EMOJI_GEM}</b>\n\n"
        f"{EMOJI_NOUP} Проиграно: <b>-{fmt(total_losses_sum)} TON {EMOJI_GEM}</b>"
    )

    keyboard = [
        [
            InlineKeyboardButton("🏦 Банк", callback_data="profile_bank"),
            InlineKeyboardButton("📋 История", callback_data="profile_history")
        ]
    ]

    if update.callback_query:
        await update.callback_query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

# =========================================================
# БАНК
# =========================================================

def build_bank_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Пополнить депозит", callback_data="bank_deposit")],
        [InlineKeyboardButton("Снять с депозита", callback_data="bank_withdraw")]
    ])


async def show_bank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_msg = update.message if update.message else (update.callback_query.message if update.callback_query else None)
    if not target_msg:
        return
    user_id = str(update.effective_user.id)
    acc = get_bank_account(user_id)
    
    text = (
        f"{EMOJI_BA} <b>Банк</b>\n\n"
        f"{EMOJI_BAN}В банке: <b>{fmt(bank_total())} TON</b>\n\n"
        f"{EMOJI_BANK}Ваш депозит: <b>{fmt(acc['balance'])} TON</b>\n"
        f"Процент депозита: <b>1%</b>"
    )

    if update.callback_query:
        await update.callback_query.message.reply_text(
            text,
            reply_markup=build_bank_keyboard(),
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=build_bank_keyboard(),
            parse_mode="HTML"
        )


async def bank_callback(query):
    user_id = str(query.from_user.id)
    action = query.data
    if action not in {"bank_deposit", "bank_withdraw"}:
        return False

    kind = "deposit" if action == "bank_deposit" else "withdraw"
    label = "пополнить" if kind == "deposit" else "снять"
    prompt = await query.message.reply_text(
        f"Введи сумму, которую хочешь {label}. Ответь числом на это сообщение.",
        reply_markup=ForceReply(selective=True)
    )
    bank_waiting[user_id] = (kind, prompt.message_id)
    await query.answer()
    return True


async def process_bank_amount(update: Update, text: str):
    user_id = str(update.effective_user.id)
    pending = bank_waiting.get(user_id)
    if not pending:
        return False

    kind, prompt_id = pending
    if not update.message.reply_to_message or update.message.reply_to_message.message_id != prompt_id:
        return False

    try:
        amount = int(text.strip().replace(" ", ""))
    except ValueError:
        await update.message.reply_text("Введи сумму целым числом.")
        return True
    if amount <= 0:
        await update.message.reply_text("Сумма должна быть больше нуля.")
        return True

    acc = get_bank_account(user_id)
    now = time.time()

    if kind == "deposit":
        if int(round(float(balances.get(user_id, 0)))) < amount:
            await update.message.reply_text(f"{EMOJI_NO}Недостаточно средств на игровом балансе.", parse_mode="HTML")
            return True
        balances[user_id] = int(round(float(balances[user_id]))) - amount
        acc["balance"] += amount
        acc.setdefault("lots", []).append({"amount": amount, "since": now})
        save_balances()
        save_bank()
        add_history(user_id, "Расход (Банк)", amount, "Пополнение депозита")
        result = f"Депозит успешно пополнен на {fmt(amount)} TON."
    else:
        if acc["balance"] < amount:
            await update.message.reply_text("На депозите недостаточно средств.")
            return True
        acc["balance"] -= amount
        balances[user_id] = int(round(float(balances.get(user_id, START_BALANCE)))) + amount
        acc["last_withdrawal"] = now

        remaining = amount
        lots = sorted(acc.get("lots", []), key=lambda lot: lot.get("since", now))
        new_lots = []
        for lot in lots:
            lot_amount = int(lot.get("amount", 0))
            taken = min(remaining, lot_amount)
            remaining -= taken
            if lot_amount > taken:
                new_lots.append({"amount": lot_amount - taken, "since": lot.get("since", now)})
        acc["lots"] = new_lots

        save_balances()
        save_bank()
        add_history(user_id, "Доход (Банк)", amount, "Снятие с депозита")
        result = f"С депозита снято {fmt(amount)} TON."

    bank_waiting.pop(user_id, None)
    await update.message.reply_text(result)
    await show_bank(update, context=None)
    return True

# =========================================================
# ИГРА «КЛАД» (СУНДУКИ)
# =========================================================

async def handle_treasure_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = get_user(update.effective_user)
    parts = update.message.text.split()

    if len(parts) < 2:
        await update.message.reply_text(
            "Укажи ставку для игры в Клад:\nПример: <code>клад 100</code>",
            parse_mode="HTML"
        )
        return

    try:
        bet = int(parts[1].replace(" ", ""))
    except ValueError:
        await update.message.reply_text("❌ Ставка должна быть целым числом.")
        return

    if bet <= 0:
        await update.message.reply_text("❌ Ставка должна быть больше 0.")
        return

    current_bal = int(round(balances[user_id]))
    balances[user_id] = current_bal

    if current_bal < bet:
        await update.message.reply_text(
            f"{EMOJI_NO} Недостаточно TON для игры!\nТвой баланс: <b>{fmt(current_bal)} TON {EMOJI_GEM}</b>",
            parse_mode="HTML"
        )
        return

    balances[user_id] -= bet
    save_balances()
    add_history(user_id, "Расход (Клад)", bet, "Инициация игры")

    prizes = [0, 1, 2]
    random.shuffle(prizes)

    active_treasure_games[user_id] = {
        "bet": bet,
        "prizes": prizes,
        "opened": False
    }

    keyboard = [
        [
            InlineKeyboardButton("📦 Сундук 1", callback_data=f"treasure_{user_id}_0"),
            InlineKeyboardButton("📦 Сундук 2", callback_data=f"treasure_{user_id}_1"),
            InlineKeyboardButton("📦 Сундук 3", callback_data=f"treasure_{user_id}_2"),
        ]
    ]

    await update.message.reply_text(
        f"📦 <b>ИГРА В КЛАД</b>\n\n"
        f"{EMOJI_MONEY} Ставка: <b>{fmt(bet)} TON {EMOJI_GEM}</b>\n"
        f"Перед тобой 3 сундука. В одном пусто, во втором возврат (x1), в третьем куш (x2)!\n\n"
        f"👇 <i>Выбери свой сундук:</i>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )


async def treasure_callback_handler(query, user_id: str, box_idx: int):
    q_user_id = str(query.from_user.id)
    if q_user_id != user_id:
        await query.answer("Это не твоя игра в клад!", show_alert=True)
        return

    game = active_treasure_games.get(user_id)
    if not game or game["opened"]:
        await query.answer("Эта игра уже завершена!", show_alert=True)
        return

    game["opened"] = True
    bet = game["bet"]
    prizes = game["prizes"]

    chosen_prize = prizes[box_idx]

    icons = {0: "❌ (пусто)", 1: "🔙 (возврат x1)", 2: "💎 (куш x2)"}
    chest_results = [icons[p] for p in prizes]

    result_text = (
        f"📦 <b>ИТОГИ ИГРЫ В КЛАД</b>\n\n"
        f"Сундуки скрывали:\n"
        f"1️⃣ {chest_results[0]}\n"
        f"2️⃣ {chest_results[1]}\n"
        f"3️⃣ {chest_results[2]}\n\n"
        f"🎯 Ты выбрал сундук №{box_idx + 1}!\n"
    )

    if chosen_prize == 0:
        record_game_win(user_id, 0)
        add_game_loss(user_id, bet)
        result_text += f"💥 <b>Увы, здесь пусто!</b> Ставка сгорела.\n💸 Потеряно: <b>{fmt(bet)} TON</b>"
    elif chosen_prize == 1:
        win_amount = bet
        balances[user_id] = int(round(balances[user_id])) + win_amount
        save_balances()
        add_history(user_id, "Возврат (Клад)", win_amount, "Выбран x1")
        result_text += f"🔙 <b>Возврат ставки (x1)!</b>\n💳 На баланс возвращено: <b>{fmt(win_amount)} TON</b>"
    else:
        win_amount = bet * 2
        balances[user_id] = int(round(balances[user_id])) + win_amount
        save_balances()
        record_game_win(user_id, win_amount)
        net_win = win_amount - bet
        add_game_net_win(user_id, net_win)
        add_history(user_id, "Доход (Клад)", win_amount, "Выбран x2")
        
        chat_id = query.message.chat.id if query.message and query.message.chat else None
        if chat_id and query.message.chat.type in ("group", "supergroup"):
            record_chat_member_activity(chat_id, query.from_user, net_win)

        result_text += f"🎉 <b>КУШ! МЕГА-ПОБЕДА (x2)!</b>\n💰 Выигрыш: <b>+{fmt(win_amount)} TON {EMOJI_GEM}</b>"

    result_text += f"\n\n{EMOJI_MONEY} Твой баланс: <b>{fmt(balances[user_id])} TON {EMOJI_GEM}</b>"

    active_treasure_games.pop(user_id, None)

    try:
        await query.edit_message_text(result_text, parse_mode="HTML")
    except Exception:
        await query.message.reply_text(result_text, parse_mode="HTML")
    await query.answer("Сундук открыт!")

# =========================================================
# БАЛАНС С РАНГОМ
# =========================================================

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user = update.effective_user
    user_id = get_user(user)
    name = get_user_display_name(user)
    bal = int(round(float(balances[user_id])))
    text = (
        f"👤 <b>{name}</b>\n"
        f"{EMOJI_MONEY} Баланс: <b>{fmt(bal)}</b> TON {EMOJI_GEM}\n"
        f"{EMOJI_PUMPKIN} Тыкв: <b>{fmt(pumpkin_get(user_id))}</b>"
    )

    keyboard = []
    if bal < 500:
        bot_un = context.bot.username
        url = f"https://t.me/{bot_un}?start=donate"
        keyboard.append([InlineKeyboardButton("💳 Пополнить баланс", url=url)])

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
        parse_mode="HTML"
    )

# =========================================================
# ИСТОРИЯ ОПЕРАЦИЙ
# =========================================================

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_msg = update.message if update.message else (update.callback_query.message if update.callback_query else None)
    if not target_msg:
        return

    user_id = get_user(update.effective_user)
    user_history = history_data.get(user_id, [])

    important_types = ("Перевод", "Донат", "Промокод", "Админ")
    filtered_history = [
        item for item in user_history 
        if any(keyword in item.get("type", "") for keyword in important_types)
    ]

    if not filtered_history:
        text = "📋 <b>Ваша финансовая история пуста.</b>\n<i>(Здесь отображаются переводы другим игрокам, пополнения через донат и промокоды)</i>"
        if update.callback_query:
            await update.callback_query.message.reply_text(text, parse_mode="HTML")
        else:
            await update.message.reply_text(text, parse_mode="HTML")
        return

    lines = ["📋 <b>ИСТОРИЯ ПЕРЕВОДОВ И ПОПОЛНЕНИЙ:</b>\n"]
    for idx, item in enumerate(reversed(filtered_history[-20:]), start=1):
        t_type = item.get("type", "Операция")
        amount = item.get("amount", 0)
        details = item.get("details", "")
        time_str = item.get("timestamp", "")

        sign = "+" if "Доход" in t_type else "-"
        formatted_amount = f"<b>{sign}{fmt(amount)} TON {EMOJI_GEM}</b>"

        lines.append(f"<code>{idx}.</code> 📅 {time_str} | <b>{t_type}</b>\n↳ Сумма: {formatted_amount}\n↳ Детали: <i>{details}</i>\n")

    text = "\n".join(lines)
    if update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode="HTML")
    else:
        await update.message.reply_text(text, parse_mode="HTML")

# =========================================================
# СПИСОК СТАВОК ИГРОКА
# =========================================================

async def show_my_bets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat_id = update.effective_chat.id
    user_id = str(update.effective_user.id)

    bets = pending_bets.get(str(chat_id), []) or pending_bets.get(chat_id, [])
    my_bets = [b for b in bets if str(b["user_id"]) == user_id]

    if not my_bets:
        await update.message.reply_text("У тебя нет активных ставок в этом раунде рулетки.")
        return

    total_spent = sum(b["amount"] for b in my_bets)
    lines = ["📋 <b>Твои активные ставки:</b>\n"]

    for b in my_bets:
        lines.append(f"• <b>{fmt(b['amount'])} TON</b> на <b>{b['bet_name']}</b> (x{b['coefficient']:.2f})")

    lines.append("———————————————")
    lines.append(f"{EMOJI_MONEY} Всего списано за раунд: <b>{fmt(total_spent)} TON {EMOJI_GEM}</b>")
    lines.append(f"🎯 Всего сделано ставок: <b>{len(my_bets)} из {MAX_BETS_PER_GAME}</b>")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

# =========================================================
# ТОП ПО БАЛАНСУ И ВЫИГРЫШАМ
# =========================================================

def build_top_menu():
    kb = [
        [
            InlineKeyboardButton("🏆 Топ балансов", callback_data="top_balances"),
            InlineKeyboardButton("🏆 Топ выигрышей", callback_data="top_wins")
        ]
    ]
    return InlineKeyboardMarkup(kb)


async def show_top_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    await update.message.reply_text(
        "📊 <b>Выбери, какой топ хочешь посмотреть:</b>\n"
        "<i>(Топ выигрышей показывает статистику чистых выигрышей игроков в текущем чате и сбрасывается ежедневно в 00:00 МСК)</i>",
        reply_markup=build_top_menu(),
        parse_mode="HTML"
    )


def render_top_balances() -> str:
    sorted_users = sorted(
        balances.items(),
        key=lambda item: float(item[1]),
        reverse=True
    )[:20]

    lines = ["👑 <b>ТОП-20 ПО БАЛАНСУ:</b>\n"]
    if not sorted_users:
        lines.append("Список пока пуст.")
    else:
        for idx, (uid, bal) in enumerate(sorted_users, start=1):
            name = user_stats.get(uid, {}).get("name") or f"Игрок {uid}"
            lines.append(f"<b>{idx}.</b> {name} — <code>{fmt(bal)}</code> TON {EMOJI_GEM}")

    lines.append("\n<i>Обновляется в реальном времени</i>")
    return "\n".join(lines)


def render_top_wins_for_chat(chat_id) -> str:
    chat_id = str(chat_id)
    chat_data = chat_members_store.get(chat_id, {})
    
    sorted_users = sorted(
        chat_data.items(),
        key=lambda item: int(item[1].get("win", 0)),
        reverse=True
    )[:20]

    lines = ["🏆 <b>ТОП-20 ПО ВЫИГРЫШАМ В ЭТОМ ЧАТЕ:</b>\n"]
    valid_entries = [u for u in sorted_users if u[1].get("win", 0) > 0]

    if not valid_entries:
        lines.append("В этом чате ещё никто ничего не выиграл сегодня.")
    else:
        for idx, (uid, data) in enumerate(valid_entries, start=1):
            name = data.get("name") or f"Игрок {uid}"
            win = data.get("win", 0)
            lines.append(f"<b>{idx}.</b> {name} — <b>+{fmt(win)}</b> TON {EMOJI_GEM}")

    lines.append("\n<i>🏆 Сбрасывается ежедневно в 00:00 МСК</i>")
    return "\n".join(lines)

# =========================================================
# ДУЭЛИ
# =========================================================

async def handle_duel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global duel_id_counter
    if not update.message:
        return

    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("❌ Дуэли проводятся только в группе!")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "❌ Используй команду ответом на сообщение игрока:\n<code>дуэль 500</code>\n\n"
            "Или напиши открытый вызов: <code>кто дуэль 500</code>",
            parse_mode="HTML"
        )
        return

    parts = update.message.text.split()
    if len(parts) < 2:
        await update.message.reply_text(
            "❌ Укажи ставку: <code>дуэль 500</code>",
            parse_mode="HTML"
        )
        return

    try:
        amount = int(parts[1].replace(" ", ""))
    except ValueError:
        await update.message.reply_text("❌ Ставка должна быть целым числом.")
        return

    if amount <= 0:
        await update.message.reply_text("❌ Ставка должна быть больше 0.")
        return

    challenger = update.effective_user
    opponent = update.message.reply_to_message.from_user

    if opponent.is_bot:
        await update.message.reply_text("❌ Нельзя вызывать ботов на дуэль!")
        return

    if challenger.id == opponent.id:
        await update.message.reply_text("❌ Нельзя стреляться с самим собой!")
        return

    c_id = get_user(challenger)
    o_id = get_user(opponent)

    c_bal = int(round(balances[c_id]))
    o_bal = int(round(balances[o_id]))

    if c_bal < amount:
        await update.message.reply_text(
            f"{EMOJI_NO} У вас недостаточно TON для этой дуэли!\nВаш баланс: <b>{fmt(c_bal)} TON {EMOJI_GEM}</b>",
            parse_mode="HTML"
        )
        return

    if o_bal < amount:
        o_name = get_user_display_name(opponent)
        await update.message.reply_text(
            f"{EMOJI_NO} У {o_name} недостаточно TON для дуэли!\nЕго баланс: <b>{fmt(o_bal)} TON {EMOJI_GEM}</b>",
            parse_mode="HTML"
        )
        return

    duel_id = duel_id_counter
    duel_id_counter += 1

    win_amount = int(round(amount * DUEL_MULTIPLIER))
    c_name = get_user_display_name(challenger)
    o_name = get_user_display_name(opponent)

    pending_duels[duel_id] = {
        "chat_id": chat.id,
        "challenger_id": c_id,
        "challenger_name": c_name,
        "opponent_id": o_id,
        "opponent_name": o_name,
        "amount": amount,
        "win_amount": win_amount,
        "created_at": time.time()
    }

    keyboard = [
        [
            InlineKeyboardButton("🎯 Принять вызов", callback_data=f"duel_accept_{duel_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"duel_decline_{duel_id}")
        ]
    ]

    await update.message.reply_text(
        f"⚔️ <b>ВЫЗОВ НА ДУЭЛЬ!</b>\n\n"
        f"🤠 <b>{c_name}</b> бросает вызов <b>{o_name}</b>!\n"
        f"{EMOJI_MONEY} Ставка каждого: <b>{fmt(amount)} TON {EMOJI_GEM}</b>\n"
        f"🏆 Победитель забирает банк: <b>{fmt(win_amount)} TON {EMOJI_GEM}</b> (x{int(DUEL_MULTIPLIER)})\n\n"
        f"<i>У {o_name} есть 1 минута, чтобы принять вызов!</i>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )


async def duel_callback_handler(query, data: str):
    user_id = str(query.from_user.id)

    if data.startswith("duel_decline_open_"):
        duel_id = int(data.split("_")[3])
        duel = open_duels.get(duel_id)
        if not duel:
            await query.answer("Дуэль уже недействительна.", show_alert=True)
            return

        if user_id != duel["challenger_id"]:
            await query.answer("❌ Только создатель вызова может отменить его!", show_alert=True)
            return

        open_duels.pop(duel_id, None)
        await query.edit_message_text(
            f"{EMOJI_NO} {duel['challenger_name']} отменил своё предложение дуэли.",
            parse_mode="HTML"
        )
        await query.answer("Вызов отменён.")
        return

    if data.startswith("duel_accept_open_"):
        duel_id = int(data.split("_")[3])
        duel = open_duels.get(duel_id)
        if not duel:
            await query.answer("Дуэль не найдена или её время вышло.", show_alert=True)
            return

        opponent = query.from_user
        o_id = get_user(opponent)

        if o_id == duel["challenger_id"]:
            await query.answer("❌ Вы не можете дуэлиться с самим собой!", show_alert=True)
            return

        amount = duel["amount"]
        c_id = duel["challenger_id"]

        if int(round(balances.get(c_id, 0))) < amount:
            open_duels.pop(duel_id, None)
            await query.edit_message_text(
                f"{EMOJI_NO} Дуэль отменена: у {duel['challenger_name']} не хватает средств!",
                parse_mode="HTML"
            )
            return

        if int(round(balances.get(o_id, 0))) < amount:
            await query.answer(f"{EMOJI_NO} Недостаточно средств! Нужно {fmt(amount)} TON {EMOJI_GEM}", show_alert=True)
            return

        balances[c_id] -= amount
        balances[o_id] -= amount
        save_balances()

        add_history(c_id, "Расход (Дуэль)", amount, f"Дуэль против {get_user_display_name(opponent)}")
        add_history(o_id, "Расход (Дуэль)", amount, f"Дуэль против {duel['challenger_name']}")

        open_duels.pop(duel_id, None)

        o_name = get_user_display_name(opponent)
        turn_id = random.choice([c_id, o_id])
        turn_name = duel["challenger_name"] if turn_id == c_id else o_name

        active_duels[duel_id] = {
            "challenger_id": c_id,
            "challenger_name": duel["challenger_name"],
            "opponent_id": o_id,
            "opponent_name": o_name,
            "amount": amount,
            "win_amount": duel["win_amount"],
            "turn_id": turn_id,
            "last_action_text": "Дуэлянты зарядили револьверы и встали к барьеру."
        }

        keyboard = [
            [
                InlineKeyboardButton("🔫 Выстрел", callback_data=f"duel_shoot_{duel_id}"),
                InlineKeyboardButton("🏳 Отказаться", callback_data=f"duel_surrender_{duel_id}")
            ]
        ]

        await query.edit_message_text(
            f"⚔️ <b>ДУЭЛЬ НАЧАЛАСЬ!</b>\n\n"
            f"🤠 {duel['challenger_name']} ⚡️ {o_name}\n"
            f"{EMOJI_MONEY} Ставка каждого: <b>{fmt(amount)} TON {EMOJI_GEM}</b>\n"
            f"🏆 Победитель заберёт: <b>{fmt(duel['win_amount'])} TON {EMOJI_GEM}</b>\n\n"
            f"📝 <i>Дуэлянты встали на позиции и взвели курки.</i>\n\n"
            f"👉 Право первого выстрела за: <b>{turn_name}</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        await query.answer("Вы приняли дуэль!")
        return

    if data.startswith("duel_decline_"):
        duel_id = int(data.split("_")[2])
        duel = pending_duels.get(duel_id)
        if not duel:
            await query.answer("Дуэль уже недействительна.", show_alert=True)
            return

        if user_id != duel["opponent_id"] and user_id != duel["challenger_id"]:
            await query.answer("Это не твой вызов на дуэль!", show_alert=True)
            return

        pending_duels.pop(duel_id, None)

        if user_id == duel["opponent_id"]:
            reason_text = f"{EMOJI_NO} <b>{duel['opponent_name']} отклонил вызов на дуэль!</b>\nДеньги ни у кого не списаны."
        else:
            reason_text = f"{EMOJI_NO} <b>{duel['challenger_name']} отозвал свой вызов на дуэль.</b>"

        await query.edit_message_text(reason_text, parse_mode="HTML")
        await query.answer("Вызов отклонён.")
        return

    if data.startswith("duel_accept_"):
        duel_id = int(data.split("_")[2])
        duel = pending_duels.get(duel_id)
        if not duel:
            await query.answer("Дуэль не найдена или уже завершена.", show_alert=True)
            return

        if user_id != duel["opponent_id"]:
            await query.answer("Принять дуэль может только тот, кому бросили вызов!", show_alert=True)
            return

        c_id = duel["challenger_id"]
        o_id = duel["opponent_id"]
        amount = duel["amount"]

        if int(round(balances.get(c_id, 0))) < amount:
            pending_duels.pop(duel_id, None)
            await query.edit_message_text(
                f"{EMOJI_NO} Дуэль отменена: у {duel['challenger_name']} не хватает средств!",
                parse_mode="HTML"
            )
            return

        if int(round(balances.get(o_id, 0))) < amount:
            pending_duels.pop(duel_id, None)
            await query.edit_message_text(
                f"{EMOJI_NO} У тебя недостаточно средств для дуэли!",
                parse_mode="HTML"
            )
            return

        balances[c_id] -= amount
        balances[o_id] -= amount
        save_balances()

        add_history(c_id, "Расход (Дуэль)", amount, f"Дуэль против {duel['opponent_name']}")
        add_history(o_id, "Расход (Дуэль)", amount, f"Дуэль против {duel['challenger_name']}")

        pending_duels.pop(duel_id, None)

        turn_id = random.choice([c_id, o_id])
        turn_name = duel["challenger_name"] if turn_id == c_id else duel["opponent_name"]

        active_duels[duel_id] = {
            "challenger_id": c_id,
            "challenger_name": duel["challenger_name"],
            "opponent_id": o_id,
            "opponent_name": duel["opponent_name"],
            "amount": amount,
            "win_amount": duel["win_amount"],
            "turn_id": turn_id,
            "last_action_text": "Дуэлянты зарядили револьверы и встали к барьеру."
        }

        keyboard = [
            [
                InlineKeyboardButton("🔫 Выстрел", callback_data=f"duel_shoot_{duel_id}"),
                InlineKeyboardButton("🏳 Отказаться", callback_data=f"duel_surrender_{duel_id}")
            ]
        ]

        await query.edit_message_text(
            f"⚔️ <b>ДУЭЛЬ ПРИНЯТА И НАЧАЛАСЬ!</b>\n\n"
            f"🤠 {duel['challenger_name']} ⚡️ {duel['opponent_name']}\n"
            f"{EMOJI_MONEY} Ставка каждого: <b>{fmt(amount)} TON {EMOJI_GEM}</b>\n"
            f"🏆 Победитель заберёт: <b>{fmt(duel['win_amount'])} TON {EMOJI_GEM}</b>\n\n"
            f"📝 <i>Дуэлянты встали на позиции и взвели курки.</i>\n\n"
            f"👉 Право первого выстрела за: <b>{turn_name}</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        await query.answer("Вы приняли дуэль!")
        return

    if data.startswith("duel_shoot_"):
        duel_id = int(data.split("_")[2])
        duel = active_duels.get(duel_id)
        if not duel:
            await query.answer("Дуэль завершена или не найдена.", show_alert=True)
            return

        c_id = duel["challenger_id"]
        o_id = duel["opponent_id"]

        if user_id != c_id and user_id != o_id:
            await query.answer("Ты не участвуешь в этой дуэли!", show_alert=True)
            return

        if user_id != duel["turn_id"]:
            await query.answer("Сейчас не твоя очередь стрелять!", show_alert=True)
            return

        shooter_name = duel["challenger_name"] if user_id == c_id else duel["opponent_name"]
        target_id = o_id if user_id == c_id else c_id
        target_name = duel["opponent_name"] if user_id == c_id else duel["challenger_name"]

        roll = random.random()

        if roll < 0.40:
            win_amount = duel["win_amount"]
            balances[user_id] = int(round(balances[user_id])) + win_amount
            save_balances()

            record_game_win(user_id, win_amount)
            net_win = win_amount - duel["amount"]
            add_game_net_win(user_id, net_win)
            add_game_loss(target_id, duel["amount"])

            if query.message.chat and query.message.chat.type in ("group", "supergroup"):
                record_chat_member_activity(query.message.chat.id, query.from_user, net_win)

            add_history(user_id, "Доход (Дуэль)", win_amount, "Победа в перестрелке")
            active_duels.pop(duel_id, None)

            await query.edit_message_text(
                f"⚔️ <b>ДУЭЛЬ ОКОНЧЕНА!</b>\n\n"
                f"🤠 <b>{shooter_name}</b> нажимает на спуск...\n"
                f"💥 <b>БАХ! ТОЧНОЕ ПОПАДАНИЕ!</b> Игрок <b>{target_name}</b> сражён наповал!\n\n"
                f"🏆 Победитель: <b>{shooter_name}</b>\n"
                f"🎉 Награда: <b>+{fmt(win_amount)} TON {EMOJI_GEM}</b>\n"
                f"{EMOJI_MONEY} Баланс победителя: <b>{fmt(balances[user_id])} TON {EMOJI_GEM}</b>",
                parse_mode="HTML"
            )
            await query.answer("Точный выстрел! 💥")
            return

        elif roll < 0.85:
            action_text = f"💨 <b>{shooter_name}</b> выстрелил, но <b>ПРОМАХНУЛСЯ</b>! Пуля ушла в молоко."
            duel["turn_id"] = target_id
            duel["last_action_text"] = action_text
        else:
            action_text = f"🔧 <b>{shooter_name}</b> нажимает на курок... <b>ПИСТОЛЕТ ЗАКЛИНИЛ</b>! Осечка!"
            duel["turn_id"] = target_id
            duel["last_action_text"] = action_text

        next_shooter_name = target_name

        keyboard = [
            [
                InlineKeyboardButton("🔫 Выстрел", callback_data=f"duel_shoot_{duel_id}"),
                InlineKeyboardButton("🏳 Отказаться", callback_data=f"duel_surrender_{duel_id}")
            ]
        ]

        await query.edit_message_text(
            f"⚔️ <b>ИДЕТ ДУЭЛЬ!</b>\n\n"
            f"🤠 {duel['challenger_name']} ⚡️ {duel['opponent_name']}\n"
            f"{EMOJI_MONEY} Ставка каждого: <b>{fmt(duel['amount'])} TON {EMOJI_GEM}</b>\n"
            f"🏆 Банк на кону: <b>{fmt(duel['win_amount'])} TON {EMOJI_GEM}</b>\n\n"
            f"📝 {action_text}\n\n"
            f"👉 Очередь стрелять переходит к: <b>{next_shooter_name}</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        await query.answer("Осечка/Промах! Переход хода.")
        return

    data_split = data.split("_")
    if len(data_split) >= 3 and data_split[1] == "surrender":
        duel_id = int(data_split[2])
        duel = active_duels.get(duel_id)
        if not duel:
            await query.answer("Дуэль завершена или не найдена.", show_alert=True)
            return

        c_id = duel["challenger_id"]
        o_id = duel["opponent_id"]

        if user_id != c_id and user_id != o_id:
            await query.answer("Ты не участник этой дуэли!", show_alert=True)
            return

        surrendered_name = duel["challenger_name"] if user_id == c_id else duel["opponent_name"]
        winner_id = o_id if user_id == c_id else c_id
        winner_name = duel["opponent_name"] if user_id == c_id else duel["challenger_name"]
        win_amount = duel["win_amount"]

        balances[winner_id] = int(round(balances[winner_id])) + win_amount
        save_balances()
        record_game_win(winner_id, win_amount)
        
        net_win = win_amount - duel["amount"]
        add_game_net_win(winner_id, net_win)
        add_game_loss(user_id, duel["amount"])

        if query.message.chat and query.message.chat.type in ("group", "supergroup"):
            winner_user_obj = query.from_user if str(query.from_user.id) == str(winner_id) else None
            if winner_user_obj:
                record_chat_member_activity(query.message.chat.id, winner_user_obj, net_win)

        add_history(winner_id, "Доход (Дуэль)", win_amount, f"Оппонент {surrendered_name} сдался")
        active_duels.pop(duel_id, None)

        await query.edit_message_text(
            f"🏳 <b>ДУЭЛЬ ЗАВЕРШЕНА СДАЧЕЙ!</b>\n\n"
            f"🤠 Игрок <b>{surrendered_name}</b> испугался и сдался!\n"
            f"💸 Его ставка <b>{fmt(duel['amount'])} TON</b> потеряна.\n\n"
            f"🏆 Победитель: <b>{winner_name}</b>\n"
            f"🎉 Получает весь банк: <b>+{fmt(win_amount)} TON {EMOJI_GEM}</b>\n"
            f"{EMOJI_MONEY} Новый баланс победителя: <b>{fmt(balances[winner_id])} TON {EMOJI_GEM}</b>",
            parse_mode="HTML"
        )
        await query.answer("Вы сдались 🏳")
        return

# =========================================================
# ДОНАТ ЗА TELEGRAM STARS ⭐️
# =========================================================

async def show_donate_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    keyboard = [
        [
            InlineKeyboardButton("50 ⭐️ (150 тыс. TON)", callback_data="donate_stars_50"),
            InlineKeyboardButton("100 ⭐️ (300 тыс. TON)", callback_data="donate_stars_100")
        ],
        [
            InlineKeyboardButton("250 ⭐️", callback_data="donate_stars_250"),
            InlineKeyboardButton("500 ⭐️", callback_data="donate_stars_500")
        ],
        [
            InlineKeyboardButton("1 000 ⭐️", callback_data="donate_stars_1000"),
            InlineKeyboardButton("2 500 ⭐️", callback_data="donate_stars_2500")
        ],
        [
            InlineKeyboardButton("✍️ Ввести своё количество звёзд", callback_data="donate_custom")
        ]
    ]

    await update.message.reply_text(
        "⭐️ <b>ПОПОЛНЕНИЕ БАЛАНСА ЗА TELEGRAM STARS</b>\n\n"
        f"Курс обмена: <b>1 ⭐️ = {fmt(STARS_EXCHANGE_RATE)} TON {EMOJI_GEM}</b>\n\n"
        "Выбери пакет звёзд ниже или введи своё количество (от 5 до 10 000):",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )


async def donate_callback_handler(query, data: str, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(query.from_user.id)

    if data == "donate_custom":
        waiting_for_custom_stars[user_id] = True
        await query.edit_message_text(
            "✍️ <b>ВВЕДИ СВОЁ КОЛИЧЕСТВО ЗВЁЗД:&</b>\n\n"
            "Отправь в чат число от 5 до 10 000 (например: 300)",
            parse_mode="HTML"
        )
        await query.answer()
        return

    if data.startswith("donate_stars_"):
        stars_count = int(data.split("_")[2])
        await create_stars_invoice(query.message, context, stars_count)
        await query.answer()


async def create_stars_invoice(message, context: ContextTypes.DEFAULT_TYPE, stars_count: int):
    if not (5 <= stars_count <= 10000):
        await message.reply_text("❌ Количество звёзд должно быть от 5 до 10 000!")
        return

    ton_amount = stars_count * STARS_EXCHANGE_RATE
    title = f"Пополнение баланса на {fmt(ton_amount)} TON"
    description = f"Покупка игровой валюты за {stars_count} Telegram Stars ⭐️"
    payload = f"donate_{message.chat.id}_{stars_count}_{int(time.time())}"
    currency = "XTR"
    prices = [LabeledPrice(f"{stars_count} ⭐️ Stars", stars_count)]

    try:
        await context.bot.send_invoice(
            chat_id=message.chat.id,
            title=title,
            description=description,
            payload=payload,
            provider_token=PROVIDER_TOKEN,
            currency=currency,
            prices=prices,
            start_parameter="donate-topup"
        )
    except Exception as e:
        await message.reply_text(
            f"⚠️ Ошибка создания счёта звёзд: {e}\n\n"
            f"<i>(Убедитесь, что бот настроен как платежный магазин в BotFather или используется тестовый режим)</i>",
            parse_mode="HTML"
        )


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    stars_paid = payment.total_amount
    user_id = str(update.effective_user.id)

    ton_reward = stars_paid * STARS_EXCHANGE_RATE
    balances[user_id] = int(round(balances.get(user_id, START_BALANCE))) + ton_reward
    save_balances()
    add_history(user_id, "Доход (Донат)", ton_reward, f"Покупка {stars_paid} звезд ⭐️")

    await update.message.reply_text(
        f"✅ <b>ОПЛАТА УСПЕШНО ПРОШЛА!</b>\n\n"
        f"⭐️ Списано звёзд: <b>{stars_paid} ⭐️</b>\n"
        f"💳 Зачислено на баланс: <b>+{fmt(ton_reward)} TON {EMOJI_GEM}</b>\n"
        f"{EMOJI_MONEY} Твой новый баланс: <b>{fmt(balances[user_id])} TON {EMOJI_GEM}</b>",
        parse_mode="HTML"
    )

# =========================================================
# КАЗНА ЧАТА
# =========================================================

async def buy_treasury(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat = update.effective_chat
    user = update.effective_user
    chat_id = chat.id
    chat_key = str(chat_id)

    if chat.type in ("private",):
        await update.message.reply_text("❌ Казну можно создать только в группе или супергруппе!")
        return

    user_id = get_user(user)

    try:
        member = await chat.get_member(user.id)
        if member.status != "creator":
            await update.message.reply_text("❌ Только владелец (создатель) чата может купить казну!")
            return
    except Exception as e:
        await update.message.reply_text(f"❌ Не удалось проверить права владельца: {e}")
        return

    if chat_key in treasuries:
        await update.message.reply_text(
            f"🏛 В этом чате казна уже создана!\n"
            f"{EMOJI_MONEY} Баланс казны: <b>{fmt(treasuries[chat_key]['balance'])} TON {EMOJI_GEM}</b>",
            parse_mode="HTML"
        )
        return

    if int(round(balances[user_id])) < TREASURY_COST:
        await update.message.reply_text(
            f"{EMOJI_NO} Недостаточно средств для покупки казны!\n"
            f"Стоимость: <b>{fmt(TREASURY_COST)} TON {EMOJI_GEM}</b>\n"
            f"Твой баланс: <b>{fmt(balances[user_id])} TON {EMOJI_GEM}</b>",
            parse_mode="HTML"
        )
        return

    balances[user_id] -= TREASURY_COST
    save_balances()
    add_history(user_id, "Расход (Казна)", TREASURY_COST, "Покупка казны")

    treasuries[chat_key] = {
        "balance": 0,
        "owner_id": user_id,
        "created_at": datetime.now(MSK_TZ).isoformat()
    }
    save_treasuries()

    await update.message.reply_text(
        f"🏛 <b>Казна чата успешно приобретена!</b>\n\n"
        f"👑 Владелец: {get_user_display_name(user)}\n"
        f"💸 Списано: <code>{fmt(TREASURY_COST)}</code> TON {EMOJI_GEM}\n"
        f"{EMOJI_MONEY} Баланс казны: <code>0</code> TON {EMOJI_GEM}\n\n"
        f"Теперь любой игрок может пополнить её командой: <code>Пополнить казну сумма</code>\n"
        f"Каждый, кто пригласит нового участника, получит <b>{fmt(INVITE_REWARD)} TON</b> из казны!",
        parse_mode="HTML"
    )


async def deposit_treasury(update: Update, amount: int):
    if not update.message:
        return

    chat_key = str(update.effective_chat.id)
    if chat_key not in treasuries:
        await update.message.reply_text(
            "🏛 В этом чате ещё нет казны!\n"
            f"Владелец чата может купить её за <b>{fmt(TREASURY_COST)} TON</b> командой: <code>Купить казну</code>",
            parse_mode="HTML"
        )
        return

    if amount <= 0:
        await update.message.reply_text("❌ Сумма пополнения должна быть больше 0.")
        return

    user = update.effective_user
    user_id = get_user(user)

    if int(round(balances[user_id])) < amount:
        await update.message.reply_text(
            f"{EMOJI_NO} Недостаточно средств!\n"
            f"Нужно: {fmt(amount)} TON {EMOJI_GEM} \n"
            f"Твой баланс: {fmt(balances[user_id])} TON {EMOJI_GEM}"
        )
        return

    balances[user_id] -= amount
    treasuries[chat_key]["balance"] += amount

    save_balances()
    save_treasuries()
    add_history(user_id, "Расход (Казна)", amount, f"Пополнение казны чата")

    name = get_user_display_name(user)
    await update.message.reply_text(
        f"🏛 <b>Казна пополнена!</b>\n\n"
        f"👤 Благодетель: {name}\n"
        f"➕ Внесено: <b>{fmt(amount)} TON {EMOJI_GEM}</b>\n"
        f"{EMOJI_MONEY} Текущий баланс казны: <b>{fmt(treasuries[chat_key]['balance'])} TON {EMOJI_GEM}</b>",
        parse_mode="HTML"
    )


async def show_treasury_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat = update.effective_chat
    chat_key = str(chat.id)
    
    if chat_key not in treasuries:
        await update.message.reply_text(
            "🏛 <b>КАЗНА ЧАТА</b>\n\n"
            f"{EMOJI_MONEY} Статус: <b>Казна не приобретена в этом чате.</b>\n"
            f"Стоимость создания: <b>{fmt(TREASURY_COST)} TON {EMOJI_GEM}</b>\n"
            f"Для покупки владелец чата может написать: <code>Купить казну</code>",
            parse_mode="HTML"
        )
        return

    bal = treasuries[chat_key]["balance"]
    await update.message.reply_text(
        f"🏛 <b>КАЗНА ЧАТА</b>\n\n"
        f"{EMOJI_MONEY} Баланс казны: <b>{fmt(bal)} TON {EMOJI_GEM}</b>\n"
        f"🎁 Награда за 1 приглашённого участника: <b>{fmt(INVITE_REWARD)} TON {EMOJI_GEM}</b>\n\n"
        f"<i>Пополнить казну:</i> <code>Пополнить казну [сумма]</code>\n"
        f"<i>(Снимать средства с казны нельзя — они идут только на выплаты пригласившим)</i>",
        parse_mode="HTML"
    )


async def process_invite_reward(chat_id, inviter, joined_users, context):
    chat_key = str(chat_id)
    if chat_key not in treasuries:
        return

    if not inviter or inviter.is_bot:
        return

    for joined_user in joined_users:
        if not joined_user or joined_user.is_bot or joined_user.id == inviter.id:
            continue

        current_treasury = treasuries[chat_key]["balance"]
        if current_treasury < INVITE_REWARD:
            break

        inviter_id = get_user(inviter)
        treasuries[chat_key]["balance"] -= INVITE_REWARD
        balances[inviter_id] = int(round(balances.get(inviter_id, START_BALANCE))) + INVITE_REWARD

        save_balances()
        save_treasuries()
        add_history(inviter_id, "Доход (Приглашение)", INVITE_REWARD, f"Приглашение участника {get_user_display_name(joined_user)}")

        name = get_user_display_name(inviter)
        invited_name = get_user_display_name(joined_user)
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"🎉 <b>Награда из казны чата!</b>\n\n"
                    f"👤 {name} пригласил(а) участника {invited_name}\n"
                    f"{EMOJI_MONEY} Выплачено из казны: <b>+{fmt(INVITE_REWARD)} TON {EMOJI_GEM}</b>\n"
                    f"🏛 Остаток в казне: <b>{fmt(treasuries[chat_key]['balance'])} TON {EMOJI_GEM}</b>"
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Ошибка отправки сообщения о награде из казны: {e}")


async def chat_member_updated_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if not result:
        return

    chat_id = result.chat.id
    chat_key = str(chat_id)
    if chat_key not in treasuries:
        return

    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status

    if old_status in ("left", "kicked", "restricted") and new_status in ("member", "restricted", "administrator"):
        joined_user = result.new_chat_member.user
        inviter = result.from_user
        if inviter and joined_user:
            await process_invite_reward(chat_id, inviter, [joined_user], context)


async def new_chat_members_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    chat_id = message.chat.id
    chat_key = str(chat_id)
    if chat_key not in treasuries:
        return

    joined_users = message.new_chat_members
    if not joined_users:
        return

    inviter = message.from_user
    if inviter:
        await process_invite_reward(chat_id, inviter, joined_users, context)

# =========================================================
# СТАВКИ И РУЛЕТКА
# =========================================================

async def roulette_batch_bets(update: Update, amount: int, valid_bets: list):
    if not update.message:
        return

    user = update.effective_user
    chat_id = update.effective_chat.id
    user_id = get_user(user)

    if roulette_running.get(chat_id, False):
        await update.message.reply_text("🎰 Рулетка уже крутится.\nДождись результата.")
        return

    if amount <= 0:
        await update.message.reply_text("❌ Ставка должна быть больше 0.")
        return

    chat_key = str(chat_id)
    bets = pending_bets.setdefault(chat_key, [])

    existing_user_bets = sum(1 for b in bets if str(b["user_id"]) == user_id)
    if existing_user_bets + len(valid_bets) > MAX_BETS_PER_GAME:
        await update.message.reply_text(
            f"{EMOJI_NO} Ограничение: не более {MAX_BETS_PER_GAME} ставок на игру от одного игрока!\n"
            f"У вас уже сделано: {existing_user_bets} шт.",
            parse_mode="HTML"
        )
        return

    total_amount = amount * len(valid_bets)

    current_user_bal = int(round(balances[user_id]))
    balances[user_id] = current_user_bal

    if total_amount > current_user_bal:
        await update.message.reply_text(
            f"❌ Недостаточно TON для этой ставки.\n"
            f"Требуется: {fmt(total_amount)} TON\n"
            f"Ваш баланс: {fmt(current_user_bal)} TON "
        )
        return

    now_time = time.time()
    if not bets:
        roulette_ready_time[chat_id] = now_time + BET_WAIT_SECONDS
        roulette_start_time[chat_id] = now_time

    balances[user_id] -= total_amount
    save_balances()
    add_history(user_id, "Расход (Рулетка)", total_amount, f"Ставок поставлено: {len(valid_bets)}")

    raw_user_name = user.first_name or f"Игрок {user.id}"
    username_tag = get_user_link(user_id, raw_user_name)

    placed_lines = []
    for bet_str, (numbers, coefficient, bet_name) in valid_bets:
        bets.append({
            "user_id": user_id,
            "username": username_tag,
            "raw_name": raw_user_name,
            "amount": amount,
            "bet_name": bet_name,
            "numbers": list(numbers),
            "coefficient": coefficient,
            "raw_bet": bet_str
        })
        placed_lines.append(f"{username_tag} — {fmt(amount)} на {bet_name}")

    save_pending_bets() 

    placed_text = "\n".join(placed_lines[:15])
    if len(placed_lines) > 15:
        placed_text += f"\n... и ещё {len(placed_lines) - 15} ставок"

    rem_time = max(1, int(roulette_ready_time.get(chat_id, now_time + BET_WAIT_SECONDS) - now_time))

    await update.message.reply_text(
        f"{EMOJI_OK} <b>Ставки приняты!</b>\n\n"
        f"{placed_text}\n\n"
        f"{EMOJI_MONEY} Списано: {fmt(total_amount)} TON\n"
        f"{EMOJI_TIME} Запуск возможен через {rem_time} сек.",
        parse_mode="HTML"
    )


async def roulette_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat_id = update.effective_chat.id
    user_id = get_user(update.effective_user)

    if roulette_running.get(chat_id, False):
        await update.message.reply_text("❌ Рулетка уже запущена, отмена невозможна!")
        return

    chat_key = str(chat_id)
    bets = pending_bets.get(chat_key, [])
    if not bets:
        await update.message.reply_text("❌ У вас нет активных ставок в этом чате.")
        return

    user_bets = [b for b in bets if str(b["user_id"]) == user_id]
    if not user_bets:
        await update.message.reply_text("❌ У вас нет активных ставок в этом чате.")
        return

    refund_sum = sum(b["amount"] for b in user_bets)
    balances[user_id] += refund_sum
    save_balances()
    add_history(user_id, "Возврат (Рулетка)", refund_sum, "Отмена ставок")

    pending_bets[chat_key] = [b for b in bets if str(b["user_id"]) != user_id]

    if not pending_bets[chat_key]:
        pending_bets.pop(chat_key, None)
        roulette_ready_time.pop(chat_id, None)
        roulette_start_time.pop(chat_id, None)

    save_pending_bets()

    username = get_user_display_name(update.effective_user)
    await update.message.reply_text(
        f"{EMOJI_NO} Ставки {username} отменены!\n"
        f"{EMOJI_MONEY} На баланс возвращено: {fmt(refund_sum)} TON {EMOJI_GEM}\n"
        f"{EMOJI_MONEY} Текущий баланс: {fmt(balances[user_id])} TON {EMOJI_GEM}",
        parse_mode="HTML"
    )


async def roulette_go(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat_id = update.effective_chat.id
    user_id = get_user(update.effective_user)

    if roulette_running.get(chat_id, False):
        await update.message.reply_text("🎰 Рулетка уже крутится.")
        return

    chat_key = str(chat_id)
    bets = pending_bets.get(chat_key, [])
    if not bets:
        await update.message.reply_text("❌ В этом чате нет ставок.")
        return

    has_own_bet = any(str(b["user_id"]) == user_id for b in bets)
    if not has_own_bet:
        await update.message.reply_text("❌ Вы не можете запустить рулетку, пока не сделали свою ставку!")
        return

    now_time = time.time()
    ready_time = roulette_ready_time.get(chat_id)

    if ready_time is not None and now_time < ready_time:
        remaining_seconds = int(ready_time - now_time) + 1
        await update.message.reply_text(
            f"{EMOJI_TIME} <b>Подождите {remaining_seconds} сек. перед запуском рулетки!</b>\n"
            f"Игроки ещё могут сделать или добавить свои ставки.",
            parse_mode="HTML"
        )
        return

    roulette_running[chat_id] = True
    bets = list(pending_bets[chat_key])

    current_round_id = uuid.uuid4().hex[:10]
    user_completed_bets = {}
    for bet_data in bets:
        uid = bet_data["user_id"]
        user_completed_bets.setdefault(uid, []).append({
            "amount": bet_data["amount"],
            "raw_bet": bet_data["raw_bet"]
        })
    round_saved_bets[current_round_id] = user_completed_bets

    if len(round_saved_bets) > 150:
        oldest_key = next(iter(round_saved_bets))
        round_saved_bets.pop(oldest_key, None)

    animation_msg = None

    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        video_filename = None
        for cand in ["red-1.mp4", "roulette.mp4", "roulette.gif"]:
            full_path = os.path.join(base_dir, cand)
            if os.path.exists(full_path):
                video_filename = full_path
                break

        if video_filename:
            try:
                with open(video_filename, "rb") as anim_file:
                    if video_filename.endswith(".gif"):
                        animation_msg = await context.bot.send_animation(
                            chat_id=chat_id,
                            animation=anim_file,
                            caption=f"{EMOJI_RULET} <b>Рулетка крутится...</b>",
                            parse_mode="HTML"
                        )
                    else:
                        animation_msg = await context.bot.send_video(
                            chat_id=chat_id,
                            video=anim_file,
                            caption=f"{EMOJI_RULET} <b>Рулетка крутится...</b>",
                            parse_mode="HTML"
                        )
            except Exception as e:
                print(f"Ошибка отправки видео: {e}")
                animation_msg = await update.message.reply_text("🎡 <b>Рулетка крутится...</b>", parse_mode="HTML")
        else:
            animation_msg = await update.message.reply_text("🎡 <b>Рулетка крутится...</b>", parse_mode="HTML")

        await asyncio.sleep(SPIN_SECONDS)

        if animation_msg:
            try:
                await animation_msg.delete()
            except Exception:
                pass

        result = random.randint(0, 36)
        if random.random() < 0.08:  
            winning_numbers_in_pool = set()
            for b in bets:
                winning_numbers_in_pool.update(b["numbers"])
            
            losing_numbers = [n for n in range(0, 37) if n not in winning_numbers_in_pool]
            if losing_numbers:
                result = random.choice(losing_numbers)

        if result == 0:
            color = "🟢"
            color_name = "Зелёное"
        elif result in RED:
            color = "🔴"
            color_name = "Красное"
        else:
            color = "⚫️"
            color_name = "Чёрное"

        if chat_key not in roulette_log:
            roulette_log[chat_key] = []

        roulette_log[chat_key].append({
            "number": result,
            "color": color_name,
            "timestamp": datetime.now(MSK_TZ).isoformat(timespec="seconds")
        })
        roulette_log[chat_key] = roulette_log[chat_key][-1000:]
        save_log()

        lines = [
            f"{EMOJI_RULET} <b>Рулетка</b>",
            "———————————————",
            f"{EMOJI_VIN} Результат: <b>{result} {color}</b>"
        ]

        for bet_data in bets:
            p_name = get_user_link(bet_data["user_id"], bet_data.get("raw_name") or "Игрок")
            lines.append(f"{p_name} — {fmt(bet_data['amount'])} на {bet_data['bet_name']}")

        lines.append("———————————————")

        winning_bets_lines = []
        round_staked = {}
        round_won = {}
        round_names = {}

        for bet_data in bets:
            b_uid = bet_data["user_id"]
            amount = bet_data["amount"]
            round_staked[b_uid] = round_staked.get(b_uid, 0) + amount
            round_names[b_uid] = bet_data.get("raw_name") or f"Игрок {b_uid}"

            if result in bet_data["numbers"]:
                win = int(round(amount * bet_data["coefficient"]))
                round_won[b_uid] = round_won.get(b_uid, 0) + win
                balances[b_uid] = int(round(balances[b_uid])) + win
                p_name = get_user_link(b_uid, bet_data.get("raw_name") or "Игрок")
                winning_bets_lines.append(
                    f"{EMOJI_VIN} {p_name} — выиграла ставка <b>{bet_data['bet_name']}</b> (+{fmt(win)} TON)"
                )
                record_game_win(b_uid, win)
                net_win = win - amount
                add_game_net_win(b_uid, net_win)
                
                if update.effective_chat.type in ("group", "supergroup"):
                    winner_user_obj = update.effective_user if str(update.effective_user.id) == str(b_uid) else None
                    if winner_user_obj:
                        record_chat_member_activity(chat_id, winner_user_obj, net_win)

                add_history(b_uid, "Доход (Рулетка)", win, f"Ставка на {bet_data['bet_name']} зашла")
            else:
                add_game_loss(b_uid, amount)

        save_balances()

        # Турнир: чистый выигрыш игрока за раунд (выигрыш минус все его ставки)
        for t_uid, t_staked in round_staked.items():
            t_net = round_won.get(t_uid, 0) - t_staked
            if t_net > 0:
                tournament_add_win(t_uid, round_names[t_uid], t_net)

        if winning_bets_lines:
            lines.extend(winning_bets_lines)
        else:
            lines.append(f"{EMOJI_NO} <b>Никто не выиграл!</b>")

        # Бонус: тыквы за крупные ставки
        try:
            for pb_uid, pb_staked in round_staked.items():
                pb_got = pumpkin_roulette_bonus(pb_uid, pb_staked)
                if pb_got:
                    lines.append(
                        f"{EMOJI_PUMPKIN} {get_user_link(pb_uid, round_names[pb_uid])} — бонус <b>+{pb_got}</b> тыкв"
                    )
        except Exception:
            traceback.print_exc()

        keyboard = [
            [
                InlineKeyboardButton("Повторить", callback_data=f"roulette_repeat_{current_round_id}"),
                InlineKeyboardButton("Удвоить", callback_data=f"roulette_double_{current_round_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        full_text = "\n".join(lines)
        
        if len(full_text) > 3500:
            lines_list = full_text.split("\n")
            chunks = []
            current_chunk = ""
            
            for line in lines_list:
                if len(current_chunk) + len(line) + 1 > 3500:
                    chunks.append(current_chunk)
                    current_chunk = line + "\n"
                else:
                    current_chunk += line + "\n"
            if current_chunk:
                chunks.append(current_chunk)
            
            for chunk in chunks[:-1]:
                await update.message.reply_text(chunk.strip(), parse_mode="HTML")
                await asyncio.sleep(0.3)
                
            await update.message.reply_text(chunks[-1].strip(), reply_markup=reply_markup, parse_mode="HTML")
        else:
            await update.message.reply_text(full_text, reply_markup=reply_markup, parse_mode="HTML")

    finally:
        pending_bets.pop(chat_key, None)
        save_pending_bets() 
        roulette_ready_time.pop(chat_id, None)
        roulette_start_time.pop(chat_id, None)
        roulette_running.pop(chat_id, None)


async def roulette_callback(query, user_id, chat_id, round_id, double=False):
    r_bets = round_saved_bets.get(round_id, {})
    saved_bets = r_bets.get(str(user_id))

    if not saved_bets:
        await query.answer("⚠️ В этом раунде у вас не было ставок!", show_alert=True)
        return

    if str(chat_id) in disabled_chats:
        await query.answer("⚠️ Игры в этом чате временно отключены администратором.", show_alert=True)
        return

    if roulette_running.get(chat_id, False):
        await query.answer("🎰 Рулетка уже крутится! Дождитесь следующего раунда.", show_alert=True)
        return

    chat_key = str(chat_id)
    bets = pending_bets.setdefault(chat_key, [])

    existing_user_bets = sum(1 for b in bets if str(b["user_id"]) == str(user_id))
    if existing_user_bets + len(saved_bets) > MAX_BETS_PER_GAME:
        await query.answer(f"{EMOJI_NO} Превышен лимит {MAX_BETS_PER_GAME} ставок за раунд!", show_alert=True)
        return

    multiplier = 2 if double else 1
    total_needed = sum(b["amount"] * multiplier for b in saved_bets)

    user_cur_bal = int(round(balances[user_id]))
    balances[user_id] = user_cur_bal

    if user_cur_bal < total_needed:
        await query.answer(f"❌ Недостаточно TON! Требуется: {fmt(total_needed)} TON", show_alert=True)
        return

    now_time = time.time()
    if not bets:
        roulette_ready_time[chat_id] = now_time + BET_WAIT_SECONDS
        roulette_start_time[chat_id] = now_time

    balances[user_id] -= total_needed
    save_balances()
    add_history(user_id, "Расход (Рулетка)", total_needed, "Повтор ставок")

    user = query.from_user
    raw_user_name = user.first_name or f"Игрок {user.id}"
    username_tag = get_user_link(user_id, raw_user_name)

    placed_lines = []
    for s_bet in saved_bets:
        text_bet_str = s_bet["raw_bet"]
        amount = s_bet["amount"] * multiplier
        parsed = parse_bet(text_bet_str)
        if parsed:
            numbers, coefficient, bet_name = parsed
            bets.append({
                "user_id": user_id,
                "username": username_tag,
                "raw_name": raw_user_name,
                "amount": amount,
                "bet_name": bet_name,
                "numbers": list(numbers),
                "coefficient": coefficient,
                "raw_bet": text_bet_str
            })
            placed_lines.append(f"{username_tag} — {fmt(amount)} на {bet_name}")

    save_pending_bets() 

    action_word = "удвоил" if double else "повторил"
    placed_text = "\n".join(placed_lines[:15])
    if len(placed_lines) > 15:
        placed_text += f"\n... и ещё {len(placed_lines) - 15} ставок"

    rem_time = max(1, int(roulette_ready_time.get(chat_id, now_time + BET_WAIT_SECONDS) - now_time))

    await query.message.reply_text(
        f"{EMOJI_OK} <b>{username_tag} {action_word} ставки!</b>\n\n"
        f"{placed_text}\n\n"
        f"{EMOJI_MONEY} Списано: {fmt(total_needed)} TON\n"
        f"{EMOJI_TIME} Запуск возможен через {rem_time} сек.",
        parse_mode="HTML"
    )
    await query.answer("Ставки продублированы!")

# =========================================================
# ОБРАБОТЧИК КЛИКОВ В МИНАХ
# =========================================================

async def _safe_edit(query, *args, **kwargs):
    """edit_message_text, который не роняет логику игры при сетевых/телеграм-ошибках."""
    try:
        return await query.edit_message_text(*args, **kwargs)
    except Exception as e:
        print(f"[mines] не удалось отредактировать сообщение: {e}")
        return None


async def mines_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    data = query.data
    user_id = str(query.from_user.id)

    if data == "mine_ignore":
        await query.answer()
        return

    if user_id not in active_mines_games:
        await query.answer("⚠️ Это не ваша игра или она уже завершена!", show_alert=True)
        return

    game_data = active_mines_games[user_id]
    game_data["last_action"] = time.time()
    mines_count = game_data.get("mines_count", 3)

    if data == "mine_cancel":
        opened_count = len(game_data["opened"])
        if opened_count > 0:
            await query.answer("Нельзя отменить начатую игру!", show_alert=True)
            return

        bet = game_data["bet"]
        balances[user_id] = int(round(balances[user_id])) + bet
        save_balances()
        add_history(user_id, "Возврат (Мины)", bet, "Отмена игры игроком")

        active_mines_games.pop(user_id, None)

        await _safe_edit(query, 
            f"{EMOJI_NO} Игра в Мины отменена.\n{EMOJI_MONEY} На баланс возвращено: <b>{fmt(bet)} TON</b>\n {EMOJI_MONEY} Баланс: <b>{fmt(balances[user_id])} TON {EMOJI_GEM}</b>",
            parse_mode="HTML"
        )
        await query.answer("Игра отменена, ставка возвращена!")
        return

    if data == "mine_cashout":
        opened_count = len(game_data["opened"])
        if opened_count == 0:
            await query.answer("Откройте ячейку!", show_alert=True)
            return

        active_mines_games.pop(user_id, None)
        mult = get_mines_multiplier(opened_count, mines_count)
        win_amount = int(round(game_data["bet"] * mult))

        balances[user_id] = int(round(balances[user_id])) + win_amount
        save_balances()

        record_game_win(user_id, win_amount)
        net_win = win_amount - game_data["bet"]
        add_game_net_win(user_id, net_win)

        chat_id = query.message.chat.id if query.message and query.message.chat else None
        if chat_id and query.message.chat.type in ("group", "supergroup"):
            record_chat_member_activity(chat_id, query.from_user, net_win)

        add_history(user_id, "Доход (Мины)", win_amount, f"Забрал кэш на x{mult}")

        reply_markup = build_mines_keyboard(game_over=True, won=True, game_data=game_data)

        await _safe_edit(query, 
            f"🎉 <b>ПОБЕДА!</b>\n\n"
            f"💳 Вы забрали: <b>{fmt(win_amount)} TON {EMOJI_GEM}</b> (x{mult})\n"
            f"{EMOJI_MONEY} Ваш баланс: <b>{fmt(balances[user_id])} TON {EMOJI_GEM}</b>",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

        active_mines_games.pop(user_id, None)
        await query.answer("Выигрыш зачислен!")
        return

    if data.startswith("mine_click_"):
        idx = int(data.split("_")[2])

        if idx in game_data["opened"]:
            await query.answer("Ячейка уже открыта!")
            return

        is_hit = (idx in game_data["mines"])

        if not is_hit:
            opened_cnt = len(game_data["opened"])
            trap_chance = 0.05 + (opened_cnt * 0.015)
            if random.random() < trap_chance:
                unopened_mines = [m for m in game_data["mines"] if m not in game_data["opened"]]
                if unopened_mines:
                    old_mine = random.choice(unopened_mines)
                    game_data["mines"].remove(old_mine)
                    game_data["mines"].add(idx)
                    is_hit = True

        if is_hit:
            active_mines_games.pop(user_id, None)
            reply_markup = build_mines_keyboard(game_over=True, won=False, game_data=game_data)

            add_game_loss(user_id, game_data["bet"])

            await _safe_edit(query, 
                f"💥 <b>БУМ! ВЫ ВЗОРВАЛИСЬ НА МИНЕ!</b>\n\n"
                f"💸 Потеряно: <b>{fmt(game_data['bet'])} TON</b>\n"
                f"{EMOJI_MONEY} Ваш баланс: <b>{fmt(balances[user_id])} TON {EMOJI_GEM}</b>",
                reply_markup=reply_markup,
                parse_mode="HTML"
            )

            active_mines_games.pop(user_id, None)
            await query.answer("Бум! Проигрыш 💥")
            return

        game_data["opened"].add(idx)
        opened_count = len(game_data["opened"])
        safe_total = 25 - mines_count

        if opened_count == safe_total:
            active_mines_games.pop(user_id, None)
            mult = get_mines_multiplier(opened_count, mines_count)
            win_amount = int(round(game_data["bet"] * mult))

            balances[user_id] = int(round(balances[user_id])) + win_amount
            save_balances()

            record_game_win(user_id, win_amount)
            net_win = win_amount - game_data["bet"]
            add_game_net_win(user_id, net_win)

            chat_id = query.message.chat.id if query.message and query.message.chat else None
            if chat_id and query.message.chat.type in ("group", "supergroup"):
                record_chat_member_activity(chat_id, query.from_user, net_win)

            add_history(user_id, "Доход (Мины)", win_amount, "Полная зачистка поля!")

            reply_markup = build_mines_keyboard(game_over=True, won=True, game_data=game_data)

            await _safe_edit(query, 
                f"🏆 <b>МЕГА-ПОБЕДА!</b> Вы открыли все безопасные ячейки!\n\n"
                f"🎉 Выигрыш: <b>+{fmt(win_amount)} TON {EMOJI_GEM}</b> (x{mult})\n"
                f"{EMOJI_MONEY} Ваш баланс: <b>{fmt(balances[user_id])} TON {EMOJI_GEM}</b>",
                reply_markup=reply_markup,
                parse_mode="HTML"
            )

            active_mines_games.pop(user_id, None)
            await query.answer("Победа! 🎉")
            return

        mult = get_mines_multiplier(opened_count, mines_count)
        win_amount = int(round(game_data["bet"] * mult))

        reply_markup = build_mines_keyboard(game_data=game_data)

        await _safe_edit(query, 
            f"💣 <b>ИГРА В МИНЫ</b>\n\n"
            f"{EMOJI_MONEY} Ставка: <b>{fmt(game_data['bet'])} TON {EMOJI_GEM}</b> | Мин: {mines_count}\n"
            f"💎 Открыто: {opened_count}/{safe_total}\n"
            f"{EMOJI_UP} Текущий выигрыш: <b>{fmt(win_amount)} TON {EMOJI_GEM}</b> (x{mult})\n\n"
            f"Выберите следующую ячейку или заберите банк!",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        await query.answer("Безопасно! 💎")

# =========================================================
# ГЛАВНЫЙ РОУТЕР ДЛЯ КЛИКОВ (CALLBACK QUERY)
# =========================================================

async def general_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    data = query.data
    user_id = str(query.from_user.id)
    chat_id = update.effective_chat.id if update.effective_chat else query.message.chat.id

    try:
        if data.startswith("mk_"):
            await market_callback(update, context)
            return

        if data == "profile_bank":
            await query.answer()
            await show_bank(update, context)
            return
        if data == "profile_history":
            await query.answer()
            await show_history(update, context)
            return

        if data.startswith("bj_"):
            await blackjack_callback_handler(update, context)
            return

        if data.startswith("tower_"):
            await tower_callback_handler(update, context)
            return

        if data in {"bank_deposit", "bank_withdraw"}:
            await bank_callback(query)
            return

        if data.startswith("treasure_"):
            parts = data.split("_")
            u_id = parts[1]
            box_idx = int(parts[2])
            await treasure_callback_handler(query, u_id, box_idx)
            return

        if data.startswith("donate_"):
            await donate_callback_handler(query, data, context)
            return

        if data.startswith("duel_"):
            await duel_callback_handler(query, data)
            return

        if data.startswith("roulette_repeat_"):
            r_id = data.replace("roulette_repeat_", "")
            await roulette_callback(query, user_id, chat_id, r_id, double=False)
            return
        elif data.startswith("roulette_double_"):
            r_id = data.replace("roulette_double_", "")
            await roulette_callback(query, user_id, chat_id, r_id, double=True)
            return
        elif data == "roulette_repeat" or data == "roulette_double":
            await query.answer("⚠️ Повторите ставку в новом сообщении раунда.", show_alert=True)
            return

        if data == "top_balances":
            text = render_top_balances()
            kb = [[InlineKeyboardButton("🏆 Топ выигрышей", callback_data="top_wins")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
            await query.answer()
            return

        if data == "top_wins":
            text = render_top_wins_for_chat(chat_id)
            kb = [[InlineKeyboardButton("💰 Топ балансов", callback_data="top_balances")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
            await query.answer()
            return

        await mines_callback(update, context)
    except Exception as e:
        print(f"Callback error: {e}")
        try:
            await query.answer("⚠️ Ошибка обработки кнопки.", show_alert=True)
        except:
            pass

# =========================================================
# ЛОГИ
# =========================================================

async def show_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat_id = str(update.effective_chat.id)
    history = roulette_log.get(chat_id, [])

    if not history:
        await update.message.reply_text("📜 Лог пока пуст.")
        return

    last_results = history[-10:]
    lines = []

    for item in reversed(last_results):
        color_name = item.get("color", "")
        if "Зелёное" in color_name:
            icon = "🟢"
        elif "Красное" in color_name:
            icon = "🔴"
        else:
            icon = "⚫️"
        lines.append(f"{icon} {item['number']}")

    await update.message.reply_text(
        "📜 Последние результаты:\n\n" + "\n".join(lines)
    )

# =========================================================
# ПЕРЕДАЧА МОНЕТ (ЧЕРЕЗ Telegram API search/chat members / кэш)
# =========================================================

async def transfer_coins(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int, target_identifier: str = None, comment: str = ""):
    if not update.message:
        return

    if amount <= 0:
        await update.message.reply_text("❌ Сумма должна быть больше 0.")
        return

    sender = update.effective_user
    sender_id = get_user(sender)

    recipient_id = None
    recipient_display = ""

    if update.message.reply_to_message:
        recipient = update.message.reply_to_message.from_user
        if recipient.is_bot:
            await update.message.reply_text("❌ Нельзя переводить TON ботам.")
            return
        recipient_id = get_user(recipient)
        recipient_display = get_user_display_name(recipient)

    elif target_identifier:
        target_identifier = target_identifier.strip()
        found_uid = None

        if target_identifier.startswith("@"):
            search_username = target_identifier.lstrip("@").strip().strip(".,!?;:").lower()

            # 1. Ищем в базе юзеров бота (точное совпадение юзернейма)
            for uid, data in user_stats.items():
                if (data.get("username") or "").lower() == search_username:
                    found_uid = uid
                    break

            # 2. Если в базе нет — пробуем спросить Telegram
            if not found_uid and search_username:
                try:
                    tg_chat = await context.bot.get_chat(f"@{search_username}")
                    if tg_chat.type == "private" and not getattr(tg_chat, "is_bot", False):
                        found_uid = str(tg_chat.id)
                        if found_uid not in user_stats:
                            user_stats[found_uid] = {
                                "name": get_user_link(found_uid, tg_chat.first_name or f"Игрок {found_uid}"),
                                "username": search_username,
                                "win": 0,
                            }
                            save_stats()
                except Exception:
                    pass

            if not found_uid:
                await update.message.reply_text(
                    f"❌ Игрок {target_identifier} не найден в базе данных бота!\n"
                    f"Игрок должен хотя бы раз написать любое сообщение в чате с ботом, чтобы бот запомнил его ID."
                )
                return

            recipient_id = found_uid
            # Берем актуальное имя/ссылку на найденный ID
            saved_name = user_stats.get(recipient_id, {}).get("name")
            if saved_name:
                recipient_display = saved_name
            else:
                recipient_display = f'<a href="tg://user?id={recipient_id}">Игрок {recipient_id}</a>'

        else:
            clean_id = target_identifier.replace("'", "").replace('"', "")
            if clean_id.isdigit() and clean_id in balances:
                recipient_id = clean_id
                recipient_display = user_stats.get(recipient_id, {}).get("name", f'<a href="tg://user?id={recipient_id}">Игрок {recipient_id}</a>')
            else:
                await update.message.reply_text("❌ Неверный формат ID или юзернейма.")
                return

    else:
        await update.message.reply_text(
            "❌ Используй команду одним из способов:\n"
            "• По юзернейму: <code>д 2000 @miki</code>\n"
            "• Ответом на сообщение: <code>д 2000</code>\n"
            "• По ID: <code>д 2000 123456789</code>",
            parse_mode="HTML"
        )
        return

    if sender_id == recipient_id:
        await update.message.reply_text("❌ Нельзя передать TON самому себе.")
        return

    if int(round(balances[sender_id])) < amount:
        await update.message.reply_text(
            f"❌ Недостаточно TON.\nТвой баланс: {fmt(balances[sender_id])} TON"
        )
        return

    balances[sender_id] -= amount
    balances[recipient_id] = int(round(float(balances.get(recipient_id, START_BALANCE)))) + amount
    save_balances()

    history_details_sender = f"Перевод игроку {recipient_display}"
    history_details_recipient = f"Получено от {get_user_display_name(sender)}"
    if comment:
        history_details_sender += f" | {comment}"
        history_details_recipient += f" | {comment}"

    add_history(sender_id, "Расход (Перевод)", amount, history_details_sender)
    add_history(recipient_id, "Доход (Перевод)", amount, history_details_recipient)

    reply_text = (
        f"{EMOJI_PAY} Передано: <b>{fmt(amount)} TON {EMOJI_GEM}</b>\n"
        f"{EMOJI_PLAYER} Получатель: {recipient_display}"
    )

    if comment:
        safe_comment = comment.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        reply_text += f"<blockquote><i>{safe_comment}</i></blockquote>"

    await update.message.reply_text(reply_text, parse_mode="HTML")


async def give_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user = update.effective_user
    if user.id != OWNER_ID:
        await update.message.reply_text("")
        return

    if update.message.reply_to_message:
        if len(context.args) < 1:
            await update.message.reply_text("❌ Укажите сумму: /give [сумма]")
            return
        try:
            amount = int(context.args[0].replace(" ", ""))
        except ValueError:
            await update.message.reply_text("❌ Сумма должна быть целым числом.")
            return

        target_user = update.message.reply_to_message.from_user
        target_id = get_user(target_user)
        balances[target_id] = int(round(balances.get(target_id, START_BALANCE))) + amount
        save_balances()
        add_history(target_id, "Доход (Админ)", amount, "Выдача валюты владельцем")

        await update.message.reply_text(
            f"✅ Игроку {get_user_display_name(target_user)} успешно выдано <b>{fmt(amount)} TON {EMOJI_GEM}</b>!",
            parse_mode="HTML"
        )
        return

    if len(context.args) < 1:
        await update.message.reply_text("❌ Пример: /give 100000 или реплаем на сообщение игрока.")
        return

    try:
        amount = int(context.args[0].replace(" ", ""))
    except ValueError:
        await update.message.reply_text("❌ Сумма должна быть целым числом.")
        return

    owner_id_str = get_user(user)
    balances[owner_id_str] = int(round(balances.get(owner_id_str, START_BALANCE))) + amount
    save_balances()
    add_history(owner_id_str, "Доход (Админ)", amount, "Самовыдача валюты владельцем")

    await update.message.reply_text(
        f"✅ Вам (владельцу) успешно начислено <b>{fmt(amount)} TON {EMOJI_GEM}</b>!\n"
        f"Новый баланс: <b>{fmt(balances[owner_id_str])} TON {EMOJI_GEM}</b>",
        parse_mode="HTML"
    )

# =========================================================
# РАССЫЛКА ВЛАДЕЛЬЦА (ФОНОВАЯ)
# =========================================================

async def background_mailing(bot: Bot, owner_chat_id: int, status_msg_id: int, text_to_send: str, users_list: list):
    success_count = 0
    fail_count = 0

    for uid in users_list:
        try:
            await bot.send_message(
                chat_id=int(uid),
                text=text_to_send,
                parse_mode="HTML"
            )
            success_count += 1
            await asyncio.sleep(0.05)
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
            try:
                await bot.send_message(
                    chat_id=int(uid),
                    text=text_to_send,
                    parse_mode="HTML"
                )
                success_count += 1
            except Exception:
                fail_count += 1
        except Exception:
            fail_count += 1

    try:
        await bot.edit_message_text(
            chat_id=owner_chat_id,
            message_id=status_msg_id,
            text=(
                f"✅ <b>Рассылка завершена!</b>\n\n"
                f"📤 Успешно отправлено: <b>{success_count}</b>\n"
                f"❌ Ошибок (заблокировали бота): <b>{fail_count}</b>"
            ),
            parse_mode="HTML"
        )
    except Exception:
        try:
            await bot.send_message(
                chat_id=owner_chat_id,
                text=(
                    f"✅ <b>Рассылка завершена!</b>\n\n"
                    f"📤 Успешно отправлено: <b>{success_count}</b>\n"
                    f"❌ Ошибок (заблокировали бота): <b>{fail_count}</b>"
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass


async def mailing_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user = update.effective_user
    if user.id != OWNER_ID:
        await update.message.reply_text("❌ Эта команда доступна только владельцу бота.")
        return

    text_to_send = ""
    if update.message.text.startswith("/mailing"):
        text_to_send = update.message.text[len("/mailing"):].strip()
    else:
        parts = update.message.text.split(maxsplit=1)
        if len(parts) > 1:
            text_to_send = parts[1].strip()

    if not text_to_send:
        await update.message.reply_text("❌ Укажите текст для рассылки!\nПример: /mailing Внимание, обновление!")
        return

    all_users = list(balances.keys())

    status_msg = await update.message.reply_text(
        f"📢 <b>Рассылка запущена в фоновом режиме!</b>\n\n"
        f"👥 Получателей: <b>{len(all_users)}</b>\n"
        f"⚡️ Бот продолжает работать и отвечать игрокам без задержек.",
        parse_mode="HTML"
    )

    asyncio.create_task(
        background_mailing(
            bot=context.bot,
            owner_chat_id=update.effective_chat.id,
            status_msg_id=status_msg.message_id,
            text_to_send=text_to_send,
            users_list=all_users
        )
    )

# =========================================================
# ОБРАБОТКА ТЕКСТА
# =========================================================

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global duel_id_counter
    if not update.message or not update.message.text:
        return

    msg_date = update.message.date
    if msg_date:
        msg_timestamp = msg_date.timestamp()
        if (msg_timestamp < BOT_START_TIME) and (time.time() - msg_timestamp > 15):
            return  

    text = update.message.text.strip()
    lower = text.lower()
    user_id = str(update.effective_user.id)

    if not update.effective_user.is_bot:
        get_user(update.effective_user)

    if update.effective_chat.type in ("group", "supergroup"):
        record_chat_member_activity(update.effective_chat.id, update.effective_user)

    if await process_bank_amount(update, text):
        return

    if waiting_for_custom_stars.get(user_id):
        waiting_for_custom_stars.pop(user_id, None)
        try:
            stars_count = int(text.replace(" ", ""))
            await create_stars_invoice(update.message, context, stars_count)
            return
        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите корректное число звёзд (например: 300).")
            return

    # КОМАНДА «БОТ» (ПРОВЕРКА ПИНГА)
    if lower == "бот":
        start_time = time.time()
        sent_msg = await update.message.reply_text("⏳")
        ping_ms = int((time.time() - start_time) * 1000)
        await sent_msg.edit_text(
            f"{EMOJI_BOT} <b>На месте!</b>\nPing: <code>{ping_ms} ms</code>",
            parse_mode="HTML"
        )
        return

    if text == "🎁 Забрать бонус":
        await bonus_command(update, context)
        return
    if text == "🎮 Игры":
        await show_games_help(update, context)
        return
    if text == "📜 Команды":
        await show_commands_help(update, context)
        return
    if text == "⭐️ Донат":
        await show_donate_menu(update, context)
        return
    if text == "👤 Профиль":
        await show_profile(update, context)
        return
    if text == "🏦 Банк":
        await show_bank(update, context)
        return
    if text in {"💬 Чаты", "Чаты"}:
        await show_community_chats(update, context)
        return
    if text == "🏆 Турниры" or lower in {"турнир", "турниры", "/турнир", "/турниры", "/tournament"}:
        await show_tournament(update, context)
        return

    if lower == "-game":
        chat = update.effective_chat
        if chat.type == "private":
            await update.message.reply_text("❌ Эту команду можно использовать только в группах!")
            return
        
        user = update.effective_user
        is_authorized = False
        if user.id == OWNER_ID:
            is_authorized = True
        else:
            try:
                member = await chat.get_member(user.id)
                if member.status in ("administrator", "creator"):
                    is_authorized = True
            except Exception as e:
                print(f"Ошибка проверки прав: {e}")
        
        if not is_authorized:
            await update.message.reply_text("❌ Только администраторы или создатель группы могут использовать эту команду!")
            return
        
        chat_id_str = str(chat.id)
        if chat_id_str in disabled_chats:
            disabled_chats.remove(chat_id_str)
            save_json(DISABLED_CHATS_FILE, disabled_chats)
            await update.message.reply_text("🎮 <b>Игры в этом чате успешно включены!</b>", parse_mode="HTML")
        else:
            disabled_chats.append(chat_id_str)
            save_json(DISABLED_CHATS_FILE, disabled_chats)
            await update.message.reply_text("🚫 <b>Игры в этом чате отключены администрацией!</b>", parse_mode="HTML")
        return

    is_group_chat = update.effective_chat.type in ("group", "supergroup")
    chat_id_str = str(update.effective_chat.id)
    games_blocked = is_group_chat and (chat_id_str in disabled_chats)

    if await pumpkin_text_router(update, context, text, lower):
        return

    if lower in {"бонус", "подарок", "/бонус", "/bonus"}:
        await bonus_command(update, context)
        return
    elif lower in {"игры", "игра", "games", "game", "/игры", "/games"}:
        await show_games_help(update, context)
        return
    elif lower in {"команды", "команда", "help", "/команды", "/help", "справка"}:
        await show_commands_help(update, context)
        return
    elif lower in {"донат", "donate", "/донат", "звезды", "звёзды"}:
        await show_donate_menu(update, context)
        return
    elif lower in {"профиль", "/профиль", "кабинет", "/кабинет"}:
        await show_profile(update, context)
        return

    if lower in {"чаты", "чат", "/чаты", "/chats", "сообщества"}:
        await show_community_chats(update, context)
        return

    if lower in {"баланс", "б", "/баланс", "/б"}:
        await show_balance(update, context)
        return

    if lower in {"банк", "/банк"}:
        await show_bank(update, context)
        return

    if lower in {"история", "/история"}:
        await show_history(update, context)
        return

    if lower in {"ставки", "мои ставки", "/ставки"}:
        await show_my_bets(update, context)
        return

    if lower in {"топ", "/топ", "top", "/top"}:
        await show_top_menu(update, context)
        return

    if lower in {"логи", "/логи", "логи рулетки", "/логи рулетки", "/лог"}:
        await show_log(update, context)
        return

    if lower.startswith("рассылка ") or lower.startswith("/mailing "):
        await mailing_command(update, context)
        return

    parts = text.split()

    is_game_trigger = False
    if lower.startswith("кубы") or lower.startswith("клад") or \
       lower.startswith("блекджек") or lower.startswith("бд") or lower.startswith("blackjack") or lower.startswith("bj") or \
       lower.startswith("слот") or lower.startswith("слоты") or \
       lower.startswith("кто дуэль") or lower.startswith("дуэль") or lower.startswith("/дуэль") or \
       lower.startswith("мины") or lower.startswith("башня") or \
       lower in {"гоу", "отмена"}:
        is_game_trigger = True
    elif len(parts) >= 3 and parts[0].lower() in {"р", "p", "r"}:
        try:
            _ = int(parts[1].replace(" ", ""))
            if parse_bet(parts[2]) is not None:
                is_game_trigger = True
        except ValueError:
            pass

    if is_game_trigger and games_blocked:
        await update.message.reply_text("⚠️ <b>Игры в этом чате временно отключены администратором!</b>", parse_mode="HTML")
        return

    if lower.startswith("кубы"):
        await handle_dice_command(update, context)
        return

    if lower.startswith("клад"):
        await handle_treasure_command(update, context)
        return

    if lower.startswith("башня"):
        await handle_tower_command(update, context)
        return

    if lower.startswith("блекджек") or lower.startswith("бд") or lower.startswith("blackjack") or lower.startswith("bj"):
        await handle_blackjack_command(update, context)
        return

    if lower.startswith("слот") or lower.startswith("слоты"):
        await handle_slot_command(update, context)
        return

    if lower.startswith("кто дуэль"):
        if len(parts) < 3:
            await update.message.reply_text(
                "❌ Укажите ставку открытой дуэли:\nПример: <code>Кто дуэль 5000</code>",
                parse_mode="HTML"
            )
            return

        try:
            amount = int(parts[2].replace(" ", ""))
        except ValueError:
            await update.message.reply_text("❌ Ставка должна быть целым числом.")
            return

        if amount <= 0:
            await update.message.reply_text("❌ Ставка должна быть больше 0.")
            return

        challenger = update.effective_user
        c_id = get_user(challenger)
        c_bal = int(round(balances[c_id]))

        if c_bal < amount:
            await update.message.reply_text(
                f"{EMOJI_GEM} У вас недостаточно TON для этой дуэли!\nВаш баланс: <b>{fmt(c_bal)} TON {EMOJI_GEM}</b>",
                parse_mode="HTML"
            )
            return

        duel_id = duel_id_counter
        duel_id_counter += 1

        win_amount = int(round(amount * DUEL_MULTIPLIER))
        c_name = get_user_display_name(challenger)

        keyboard = [
            [
                InlineKeyboardButton("🎯 Принять вызов", callback_data=f"duel_accept_open_{duel_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"duel_decline_open_{duel_id}")
            ]
        ]

        msg = await update.message.reply_text(
            f"⚔️ <b>ОТКРЫТЫЙ ВЫЗОВ НА ДУЭЛЬ!</b>\n\n"
            f"🤠 {c_name} предлагает сыграть в дуэль всем желающим!\n"
            f"{EMOJI_MONEY} Ставка: <b>{fmt(amount)} TON {EMOJI_GEM}</b>\n"
            f"🏆 Победитель заберёт: <b>{fmt(win_amount)} TON {EMOJI_GEM}</b> (x{int(DUEL_MULTIPLIER)})\n\n"
            f"{EMOJI_LOW} Нажмите кнопку ниже, чтобы принять вызов (у вас есть 1 минута):",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        open_duels[duel_id] = {
            "chat_id": update.effective_chat.id,
            "challenger_id": c_id,
            "challenger_name": c_name,
            "amount": amount,
            "win_amount": win_amount,
            "created_at": time.time(),
            "message_id": msg.message_id
        }
        return

    if lower.startswith("дуэль") or lower.startswith("/дуэль"):
        await handle_duel_command(update, context)
        return

    if lower == "гоу":
        await roulette_go(update, context)
        return

    if lower == "отмена":
        await roulette_cancel(update, context)
        return

    if lower == "купить казну":
        await buy_treasury(update, context)
        return

    if lower in {"казна", "/казна"}:
        await show_treasury_status(update, context)
        return

    if lower.startswith("пополнить казну"):
        if len(parts) >= 3:
            raw_sum = parts[2].replace(" ", "")
            try:
                amount = int(raw_sum)
                await deposit_treasury(update, amount)
                return
            except ValueError:
                await update.message.reply_text("❌ Пример использования: <code>Пополнить казну 5000</code>", parse_mode="HTML")
                return
        else:
            await update.message.reply_text("❌ Укажите сумму: <code>Пополнить казну 5000</code>", parse_mode="HTML")
            return

    # МИНЫ (ОТ 3 ДО 24 МИН)
    if lower.startswith("мины"):
        if len(parts) < 2:
            await update.message.reply_text(
                "❌ Пример команды: <code>мины 100</code> или <code>мины 100 10</code>\n"
                "ℹ️ Количество мин можно выбрать от 3 до 24 (по умолчанию: 3).",
                parse_mode="HTML"
            )
            return

        try:
            bet = int(parts[1].replace(" ", ""))
        except ValueError:
            await update.message.reply_text("❌ Ставка должна быть числом.")
            return

        mines_count = 3
        if len(parts) >= 3:
            try:
                mines_count = int(parts[2].replace(" ", ""))
            except ValueError:
                await update.message.reply_text("❌ Количество мин должно быть числом от 3 до 24.")
                return

        if not (3 <= mines_count <= 24):
            await update.message.reply_text("❌ Количество мин должно быть от 3 до 24.")
            return

        user_id_obj = get_user(update.effective_user)

        if user_id_obj in active_mines_games:
            await update.message.reply_text("⚠️ У вас уже есть активная игра в Мины!")
            return

        if bet <= 0:
            await update.message.reply_text("❌ Ставка должна быть больше 0.")
            return

        if int(round(balances[user_id_obj])) < bet:
            await update.message.reply_text(
                f"Недостаточно TON на балансе.\nТвой баланс: {fmt(balances[user_id_obj])} TON"
            )
            return

        balances[user_id_obj] -= bet
        save_balances()
        add_history(user_id_obj, "Расход (Мины)", bet, f"Игра в мины ({mines_count} мин)")

        mine_positions = set(random.sample(range(25), mines_count))

        game_data = {
            "bet": bet,
            "mines_count": mines_count,
            "mines": mine_positions,
            "opened": set(),
            "chat_id": update.effective_chat.id,
            "user_id": user_id_obj,
            "raw_name": update.effective_user.first_name or f"Игрок {user_id_obj}",
            "last_action": time.time(),
            "chat_type": update.effective_chat.type,
            "user_obj": update.effective_user
        }

        active_mines_games[user_id_obj] = game_data
        reply_markup = build_mines_keyboard(game_data)

        await update.message.reply_text(
            f"💣 <b>ИГРА В МИНЫ</b>\n\n"
            f"{EMOJI_MONEY} Ставка: <b>{fmt(bet)} TON {EMOJI_GEM}</b> | Мин: {mines_count}\n"
            f"💎 Выберите ячейку (или нажмите ❌ Отменить игру):",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        return

    # Промокоды
    if len(parts) == 5 and parts[0].lower() == "создать" and parts[1].lower() == "промокод":
        if update.effective_user.id != OWNER_ID:
            await update.message.reply_text("❌ Только владелец бота может генерировать промокоды.")
            return

        code = parts[2].lstrip("#").lower()

        try:
            reward = int(parts[3].replace(" ", ""))
            limit = int(parts[4].replace(" ", ""))
        except ValueError:
            await update.message.reply_text("Формат: Создать промокод #код сумма количество")
            return

        if not code or reward <= 0 or limit <= 0:
            await update.message.reply_text("❌ Сумма и количество должны быть больше 0.")
            return

        if code in promos:
            await update.message.reply_text("❌ Промокод с таким названием уже активен.")
            return

        promos[code] = {"reward": reward, "limit": limit, "used": 0}
        promo_uses[code] = []
        save_promos()
        save_promo_uses()

        await update.message.reply_text(
            f"✅ <b>Промокод #{code} успешно создан!</b>\n\n"
            f"🎁 Награда: <b>+{fmt(reward)} TON</b>\n"
            f"👥 Макс. активаций: <b>{limit}</b>",
            parse_mode="HTML"
        )
        return

    if len(parts) == 1 and parts[0].startswith("#"):
        code = parts[0].lstrip("#").lower()
        user_id_p = get_user(update.effective_user)

        promo = promos.get(code)
        if not promo:
            await update.message.reply_text("❌ Такого промокода не существует.")
            return

        used_by = promo_uses.setdefault(code, [])
        if user_id_p in used_by:
            await update.message.reply_text("❌ Вы уже активировали этот промокод!")
            return

        if promo["used"] >= promo["limit"]:
            await update.message.reply_text("❌ Данный промокод больше не действителен (лимит превышен).")
            return

        balances[user_id_p] = int(balances.get(user_id_p, START_BALANCE)) + int(promo["reward"])
        promo["used"] += 1
        used_by.append(user_id_p)

        save_balances()
        save_promos()
        save_promo_uses()
        add_history(user_id_p, "Доход (Промокод)", promo["reward"], f"Активация #{code}")

        await update.message.reply_text(
            f"🎉 <b>Успешно!</b>\n"
            f"Начислено: <b>+{fmt(promo['reward'])} TON {EMOJI_GEM}</b>\n"
            f"{EMOJI_MONEY} Твой баланс: <b>{fmt(balances[user_id_p])} TON {EMOJI_GEM}</b>",
            parse_mode="HTML"
        )
        return

    # Перевод монет с поддержкой комментария
    if len(parts) >= 2 and parts[0].lower() in {"д", "/д", "дать", "/дать"}:
        try:
            amount = int(parts[1].replace(" ", ""))
        except ValueError:
            await update.message.reply_text("❌ Сумма должна быть числом.")
            return

        target = None
        comment_parts = []

        if update.message.reply_to_message:
            if len(parts) >= 3:
                comment_parts = parts[2:]
        else:
            if len(parts) >= 3:
                target = parts[2]
                if len(parts) >= 4:
                    comment_parts = parts[3:]

        comment = " ".join(comment_parts).strip()
        await transfer_coins(update, context, amount, target, comment)
        return

    # ОПРЕДЕЛЕНИЕ СТАВКИ РУЛЕТКИ (р / p / r)
    if len(parts) >= 3 and parts[0].lower() in {"р", "p", "r"}:
        try:
            amount = int(parts[1].replace(" ", ""))
            valid_bets = []
            for bet_str in parts[2:]:
                parsed = parse_bet(bet_str)
                if parsed is not None:
                    valid_bets.append((bet_str, parsed))

            if valid_bets:
                await roulette_batch_bets(update, amount, valid_bets)
                return
        except ValueError:
            pass

# =========================================================
# БОНУС
# =========================================================

async def bonus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "🎁 Бонус можно забрать только в личных сообщениях с ботом!\n"
            "Напиши мне в ЛС: /start"
        )
        return

    user_id = get_user(update.effective_user)

    now = time.time()
    last_bonus = bonus_times.get(user_id, 0)

    cooldown = 24 * 60 * 60
    remaining = cooldown - (now - last_bonus)

    if remaining > 0:
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        await update.message.reply_text(
            f"Бонус уже получен.\n"
            f"Следующий бонус через: {hours} ч. {minutes} мин."
        )
        return

    bonus = 2000
    balances[user_id] += bonus
    bonus_times[user_id] = now
    save_balances()
    save_bonus_times()
    add_history(user_id, "Бонус", bonus, "Ежедневный бонус")

    await update.message.reply_text(
        f"🎁 Бонус начислен: <b>+{fmt(bonus)} TON {EMOJI_GEM}</b>\n"
        f"{EMOJI_MONEY} Твой баланс: <b>{fmt(balances[user_id])} TON {EMOJI_GEM}</b>",
        parse_mode="HTML"
    )


# =========================================================
# БИРЖА ТЫКВ
# =========================================================

PUMPKIN_TOTAL = 5_000_000            # всего тыкв в игре
PUMPKIN_MIN_STOCK = 10_000           # столько тыкв всегда остаётся на бирже
PUMPKIN_START_PRICE = (13_000, 15_000)  # стартовая цена за 1 тыкву (случайно в диапазоне)
PUMPKIN_TICK_SECONDS = 300           # как часто цена "дышит" (колебания рынка)
PUMPKIN_HISTORY_LIMIT = 600          # сколько точек истории хранить
PUMPKIN_CHART_HOURS = 24             # период графика
PUMPKIN_MAX_ALERTS = 3               # лимит уведомлений о цене на игрока

# Бонус из рулетки: (сумма ставок игрока за раунд от, шанс в %). Падает 1-5 тыкв.
PUMPKIN_BONUS_TIERS = [(10_000, 1), (50_000, 3), (200_000, 5)]
PUMPKIN_BONUS_RANGE = (1, 5)

# События рынка (раз в 18-30 часов, длятся 2 часа)
PUMPKIN_EVENTS = [
    {"name": "Тыквенный сезон", "text": "Урожай удался, цена падает", "mult": 0.80},
    {"name": "Дефицит", "text": "Тыкв не хватает, цена растёт", "mult": 1.30},
    {"name": "Ажиотаж", "text": "Все скупают тыквы", "mult": 1.15},
    {"name": "Распродажа", "text": "Склады чистят, цена ниже", "mult": 0.88},
]
PUMPKIN_EVENT_DURATION = 2 * 3600
PUMPKIN_EVENT_GAP = (18 * 3600, 30 * 3600)

PUMPKIN_MARKET_FILE = "pumpkin_market.json"
PUMPKIN_BALANCES_FILE = "pumpkin_balances.json"

pumpkin_market = load_json(PUMPKIN_MARKET_FILE, {})
pumpkin_balances = load_json(PUMPKIN_BALANCES_FILE, {})


# ---------- данные и цена ----------

def pumpkin_save_market():
    save_json(PUMPKIN_MARKET_FILE, pumpkin_market)


def pumpkin_get(user_id) -> int:
    return int(pumpkin_balances.get(str(user_id), 0))


def pumpkin_add(user_id, n: int):
    uid = str(user_id)
    value = int(pumpkin_balances.get(uid, 0)) + int(n)
    if value <= 0:
        pumpkin_balances.pop(uid, None)
    else:
        pumpkin_balances[uid] = value
    save_json(PUMPKIN_BALANCES_FILE, pumpkin_balances)


def pumpkin_event_active():
    ev = pumpkin_market.get("event")
    if ev and time.time() < ev.get("until", 0):
        return ev
    return None


def pumpkin_k() -> float:
    """Цена = k / остаток. Чем меньше тыкв на бирже, тем дороже."""
    m = pumpkin_market
    ev = pumpkin_event_active()
    return m["base"] * m["mood"] * (ev["mult"] if ev else 1.0) * PUMPKIN_TOTAL


def pumpkin_price() -> float:
    return pumpkin_k() / max(pumpkin_market["stock"], PUMPKIN_MIN_STOCK)


def pumpkin_buy_cost(n: int) -> int:
    # Цена считается по кривой (интеграл), поэтому купить и сразу продать нельзя в плюс.
    s = pumpkin_market["stock"]
    return max(1, math.ceil(pumpkin_k() * math.log(s / (s - n))))


def pumpkin_sell_value(n: int) -> int:
    s = pumpkin_market["stock"]
    return max(0, math.floor(pumpkin_k() * math.log((s + n) / s)))


def pumpkin_max_affordable(balance: int) -> int:
    s = pumpkin_market["stock"]
    n = int(s * (1 - math.exp(-balance / pumpkin_k())))
    n = min(n, s - PUMPKIN_MIN_STOCK)
    while n > 0 and pumpkin_buy_cost(n) > balance:
        n -= 1
    return max(n, 0)


def pumpkin_record_price():
    m = pumpkin_market
    now = time.time()
    point = [now, round(pumpkin_price(), 2)]
    hist = m["history"]
    if hist and now - hist[-1][0] < 60:
        hist[-1] = point
    else:
        hist.append(point)
    m["history"] = hist[-PUMPKIN_HISTORY_LIMIT:]
    pumpkin_save_market()


def _pumpkin_init():
    m = pumpkin_market
    if "base" not in m:
        m["base"] = random.randint(*PUMPKIN_START_PRICE)
    m.setdefault("stock", PUMPKIN_TOTAL - sum(int(v) for v in pumpkin_balances.values()))
    m.setdefault("mood", 1.0)
    m.setdefault("event", None)
    m.setdefault("next_event", time.time() + random.randint(*PUMPKIN_EVENT_GAP))
    m.setdefault("history", [])
    m.setdefault("alerts", {})
    m.setdefault("notify", [])
    if not m["history"]:
        m["history"].append([time.time(), round(pumpkin_price(), 2)])
    pumpkin_save_market()


_pumpkin_init()


def pumpkin_parse_count(raw):
    """Число, 'all' или None."""
    raw = (raw or "").strip().lower()
    if raw in {"все", "всё", "all"}:
        return "all"
    try:
        n = int(raw.replace(" ", ""))
    except ValueError:
        return None
    return n if n > 0 else None


def pumpkin_parse_price(raw):
    raw = (raw or "").strip().lower().replace(",", ".").replace(" ", "")
    mult = 1
    if raw.endswith(("к", "k")):
        mult = 1000
        raw = raw[:-1]
    try:
        value = float(raw) * mult
    except ValueError:
        return None
    return int(value) if value > 0 else None


# ---------- бонус из рулетки ----------

def pumpkin_roulette_bonus(user_id, staked: int) -> int:
    chance = 0
    for limit, ch in PUMPKIN_BONUS_TIERS:
        if staked >= limit:
            chance = ch
    if chance <= 0 or random.random() * 100 >= chance:
        return 0
    available = pumpkin_market["stock"] - PUMPKIN_MIN_STOCK
    if available < 1:
        return 0
    n = min(random.randint(*PUMPKIN_BONUS_RANGE), available)
    pumpkin_market["stock"] -= n
    pumpkin_add(user_id, n)
    pumpkin_record_price()
    return n


# ---------- график ----------

def pumpkin_render_chart() -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    m = pumpkin_market
    now = time.time()
    price_now = pumpkin_price()

    pts = [p for p in m["history"] if now - p[0] <= PUMPKIN_CHART_HOURS * 3600]
    pts = pts + [[now, price_now]]
    if len(pts) < 2:
        pts = [[now - 60, price_now]] + pts

    times = [datetime.fromtimestamp(p[0], MSK_TZ) for p in pts]
    prices = [p[1] for p in pts]
    first, hi, lo = prices[0], max(prices), min(prices)
    change = (price_now - first) / first * 100 if first else 0.0
    up = change >= 0
    color = "#2ecc71" if up else "#e74c3c"
    bg, fg, grey = "#12141a", "#ffffff", "#8b93a7"

    fig = plt.figure(figsize=(9, 6), dpi=130, facecolor=bg)

    fig.text(0.05, 0.93, "ТЫКВЕННАЯ БИРЖА", color=grey, fontsize=12, weight="bold")
    fig.text(0.05, 0.84, f"{fmt(price_now)} TON", color=fg, fontsize=30, weight="bold")
    arrow = "▲" if up else "▼"
    fig.text(0.05, 0.775, f"{arrow} {change:+.2f}% за {PUMPKIN_CHART_HOURS} ч", color=color, fontsize=13)
    fig.text(0.95, 0.84, f"Макс  {fmt(hi)}", color="#2ecc71", fontsize=11, ha="right")
    fig.text(0.95, 0.80, f"Мин   {fmt(lo)}", color="#e74c3c", fontsize=11, ha="right")

    ev = pumpkin_event_active()
    if ev:
        fig.text(0.95, 0.93, f"Событие: {ev['name']} (x{ev['mult']})", color="#f39c12",
                 fontsize=11, ha="right", weight="bold")

    ax = fig.add_axes([0.10, 0.24, 0.86, 0.45], facecolor=bg)
    ax.plot(times, prices, color=color, linewidth=2.2)
    ax.fill_between(times, prices, min(prices), color=color, alpha=0.13)

    i_hi, i_lo = prices.index(hi), prices.index(lo)
    ax.scatter([times[i_hi]], [hi], color="#2ecc71", s=34, zorder=5)
    ax.scatter([times[i_lo]], [lo], color="#e74c3c", s=34, zorder=5)
    ax.scatter([times[-1]], [prices[-1]], color=fg, s=40, zorder=6)

    span = hi - lo
    pad = span * 0.18 if span > 0 else hi * 0.01
    ax.set_ylim(lo - pad, hi + pad)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=MSK_TZ))
    ax.tick_params(colors=grey, labelsize=9)
    ax.grid(color="#262a36", linewidth=0.8)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)

    stock = m["stock"]
    pct = stock / PUMPKIN_TOTAL * 100
    fig.text(0.05, 0.145, f"Осталось на бирже: {fmt(stock)} из {fmt(PUMPKIN_TOTAL)} тыкв ({pct:.2f}%)",
             color=grey, fontsize=11)
    bar = fig.add_axes([0.05, 0.07, 0.90, 0.045], facecolor="#262a36")
    bar.barh([0], [pct], color="#f39c12", height=1)
    bar.set_xlim(0, 100)
    bar.set_ylim(-0.5, 0.5)
    bar.set_xticks([])
    bar.set_yticks([])
    for side in bar.spines.values():
        side.set_visible(False)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=bg)
    plt.close(fig)
    return buf.getvalue()


# ---------- события, уведомления, фоновая задача ----------

async def pumpkin_check_alerts(bot):
    price = pumpkin_price()
    alerts = pumpkin_market.get("alerts", {})
    changed = False
    for uid in list(alerts.keys()):
        keep = []
        for a in alerts[uid]:
            going_up = a["dir"] == "up"
            hit = price >= a["price"] if going_up else price <= a["price"]
            if not hit:
                keep.append(a)
                continue
            changed = True
            try:
                await bot.send_message(
                    chat_id=int(uid),
                    text=(
                        f"🔔 {EMOJI_PUMPKIN} Тыква {'выросла' if going_up else 'упала'} до "
                        f"<b>{fmt(price)} TON</b>\nВаш уровень: {fmt(a['price'])} TON"
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass
        if keep:
            alerts[uid] = keep
        else:
            alerts.pop(uid, None)
    if changed:
        pumpkin_save_market()


async def pumpkin_tick(bot):
    m = pumpkin_market
    now = time.time()

    mood = m["mood"] * math.exp(random.gauss(0, 0.012))
    mood += (1 - mood) * 0.01
    m["mood"] = min(1.6, max(0.6, mood))

    if m.get("event") and now >= m["event"]["until"]:
        m["event"] = None

    new_event = None
    if not m.get("event") and now >= m.get("next_event", 0):
        base_ev = random.choice(PUMPKIN_EVENTS)
        new_event = dict(base_ev, until=now + PUMPKIN_EVENT_DURATION)
        m["event"] = new_event
        m["next_event"] = now + PUMPKIN_EVENT_DURATION + random.randint(*PUMPKIN_EVENT_GAP)

    pumpkin_record_price()

    if new_event:
        text = (
            f"{EMOJI_FIRE} <b>{new_event['name']}</b>\n"
            f"{new_event['text']}\n"
            f"Цена: <b>{fmt(pumpkin_price())} TON</b> {EMOJI_PUMPKIN}"
        )
        for uid in list(m.get("notify", [])):
            try:
                await bot.send_message(chat_id=int(uid), text=text, parse_mode="HTML")
            except Exception:
                pass
            await asyncio.sleep(0.05)

    await pumpkin_check_alerts(bot)


async def pumpkin_task(application: Application):
    while True:
        try:
            await asyncio.sleep(PUMPKIN_TICK_SECONDS)
            await pumpkin_tick(application.bot)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Ошибка биржи тыкв: {e}")
            traceback.print_exc()
            await asyncio.sleep(30)


# ---------- команды ----------

async def pumpkin_show_info(update: Update):
    await update.message.reply_text(
        f"{EMOJI_PUMPKIN} <b>ТЫКВЫ — КОМАНДЫ</b>\n\n"
        "• <b>биржа</b> — график, цена и остаток\n"
        "• <code>купить тыквы 10</code> (или «все»)\n"
        "• <code>продать тыквы 10</code> (или «все»)\n"
        "• <code>передать тыквы 10 @юзер</code> (или ответом)\n"
        "• <code>рт 5 к</code> — ставка тыквами в рулетке\n"
        "• <code>тыква алерт 16000</code> — сообщу, когда цена дойдёт\n"
        "• <code>тыква алерты</code> — список, «сброс» — очистить\n"
        "• <code>тыква события вкл</code> — оповещения о событиях\n\n"
        "<i>Тыквы выпадают бонусом в рулетке при ставках от 10 000 TON за раунд.</i>",
        parse_mode="HTML",
    )


async def pumpkin_show_exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    uid = get_user(update.effective_user)
    try:
        png = await asyncio.to_thread(pumpkin_render_chart)
    except Exception:
        traceback.print_exc()
        await msg.reply_text("❌ Не удалось нарисовать график, попробуй позже.")
        return

    caption = (
        f"{EMOJI_PUMPKIN} <b>Биржа тыкв</b>\n"
        f"Цена: <b>{fmt(pumpkin_price())} TON</b> {EMOJI_GEM}\n"
        f"У вас: <b>{fmt(pumpkin_get(uid))}</b>"
    )
    ev = pumpkin_event_active()
    if ev:
        caption += f"\n{EMOJI_FIRE} {ev['name']}: {ev['text']}"

    try:
        await msg.reply_photo(photo=io.BytesIO(png), caption=caption, parse_mode="HTML")
    except BadRequest as e:
        if "document_invalid" in str(e).lower():
            await msg.reply_photo(photo=io.BytesIO(png), caption=strip_tg_emojis(caption), parse_mode="HTML")
        else:
            raise


async def pumpkin_buy(update: Update, context: ContextTypes.DEFAULT_TYPE, raw: str):
    msg = update.message
    uid = get_user(update.effective_user)
    bal = int(round(float(balances[uid])))

    count = pumpkin_parse_count(raw)
    if count is None:
        await msg.reply_text("❌ Укажите количество: <code>купить тыквы 10</code>", parse_mode="HTML")
        return
    if count == "all":
        count = pumpkin_max_affordable(bal)
        if count <= 0:
            await msg.reply_text(f"❌ Не хватает TON. Цена тыквы: {fmt(pumpkin_price())} TON")
            return

    left = max(pumpkin_market["stock"] - PUMPKIN_MIN_STOCK, 0)
    if count > left:
        await msg.reply_text(f"❌ На бирже доступно только {fmt(left)} тыкв.")
        return

    cost = pumpkin_buy_cost(count)
    if cost > bal:
        await msg.reply_text(
            f"❌ Не хватает TON.\nНужно: {fmt(cost)} TON\nБаланс: {fmt(bal)} TON"
        )
        return

    balances[uid] = bal - cost
    save_balances()
    pumpkin_market["stock"] -= count
    pumpkin_add(uid, count)
    pumpkin_record_price()
    add_history(uid, "Расход (Тыквы)", cost, f"Куплено тыкв: {count}")

    await msg.reply_text(
        f"{EMOJI_PUMPKIN} Куплено: <b>{fmt(count)}</b>\n"
        f"{EMOJI_MONEY} Потрачено: <b>{fmt(cost)} TON</b> {EMOJI_GEM}\n"
        f"Тыкв: <b>{fmt(pumpkin_get(uid))}</b>",
        parse_mode="HTML",
    )
    await pumpkin_check_alerts(context.bot)


async def pumpkin_sell(update: Update, context: ContextTypes.DEFAULT_TYPE, raw: str):
    msg = update.message
    uid = get_user(update.effective_user)
    have = pumpkin_get(uid)

    count = pumpkin_parse_count(raw)
    if count is None:
        await msg.reply_text("❌ Укажите количество: <code>продать тыквы 10</code>", parse_mode="HTML")
        return
    if count == "all":
        count = have
    if count <= 0 or count > have:
        await msg.reply_text(f"❌ У вас только {fmt(have)} тыкв.")
        return

    value = pumpkin_sell_value(count)
    balances[uid] = int(round(float(balances[uid]))) + value
    save_balances()
    pumpkin_market["stock"] += count
    pumpkin_add(uid, -count)
    pumpkin_record_price()
    add_history(uid, "Доход (Тыквы)", value, f"Продано тыкв: {count}")

    await msg.reply_text(
        f"{EMOJI_PUMPKIN} Продано: <b>{fmt(count)}</b>\n"
        f"{EMOJI_MONEY} Получено: <b>{fmt(value)} TON</b> {EMOJI_GEM}\n"
        f"Тыкв: <b>{fmt(pumpkin_get(uid))}</b>",
        parse_mode="HTML",
    )
    await pumpkin_check_alerts(context.bot)


async def pumpkin_find_user(context: ContextTypes.DEFAULT_TYPE, target: str):
    target = target.strip()
    if target.startswith("@"):
        name = target.lstrip("@").strip(".,!?;:").lower()
        for uid, data in user_stats.items():
            if (data.get("username") or "").lower() == name:
                return uid, data.get("name") or f'<a href="tg://user?id={uid}">Игрок {uid}</a>'
        try:
            chat = await context.bot.get_chat(f"@{name}")
            if chat.type == "private" and not getattr(chat, "is_bot", False):
                uid = str(chat.id)
                if uid in balances:
                    return uid, get_user_link(uid, chat.first_name or f"Игрок {uid}")
        except Exception:
            pass
        return None, ""
    clean = target.replace("'", "").replace('"', "")
    if clean.isdigit() and clean in balances:
        return clean, user_stats.get(clean, {}).get("name", f'<a href="tg://user?id={clean}">Игрок {clean}</a>')
    return None, ""


async def pumpkin_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE, tokens: list):
    msg = update.message
    sender_id = get_user(update.effective_user)

    count_raw, target = None, None
    for tok in tokens:
        if count_raw is None and pumpkin_parse_count(tok) is not None:
            count_raw = tok
        elif target is None:
            target = tok
    count = pumpkin_parse_count(count_raw)
    if count is None:
        await msg.reply_text(
            "❌ Пример: <code>передать тыквы 10 @юзер</code> или ответом на сообщение.",
            parse_mode="HTML",
        )
        return

    recipient_id, recipient_name = None, ""
    reply = msg.reply_to_message
    if reply and reply.from_user:
        if reply.from_user.is_bot:
            await msg.reply_text("❌ Нельзя передавать тыквы ботам.")
            return
        recipient_id = get_user(reply.from_user)
        recipient_name = get_user_display_name(reply.from_user)
    elif target:
        recipient_id, recipient_name = await pumpkin_find_user(context, target)
        if not recipient_id:
            await msg.reply_text("❌ Игрок не найден. Пусть он хотя бы раз напишет боту.")
            return
    else:
        await msg.reply_text(
            "❌ Укажите получателя: <code>передать тыквы 10 @юзер</code> или ответом.",
            parse_mode="HTML",
        )
        return

    if recipient_id == sender_id:
        await msg.reply_text("❌ Нельзя передать тыквы самому себе.")
        return

    have = pumpkin_get(sender_id)
    if count == "all":
        count = have
    if count <= 0 or count > have:
        await msg.reply_text(f"❌ У вас только {fmt(have)} тыкв.")
        return

    pumpkin_add(sender_id, -count)
    pumpkin_add(recipient_id, count)

    await msg.reply_text(
        f"{EMOJI_PUMPKIN} Передано: <b>{fmt(count)}</b>\n"
        f"{EMOJI_PLAYER} Получатель: {recipient_name}",
        parse_mode="HTML",
    )


async def pumpkin_roulette_bet(update: Update, context: ContextTypes.DEFAULT_TYPE, parts: list) -> bool:
    """рт <тыкв на ставку> <ставки...> — тыквы продаются по курсу и идут в рулетку как TON."""
    msg = update.message
    try:
        per_bet = int(parts[1].replace(" ", ""))
    except ValueError:
        return False
    valid_bets = []
    for bet_str in parts[2:]:
        parsed = parse_bet(bet_str)
        if parsed is not None:
            valid_bets.append((bet_str, parsed))
    if per_bet <= 0 or not valid_bets:
        return False

    chat = update.effective_chat
    if chat.type in ("group", "supergroup") and str(chat.id) in disabled_chats:
        await msg.reply_text("⚠️ <b>Игры в этом чате временно отключены администратором!</b>", parse_mode="HTML")
        return True
    if roulette_running.get(chat.id, False):
        await msg.reply_text("🎰 Рулетка уже крутится.\nДождись результата.")
        return True

    uid = get_user(update.effective_user)
    mine = sum(1 for b in pending_bets.get(str(chat.id), []) if str(b["user_id"]) == uid)
    if mine + len(valid_bets) > MAX_BETS_PER_GAME:
        await msg.reply_text(f"{EMOJI_NO} Не более {MAX_BETS_PER_GAME} ставок на игру.", parse_mode="HTML")
        return True

    total = per_bet * len(valid_bets)
    have = pumpkin_get(uid)
    if total > have:
        await msg.reply_text(f"❌ Не хватает тыкв.\nНужно: {fmt(total)}\nУ вас: {fmt(have)}")
        return True

    value = pumpkin_sell_value(total)
    per_ton = value // len(valid_bets)
    if per_ton <= 0:
        await msg.reply_text("❌ Слишком маленькая ставка.")
        return True

    pumpkin_add(uid, -total)
    pumpkin_market["stock"] += total
    balances[uid] = int(round(float(balances[uid]))) + value
    save_balances()
    pumpkin_record_price()
    add_history(uid, "Доход (Тыквы)", value, f"Тыквы в рулетку: {total}")

    await msg.reply_text(
        f"{EMOJI_PUMPKIN} {fmt(total)} тыкв → <b>{fmt(value)} TON</b> по курсу биржи",
        parse_mode="HTML",
    )
    await roulette_batch_bets(update, per_ton, valid_bets)
    return True


async def pumpkin_alert_command(update: Update, parts: list):
    msg = update.message
    uid = get_user(update.effective_user)
    alerts = pumpkin_market.setdefault("alerts", {})
    sub = parts[1]

    if sub == "алерты":
        if len(parts) > 2 and parts[2] in {"сброс", "удалить", "очистить"}:
            alerts.pop(uid, None)
            pumpkin_save_market()
            await msg.reply_text("🔕 Все уведомления удалены.")
            return
        mine = alerts.get(uid, [])
        if not mine:
            await msg.reply_text("У вас нет уведомлений.\nПример: <code>тыква алерт 16000</code>", parse_mode="HTML")
            return
        rows = [
            f"• {'выше' if a['dir'] == 'up' else 'ниже'} <b>{fmt(a['price'])}</b> TON"
            for a in mine
        ]
        await msg.reply_text("🔔 <b>Ваши уведомления:</b>\n" + "\n".join(rows), parse_mode="HTML")
        return

    # алерт <цена>
    target = pumpkin_parse_price(parts[2]) if len(parts) > 2 else None
    if target is None:
        await msg.reply_text("❌ Пример: <code>тыква алерт 16000</code>", parse_mode="HTML")
        return
    cur = pumpkin_price()
    if int(round(cur)) == target:
        await msg.reply_text("Цена уже на этом уровне.")
        return
    mine = alerts.setdefault(uid, [])
    if len(mine) >= PUMPKIN_MAX_ALERTS:
        await msg.reply_text(f"❌ Максимум {PUMPKIN_MAX_ALERTS} уведомления. Очистить: <code>тыква алерты сброс</code>", parse_mode="HTML")
        return
    direction = "up" if target > cur else "down"
    mine.append({"price": target, "dir": direction})
    pumpkin_save_market()

    text = (
        f"🔔 Напишу, когда цена {'вырастет до' if direction == 'up' else 'упадёт до'} "
        f"<b>{fmt(target)} TON</b>"
    )
    if update.effective_chat.type != "private":
        text += "\n<i>Откройте личку с ботом, иначе сообщение не дойдёт.</i>"
    await msg.reply_text(text, parse_mode="HTML")


async def pumpkin_events_command(update: Update, parts: list):
    msg = update.message
    uid = get_user(update.effective_user)
    notify = pumpkin_market.setdefault("notify", [])
    arg = parts[2] if len(parts) > 2 else ""

    if arg in {"вкл", "on", "да"}:
        if uid not in notify:
            notify.append(uid)
            pumpkin_save_market()
        text = "🔔 Оповещения о событиях рынка включены."
        if update.effective_chat.type != "private":
            text += "\n<i>Откройте личку с ботом, иначе сообщения не дойдут.</i>"
        await msg.reply_text(text, parse_mode="HTML")
    elif arg in {"выкл", "off", "нет"}:
        if uid in notify:
            notify.remove(uid)
            pumpkin_save_market()
        await msg.reply_text("🔕 Оповещения о событиях выключены.")
    else:
        state = "включены" if uid in notify else "выключены"
        await msg.reply_text(
            f"Оповещения о событиях: <b>{state}</b>\n"
            "<code>тыква события вкл</code> / <code>тыква события выкл</code>",
            parse_mode="HTML",
        )


async def pumpkin_text_router(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, lower: str) -> bool:
    """Возвращает True, если сообщение — команда тыкв/биржи."""
    parts = lower.split()
    if not parts:
        return False
    head = parts[0].lstrip("/")
    tokens = text.split()

    if lower in {"биржа", "/биржа", "биржа тыкв"}:
        await pumpkin_show_exchange(update, context)
        return True

    if head in {"тыква", "тыквы"} and len(parts) >= 2:
        sub = parts[1]
        if sub == "инфо":
            await pumpkin_show_info(update)
            return True
        if sub in {"алерт", "алерты"}:
            await pumpkin_alert_command(update, parts)
            return True
        if sub in {"события", "событие"}:
            await pumpkin_events_command(update, parts)
            return True
        return False

    if len(parts) >= 2 and parts[1].startswith("тыкв"):
        if head == "купить":
            await pumpkin_buy(update, context, parts[2] if len(parts) > 2 else "")
            return True
        if head == "продать":
            await pumpkin_sell(update, context, parts[2] if len(parts) > 2 else "")
            return True
        if head in {"передать", "дать"}:
            await pumpkin_transfer(update, context, tokens[2:])
            return True

    if head in {"рт", "rt"} and len(parts) >= 3:
        return await pumpkin_roulette_bet(update, context, parts)

    return False


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"{EMOJI_NO} Ошибка в обработчике: {context.error!r}")


async def post_init(application: Application):
    asyncio.create_task(daily_reset_task())
    asyncio.create_task(monitor_timeouts_loop(application))
    asyncio.create_task(tournament_task(application))
    asyncio.create_task(pumpkin_task(application))


def main():
    if TOKEN == "TOKEN":
        print("❌ Сначала вставь токен бота в переменную TOKEN.")
        return

    application = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("give", give_command))
    application.add_handler(CommandHandler("mailing", mailing_command))
    application.add_handler(CommandHandler("tournament", show_tournament))
    application.add_handler(CommandHandler("turnir", show_tournament))
    application.add_handler(CommandHandler("market_deals", market_deals_command))
    application.add_handler(CommandHandler("market_release", market_release_command))
    application.add_handler(CommandHandler("market_refund", market_refund_command))
    application.add_handler(CallbackQueryHandler(general_callback_handler))

    application.add_handler(ChatMemberHandler(chat_member_updated_handler, ChatMemberHandler.CHAT_MEMBER))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_chat_members_handler))

    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_error_handler(error_handler)

    print("✅ Бот запущен со всеми исправлениями...")
    application.run_polling()

# =========================================================
# МИНИАП (WEB APP) — ЕДИНЫЙ БЛОК (подпись + API + игры + кнопка меню)
# =========================================================
import hashlib
import hmac as hmac_mod
import urllib.parse
from urllib.parse import unquote
from telegram import MenuButtonWebApp, WebAppInfo
from aiohttp import web

CORS = {"Access-Control-Allow-Origin": "*"}
MINIAPP_URL = "https://my-gameton.apps.bot-hosting.cloud"

def validate_init_data(init_data: str):
    if not init_data:
        print("[miniap] 401: initData ПУСТОЙ — открой строго через кнопку меню")
        return None
    try:
        pairs_raw = dict(p.split("=", 1) for p in init_data.split("&"))
    except Exception:
        print("[miniap] 401: не удалось разобрать initData")
        return None
    received_hash = pairs_raw.pop("hash", None)
    if not received_hash:
        print("[miniap] 401: нет поля hash")
        return None
    secret = hmac_mod.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()

    def calc(dcs):
        return hmac_mod.new(secret, dcs.encode(), hashlib.sha256).hexdigest()

    try:
        from urllib.parse import parse_qsl
        dec = dict(parse_qsl(init_data, keep_blank_values=True))
        dec.pop("hash", None)
        dcs = "\n".join(f"{k}={dec[k]}" for k in sorted(dec))
        ok = calc(dcs) == received_hash
        if not ok:
            dec2 = {k: v for k, v in dec.items() if k != "signature"}
            dcs2 = "\n".join(f"{k}={dec2[k]}" for k in sorted(dec2))
            ok = calc(dcs2) == received_hash
        if ok:
            print("[miniap] подпись сошлась!")
            try:
                user = json.loads(unquote(pairs_raw.get("user", "{}")))
                return str(user.get("id"))
            except Exception as e:
                print("[miniap] 401: ошибка разбора user:", e)
                return None
    except Exception as e:
        print("[miniap] ошибка вариантов:", e)

    dcs3 = "\n".join(f"{k}={pairs_raw[k]}" for k in sorted(pairs_raw))
    if calc(dcs3) == received_hash:
        print("[miniap] подпись сошлась (сырые значения)")
        try:
            user = json.loads(unquote(pairs_raw.get("user", "{}")))
            return str(user.get("id"))
        except Exception as e:
            print("[miniap] 401: ошибка разбора user:", e)
            return None
    print("[miniap] 401: подпись не сошлась ни в одном варианте")
    return None

def clean_name(raw: str, uid: str) -> str:
    text = re.sub(r"<[^>]+>", "", raw or "")
    return text.strip() or f"Игрок {uid}"

def web_finish(uid, game_label, bet, won_amount, note=""):
    if won_amount > 0:
        balances[uid] = int(round(float(balances.get(uid, 0)))) + won_amount
        record_game_win(uid, won_amount)
        net = won_amount - bet
        if net > 0:
            add_game_net_win(uid, net)
        add_history(uid, f"Доход ({game_label})", won_amount, note or "Игра в миниапе")
    else:
        if bet > 0:
            add_game_loss(uid, bet)
        add_history(uid, f"Расход ({game_label})", bet, note or "Игра в миниапе")
    save_balances()
    return int(round(float(balances.get(uid, 0))))

async def _web_auth(request):
    try:
        payload = await request.json()
    except Exception:
        return None, None
    uid = validate_init_data(payload.get("initData", ""))
    return uid, payload

# ---- онлайн: кто присылал запрос за последние 30 секунд ----
web_last_seen = {}
ONLINE_WINDOW = 30

def _online_count():
    now = time.time()
    for k in [k for k, t in web_last_seen.items() if now - t > ONLINE_WINDOW * 4]:
        web_last_seen.pop(k, None)
    return max(1, sum(1 for t in web_last_seen.values() if now - t <= ONLINE_WINDOW))

async def api_state(request):
    uid = validate_init_data(request.query.get("initData", ""))
    if uid is None:
        return web.json_response({"error": "unauthorized"}, status=401, headers=CORS)
    web_last_seen[uid] = time.time()
    _web_expire_all()
    name = clean_name(user_stats.get(uid, {}).get("name", ""), uid)
    u_game = game_stats.get(uid, {"won": 0, "lost": 0})
    top = tournament_sorted()[:3]
    now_msk = datetime.now(MSK_TZ)
    end = now_msk.replace(hour=23, minute=59, second=0, microsecond=0)
    if now_msk >= end:
        end += timedelta(days=1)
    acc = get_bank_account(uid)
    ev = pumpkin_event_active()
    return web.json_response({
        "online": _online_count(),
        "name": name,
        "balance": int(round(float(balances.get(uid, 0)))),
        "pumpkins": pumpkin_get(uid),
        "wins": int(u_game.get("won", 0)),
        "losses": int(u_game.get("lost", 0)),
        "deposit": int(acc.get("balance", 0)),
        "pumpkin": {
            "price": int(pumpkin_price()),
            "stock_pct": round(pumpkin_market["stock"] / PUMPKIN_TOTAL * 100, 2),
            "event": {"name": ev["name"], "text": ev["text"], "mult": ev["mult"]} if ev else None,
        },
        "tournament": {
            "prizes": TOURNAMENT_PRIZES,
            "ends_in_sec": int((end - now_msk).total_seconds()),
            "top": [{"name": clean_name(d.get("name", ""), t_uid),
                     "score": int(d.get("score", 0))} for t_uid, d in top],
        },
    }, headers=CORS)

async def api_bonus(request):
    uid = validate_init_data(await request.text())
    if uid is None:
        return web.json_response({"error": "unauthorized"}, status=401, headers=CORS)
    now = time.time()
    cooldown = 24 * 60 * 60
    if now - bonus_times.get(uid, 0) < cooldown:
        return web.json_response(
            {"ok": False, "wait_hours": int((cooldown - (now - bonus_times.get(uid, 0))) // 3600)},
            headers=CORS)
    bonus_times[uid] = now
    balances[uid] = int(round(float(balances.get(uid, 0)))) + 2000
    save_bonus_times()
    save_balances()
    add_history(uid, "Бонус", 2000, "Ежедневный бонус (миниап)")
    return web.json_response({"ok": True, "reward": 2000}, headers=CORS)

WEB_SLOTS_SYMBOLS = ['🍇', '🍋', '🍒', '🔔', '💎', '7️⃣']
WEB_SLOTS_WEIGHTS = [5, 5, 4, 3, 2, 1]

async def api_play(request):
    uid, payload = await _web_auth(request)
    if uid is None:
        return web.json_response({"error": "unauthorized"}, status=401, headers=CORS)
    game = payload.get("game")
    try:
        bet = int(payload.get("bet", 0))
    except (TypeError, ValueError):
        bet = 0
    bal = int(round(float(balances.get(uid, 0))))
    if game not in {"dice", "slots", "roulette"}:
        return web.json_response({"error": "unknown_game"}, headers=CORS)
    if bet <= 0 or bet > bal:
        return web.json_response({"error": "balance"}, headers=CORS)
    balances[uid] = bal - bet
    save_balances()

    if game == "slots":
        PAY3 = {'7️⃣': 22.0, '💎': 10.0, '🔔': 8.5, '🍒': 4.75, '🍇': 4.25, '🍋': 4.25}
        PAY2 = {'7️⃣': 3.25, '💎': 1.6, '🔔': 0.85, '🍒': 0.85}
        reels = [[random.choices(WEB_SLOTS_SYMBOLS, WEB_SLOTS_WEIGHTS)[0] for _ in range(3)]
                 for _ in range(3)]
        win_amount = 0
        for r in range(3):
            a, b, c = reels[0][r], reels[1][r], reels[2][r]
            if a == b == c:
                win_amount += int(round(bet * PAY3.get(a, 1.5)))
            elif a == b and a in PAY2:
                win_amount += int(round(bet * PAY2[a]))
        if all(s == '7️⃣' for col in reels for s in col):
            win_amount += int(round(bet * 80))  # ДЖЕКПОТ: все 9 семёрок
        new_bal = web_finish(uid, "Слоты", bet, win_amount, f"Слоты (миниап): {reels}")
        return web.json_response({"reels": reels,
                                  "win_amount": win_amount,
                                  "mult": round(win_amount / bet, 2) if win_amount else 0,
                                  "balance": new_bal}, headers=CORS)

    if game == "dice":
        choice = str(payload.get("choice", "")).lower().strip()
        value = random.randint(1, 6)
        if choice.isdigit() and 1 <= int(choice) <= 6:
            won, mult = int(choice) == value, 4.0
        elif choice in {"чет", "чёт"}:
            won, mult = value % 2 == 0, 1.5
        elif choice == "нечет":
            won, mult = value % 2 != 0, 1.5
        elif choice == "больше":
            won, mult = value >= 4, 1.5
        elif choice == "меньше":
            won, mult = value <= 3, 1.5
        else:
            balances[uid] = bal
            save_balances()
            return web.json_response({"error": "bad_choice"}, headers=CORS)
        win_amount = int(round(bet * mult)) if won else 0
        new_bal = web_finish(uid, "Кубы", bet, win_amount, f"Кубы (миниап): выпало {value}")
        return web.json_response({"value": value, "won": won, "mult": mult,
                                  "win_amount": win_amount, "balance": new_bal}, headers=CORS)

    parsed = parse_bet(str(payload.get("bet_key", "")))
    if parsed is None:
        balances[uid] = bal
        save_balances()
        return web.json_response({"error": "bad_bet"}, headers=CORS)
    numbers, coefficient, bet_name = parsed
    result = random.randint(0, 36)
    color = "green" if result == 0 else ("red" if result in RED else "black")
    won = result in numbers
    win_amount = int(round(bet * coefficient)) if won else 0
    new_bal = web_finish(uid, "Рулетка", bet, win_amount, f"Рулетка (миниап): {result}")
    return web.json_response({"result": result, "color": color, "won": won, "bet_name": bet_name,
                              "mult": coefficient, "win_amount": win_amount, "balance": new_bal}, headers=CORS)

active_web_mines = {}
active_web_bj = {}
WEB_IDLE_LIMIT = 180  # сек без действий — раунд закрывается автоматически

def _web_mines_expire(uid):
    g = active_web_mines.get(uid)
    if not g or time.time() - g.get("ts", 0) <= WEB_IDLE_LIMIT:
        return
    active_web_mines.pop(uid, None)
    bet, n = g["bet"], len(g["opened"])
    if n == 0:
        balances[uid] = int(round(float(balances.get(uid, 0)))) + bet
        save_balances()
        add_history(uid, "Возврат (Мины)", bet, "Миниап: отмена по неактивности")
    else:
        mult = get_mines_multiplier(n, g["mines_count"])
        web_finish(uid, "Мины", bet, int(round(bet * mult)), "Мины (миниап): автовывод по неактивности")

def _web_bj_expire(uid):
    g = active_web_bj.get(uid)
    if not g or time.time() - g.get("ts", 0) <= WEB_IDLE_LIMIT:
        return
    active_web_bj.pop(uid, None)
    player, dealer, bet = g["player"], g["dealer"], g["bet"]
    ps, ds = calculate_score(player), calculate_score(dealer)
    while ds < 17:
        dealer.append(draw_card())
        ds = calculate_score(dealer)
    win = bet * 2 if (ds > 21 or ps > ds) else (bet if ps == ds else 0)
    web_finish(uid, "Блэкджек", bet, win, "Миниап: авто-стенд по неактивности")

def _web_expire_all():
    for u in list(active_web_mines):
        _web_mines_expire(u)
    for u in list(active_web_bj):
        _web_bj_expire(u)
    for u in list(active_web_crash):
        _crash_settle(u)
    for u in list(active_web_hilo):
        _web_hilo_expire(u)
    _mk_expire_all()

async def api_mines(request):
    uid, payload = await _web_auth(request)
    if uid is None:
        return web.json_response({"error": "unauthorized"}, status=401, headers=CORS)
    action = payload.get("action")
    _web_mines_expire(uid)
    bal = int(round(float(balances.get(uid, 0))))
    if action == "state":
        g = active_web_mines.get(uid)
        if not g:
            return web.json_response({"active": False, "balance": bal}, headers=CORS)
        opened = sorted(g["opened"])
        mult = get_mines_multiplier(len(opened), g["mines_count"]) if opened else 1.0
        return web.json_response({"active": True, "bet": g["bet"], "mines_count": g["mines_count"],
                                  "opened": opened, "mult": mult,
                                  "win_amount": int(round(g["bet"] * mult)), "balance": bal}, headers=CORS)
    if action == "start":
        try:
            bet = int(payload.get("bet", 0))
        except (TypeError, ValueError):
            bet = 0
        if bet <= 0 or bet > bal:
            return web.json_response({"error": "balance"}, headers=CORS)
        if uid in active_web_mines:
            return web.json_response({"error": "already_playing"}, headers=CORS)
        try:
            mines_count = min(24, max(3, int(payload.get("mines", 3))))
        except (TypeError, ValueError):
            mines_count = 3
        balances[uid] = bal - bet
        save_balances()
        add_history(uid, "Расход (Мины)", bet, "Миниап: старт игры")
        active_web_mines[uid] = {
            "bet": bet,
            "mines": set(random.sample(range(25), mines_count)),
            "opened": set(),
            "mines_count": mines_count,
            "ts": time.time(),
        }
        return web.json_response({"started": True, "mines_count": mines_count,
                                  "balance": bal - bet}, headers=CORS)
    g = active_web_mines.get(uid)
    if not g:
        return web.json_response({"error": "no_game"}, headers=CORS)
    g["ts"] = time.time()
    if action == "click":
        try:
            cell = int(payload.get("cell", -1))
        except (TypeError, ValueError):
            cell = -1
        if not 0 <= cell < 25 or cell in g["opened"]:
            return web.json_response({"error": "bad_cell"}, headers=CORS)
        if cell in g["mines"]:
            add_game_loss(uid, g["bet"])
            add_history(uid, "Расход (Мины)", g["bet"], "Миниап: взрыв")
            mines = list(g["mines"])
            active_web_mines.pop(uid, None)
            return web.json_response({"bust": True, "cell": cell, "mines": mines,
                                      "balance": int(round(float(balances.get(uid, 0))))}, headers=CORS)
        g["opened"].add(cell)
        mult = get_mines_multiplier(len(g["opened"]), g["mines_count"])
        safe_total = 25 - g["mines_count"]
        if len(g["opened"]) >= safe_total:
            win_amount = int(round(g["bet"] * mult))
            new_bal = web_finish(uid, "Мины", g["bet"], win_amount, "Мины (миниап): полная зачистка")
            active_web_mines.pop(uid, None)
            return web.json_response({"safe": True, "finished": True, "cell": cell, "mult": mult,
                                      "win_amount": win_amount, "balance": new_bal}, headers=CORS)
        return web.json_response({"safe": True, "cell": cell, "mult": mult,
                                  "win_amount": int(round(g["bet"] * mult)),
                                  "balance": int(round(float(balances.get(uid, 0))))}, headers=CORS)
    if action == "cashout":
        if not g["opened"]:
            return web.json_response({"error": "nothing_to_cash"}, headers=CORS)
        mult = get_mines_multiplier(len(g["opened"]), g["mines_count"])
        win_amount = int(round(g["bet"] * mult))
        new_bal = web_finish(uid, "Мины", g["bet"], win_amount, f"Мины (миниап): забрал x{mult}")
        mines = list(g["mines"])
        active_web_mines.pop(uid, None)
        return web.json_response({"cashed": True, "mult": mult, "win_amount": win_amount,
                                  "mines": mines, "balance": new_bal}, headers=CORS)
    return web.json_response({"error": "bad_action"}, headers=CORS)

async def api_bj(request):
    uid, payload = await _web_auth(request)
    if uid is None:
        return web.json_response({"error": "unauthorized"}, status=401, headers=CORS)
    action = payload.get("action")
    _web_bj_expire(uid)
    bal = int(round(float(balances.get(uid, 0))))
    if action == "state":
        g = active_web_bj.get(uid)
        if not g:
            return web.json_response({"active": False, "balance": bal}, headers=CORS)
        d0 = g["dealer"][0]
        return web.json_response({"active": True, "bet": g["bet"], "player": g["player"],
                                  "dealer": [d0], "player_score": calculate_score(g["player"]),
                                  "dealer_score": d0["value"], "balance": bal}, headers=CORS)
    if action == "start":
        try:
            bet = int(payload.get("bet", 0))
        except (TypeError, ValueError):
            bet = 0
        if bet <= 0 or bet > bal:
            return web.json_response({"error": "balance"}, headers=CORS)
        if uid in active_web_bj:
            return web.json_response({"error": "already_playing"}, headers=CORS)
        balances[uid] = bal - bet
        save_balances()
        add_history(uid, "Расход (Блэкджек)", bet, "Миниап: старт игры")
        player = [draw_card(), draw_card()]
        dealer = [draw_card(), draw_card()]
        active_web_bj[uid] = {"bet": bet, "player": player, "dealer": dealer, "ts": time.time()}
        ps = calculate_score(player)
        if ps == 21:
            ds = calculate_score(dealer)
            if ds == 21:
                win_amount = bet
                outcome = "push"
            else:
                win_amount = int(round(bet * 2.5))
                outcome = "win"
            new_bal = web_finish(uid, "Блэкджек", bet, win_amount, f"Миниап: {outcome}")
            active_web_bj.pop(uid, None)
            return web.json_response({"started": True, "player": player, "dealer": dealer,
                                      "player_score": ps, "dealer_score": ds, "finished": True,
                                      "outcome": outcome, "win_amount": win_amount,
                                      "balance": new_bal}, headers=CORS)
        return web.json_response({"started": True, "player": player, "dealer": [dealer[0]],
                                  "player_score": ps, "dealer_score": dealer[0]["value"],
                                  "balance": bal - bet}, headers=CORS)
    g = active_web_bj.get(uid)
    if not g:
        return web.json_response({"error": "no_game"}, headers=CORS)
    g["ts"] = time.time()
    if action == "hit":
        g["player"].append(draw_card())
        ps = calculate_score(g["player"])
        if ps > 21:
            add_game_loss(uid, g["bet"])
            add_history(uid, "Расход (Блэкджек)", g["bet"], "Миниап: перебор")
            dealer = g["dealer"]
            active_web_bj.pop(uid, None)
            return web.json_response({"bust": True, "player": g["player"], "dealer": dealer,
                                      "player_score": ps, "dealer_score": calculate_score(dealer),
                                      "balance": int(round(float(balances.get(uid, 0))))}, headers=CORS)
        return web.json_response({"player": g["player"], "player_score": ps}, headers=CORS)
    if action == "stand":
        player, dealer = g["player"], g["dealer"]
        ps = calculate_score(player)
        ds = calculate_score(dealer)
        while ds < 17:
            dealer.append(draw_card())
            ds = calculate_score(dealer)
        bet = g["bet"]
        if ds > 21 or ps > ds:
            win_amount, outcome = bet * 2, "win"
        elif ps == ds:
            win_amount, outcome = bet, "push"
        else:
            win_amount, outcome = 0, "lose"
        new_bal = web_finish(uid, "Блэкджек", bet, win_amount, f"Миниап: {outcome}")
        active_web_bj.pop(uid, None)
        return web.json_response({"player": player, "dealer": dealer, "player_score": ps,
                                  "dealer_score": ds, "outcome": outcome, "win_amount": win_amount,
                                  "balance": new_bal}, headers=CORS)
    return web.json_response({"error": "bad_action"}, headers=CORS)

# =========================================================
# КРАШ (миниап) — раунд считается на сервере, клиент только рисует
# множитель растёт как x = e^(0.09 * секунды); точка краша выбирается
# при старте и не передаётся клиенту до конца раунда. RTP ≈ 96%.
# =========================================================
CRASH_RATE = 0.09
CRASH_EDGE = 0.96
CRASH_MAX = 1000.0
active_web_crash = {}
crash_history = []

def _crash_mult_at(elapsed):
    return math.floor(math.exp(CRASH_RATE * max(0.0, elapsed)) * 100) / 100

def _crash_gen():
    u = random.random()
    cp = CRASH_EDGE / (1.0 - u)
    cp = math.floor(cp * 100) / 100
    return min(CRASH_MAX, max(1.0, cp))

def _crash_push(cp):
    crash_history.append(cp)
    del crash_history[:-30]

def _crash_hist():
    return list(crash_history[-25:])

def _crash_settle(uid):
    """Закрывает раунд, если авто-вывод или краш уже наступили. Иначе None."""
    g = active_web_crash.get(uid)
    if not g:
        return None
    el = time.time() - g["t0"]
    cp, bet, auto = g["cp"], g["bet"], g["auto"]
    if auto and auto < cp and el >= math.log(auto) / CRASH_RATE:
        win = int(round(bet * auto))
        nb = web_finish(uid, "Краш", bet, win, f"Краш (миниап): авто x{auto:.2f}")
        active_web_crash.pop(uid, None)
        _crash_push(cp)
        return {"cashed": True, "auto": True, "mult": auto, "win_amount": win,
                "bet": bet, "crash_point": cp, "balance": nb}
    crash_t = math.log(cp) / CRASH_RATE if cp > 1.0 else 0.0
    if el >= crash_t:
        nb = web_finish(uid, "Краш", bet, 0, f"Краш (миниап): взрыв x{cp:.2f}")
        active_web_crash.pop(uid, None)
        _crash_push(cp)
        return {"crashed": True, "crash_point": cp, "bet": bet, "balance": nb}
    return None

async def api_crash(request):
    uid, payload = await _web_auth(request)
    if uid is None:
        return web.json_response({"error": "unauthorized"}, status=401, headers=CORS)
    action = payload.get("action")
    bal = int(round(float(balances.get(uid, 0))))

    if action == "state":
        res = _crash_settle(uid)
        if res:
            res.update(active=False, history=_crash_hist())
            return web.json_response(res, headers=CORS)
        g = active_web_crash.get(uid)
        if not g:
            return web.json_response({"active": False, "balance": bal,
                                      "history": _crash_hist()}, headers=CORS)
        el = time.time() - g["t0"]
        return web.json_response({"active": True, "elapsed": round(el, 3), "bet": g["bet"],
                                  "auto": g["auto"] or 0, "mult": _crash_mult_at(el),
                                  "balance": bal, "history": _crash_hist()}, headers=CORS)

    if action == "start":
        _crash_settle(uid)  # закрыть «забытый» раунд, если он уже закончился
        if uid in active_web_crash:
            return web.json_response({"error": "already_playing"}, headers=CORS)
        try:
            bet = int(payload.get("bet", 0))
        except (TypeError, ValueError):
            bet = 0
        bal = int(round(float(balances.get(uid, 0))))
        if bet <= 0 or bet > bal:
            return web.json_response({"error": "balance"}, headers=CORS)
        try:
            auto = float(payload.get("auto") or 0)
        except (TypeError, ValueError):
            auto = 0.0
        auto = round(auto, 2) if 1.01 <= auto <= CRASH_MAX else None
        balances[uid] = bal - bet
        save_balances()
        active_web_crash[uid] = {"bet": bet, "cp": _crash_gen(), "t0": time.time(), "auto": auto}
        return web.json_response({"started": True, "elapsed": 0, "balance": bal - bet,
                                  "history": _crash_hist()}, headers=CORS)

    if action == "cashout":
        res = _crash_settle(uid)
        if res:
            res["history"] = _crash_hist()
            return web.json_response(res, headers=CORS)
        g = active_web_crash.get(uid)
        if not g:
            return web.json_response({"error": "no_game"}, headers=CORS)
        m = max(1.0, _crash_mult_at(time.time() - g["t0"]))
        win = int(round(g["bet"] * m))
        nb = web_finish(uid, "Краш", g["bet"], win, f"Краш (миниап): забрал x{m:.2f}")
        active_web_crash.pop(uid, None)
        _crash_push(g["cp"])
        return web.json_response({"cashed": True, "mult": m, "win_amount": win, "bet": g["bet"],
                                  "crash_point": g["cp"], "balance": nb,
                                  "history": _crash_hist()}, headers=CORS)

    return web.json_response({"error": "bad_action"}, headers=CORS)

# =========================================================
# ПЛИНКО (миниап) — путь шарика выбирает сервер, клиент его красиво проигрывает
# =========================================================
PLINKO_ROWS = 12
PLINKO_RTP = 0.96
PLINKO_BASE = {
    "low":    [11.0, 3.2, 1.6, 1.4, 1.1, 1.0, 0.5],
    "medium": [33.0, 11.0, 4.0, 2.0, 1.1, 0.6, 0.3],
    "high":   [170.0, 24.0, 8.1, 2.0, 0.7, 0.2, 0.2],
}

def _plinko_table(shape):
    full = shape + shape[-2::-1]  # симметрично: 13 ячеек для 12 рядов
    probs = [math.comb(PLINKO_ROWS, k) / 2 ** PLINKO_ROWS for k in range(PLINKO_ROWS + 1)]
    rtp = sum(p * m for p, m in zip(probs, full))
    scale = PLINKO_RTP / rtp
    return [round(m * scale, 2) for m in full]

PLINKO_TABLES = {name: _plinko_table(shape) for name, shape in PLINKO_BASE.items()}

async def api_plinko(request):
    uid, payload = await _web_auth(request)
    if uid is None:
        return web.json_response({"error": "unauthorized"}, status=401, headers=CORS)
    action = payload.get("action", "drop")
    if action == "config":
        return web.json_response({"rows": PLINKO_ROWS, "tables": PLINKO_TABLES}, headers=CORS)
    if action != "drop":
        return web.json_response({"error": "bad_action"}, headers=CORS)
    risk = payload.get("risk", "medium")
    if risk not in PLINKO_TABLES:
        risk = "medium"
    try:
        bet = int(payload.get("bet", 0))
    except (TypeError, ValueError):
        bet = 0
    bal = int(round(float(balances.get(uid, 0))))
    if bet <= 0 or bet > bal:
        return web.json_response({"error": "balance"}, headers=CORS)
    balances[uid] = bal - bet
    save_balances()
    path = [random.getrandbits(1) for _ in range(PLINKO_ROWS)]
    slot = sum(path)
    mult = PLINKO_TABLES[risk][slot]
    win = int(round(bet * mult))
    nb = web_finish(uid, "Плинко", bet, win, f"Плинко (миниап): x{mult}")
    if 0 < win < bet:
        add_game_loss(uid, bet - win)
    return web.json_response({"path": path, "slot": slot, "mult": mult, "win_amount": win,
                              "bet": bet, "risk": risk, "won": win > bet, "balance": nb}, headers=CORS)

# =========================================================
# ВЫШЕ-НИЖЕ / HI-LO (миниап) — угадай, будет ли следующая карта выше или ниже
# Цена шага = 0.96 / вероятность → RTP 96% на каждом шаге. Ничья = проигрыш.
# =========================================================
HILO_EDGE = 0.96
HILO_MAX = 500.0
HILO_SUITS = ["♠", "♥", "♦", "♣"]
active_web_hilo = {}

def _hilo_card():
    return {"rank": random.randint(2, 14), "suit": random.choice(HILO_SUITS)}

def _hilo_steps(rank):
    up = round(HILO_EDGE * 13 / (14 - rank), 4) if rank < 14 else None
    down = round(HILO_EDGE * 13 / (rank - 2), 4) if rank > 2 else None
    return up, down

def _hilo_view(g, extra=None):
    up, down = _hilo_steps(g["card"]["rank"])
    d = {"active": True, "bet": g["bet"], "card": g["card"], "mult": g["mult"], "steps": g["steps"],
         "up": up, "down": down, "win_amount": int(g["bet"] * g["mult"] + 0.5),
         "trail": g["trail"][-7:]}
    if extra:
        d.update(extra)
    return d

def _web_hilo_expire(uid):
    g = active_web_hilo.get(uid)
    if not g or time.time() - g.get("ts", 0) <= WEB_IDLE_LIMIT:
        return
    active_web_hilo.pop(uid, None)
    if g["steps"] == 0:
        balances[uid] = int(round(float(balances.get(uid, 0)))) + g["bet"]
        save_balances()
        add_history(uid, "Возврат (Выше-Ниже)", g["bet"], "Миниап: отмена по неактивности")
    else:
        web_finish(uid, "Выше-Ниже", g["bet"], int(g["bet"] * g["mult"] + 0.5),
                   "Выше-Ниже (миниап): автовывод по неактивности")

async def api_hilo(request):
    uid, payload = await _web_auth(request)
    if uid is None:
        return web.json_response({"error": "unauthorized"}, status=401, headers=CORS)
    action = payload.get("action")
    _web_hilo_expire(uid)
    bal = int(round(float(balances.get(uid, 0))))

    if action == "state":
        g = active_web_hilo.get(uid)
        if not g:
            return web.json_response({"active": False, "balance": bal}, headers=CORS)
        return web.json_response(_hilo_view(g, {"balance": bal}), headers=CORS)

    if action == "start":
        if uid in active_web_hilo:
            return web.json_response({"error": "already_playing"}, headers=CORS)
        try:
            bet = int(payload.get("bet", 0))
        except (TypeError, ValueError):
            bet = 0
        if bet <= 0 or bet > bal:
            return web.json_response({"error": "balance"}, headers=CORS)
        balances[uid] = bal - bet
        save_balances()
        g = {"bet": bet, "card": _hilo_card(), "mult": 1.0, "steps": 0, "trail": [], "ts": time.time()}
        active_web_hilo[uid] = g
        return web.json_response(_hilo_view(g, {"started": True, "balance": bal - bet}), headers=CORS)

    g = active_web_hilo.get(uid)
    if not g:
        return web.json_response({"error": "no_game"}, headers=CORS)
    g["ts"] = time.time()

    if action == "skip":
        old = g["card"]
        g["trail"].append(old)
        g["trail"] = g["trail"][-12:]
        g["card"] = _hilo_card()
        return web.json_response(_hilo_view(g, {"skipped": True, "prev": old, "balance": bal}), headers=CORS)

    if action == "guess":
        direction = payload.get("dir")
        up, down = _hilo_steps(g["card"]["rank"])
        step = up if direction == "up" else down if direction == "down" else None
        if step is None:
            return web.json_response({"error": "bad_guess"}, headers=CORS)
        old, new = g["card"], _hilo_card()
        won = new["rank"] > old["rank"] if direction == "up" else new["rank"] < old["rank"]
        g["trail"].append(old)
        g["trail"] = g["trail"][-12:]
        g["card"] = new
        if not won:
            nb = web_finish(uid, "Выше-Ниже", g["bet"], 0, f"Выше-Ниже (миниап): мимо после {g['steps']} угадываний")
            active_web_hilo.pop(uid, None)
            return web.json_response({"correct": False, "finished": True, "prev": old, "card": new,
                                      "steps": g["steps"], "bet": g["bet"], "balance": nb}, headers=CORS)
        g["steps"] += 1
        g["mult"] = min(HILO_MAX, round(g["mult"] * step, 2))
        if g["mult"] >= HILO_MAX:
            win = int(g["bet"] * g["mult"] + 0.5)
            nb = web_finish(uid, "Выше-Ниже", g["bet"], win, f"Выше-Ниже (миниап): максимум x{g['mult']}")
            active_web_hilo.pop(uid, None)
            return web.json_response({"correct": True, "finished": True, "cashed": True, "prev": old, "card": new,
                                      "mult": g["mult"], "steps": g["steps"], "win_amount": win,
                                      "bet": g["bet"], "balance": nb}, headers=CORS)
        return web.json_response(_hilo_view(g, {"correct": True, "prev": old, "balance": bal}), headers=CORS)

    if action == "cashout":
        if g["steps"] < 1:
            return web.json_response({"error": "nothing_to_cash"}, headers=CORS)
        win = int(g["bet"] * g["mult"] + 0.5)
        nb = web_finish(uid, "Выше-Ниже", g["bet"], win, f"Выше-Ниже (миниап): забрал x{g['mult']}")
        active_web_hilo.pop(uid, None)
        return web.json_response({"cashed": True, "mult": g["mult"], "win_amount": win, "bet": g["bet"],
                                  "steps": g["steps"], "card": g["card"], "balance": nb}, headers=CORS)

    return web.json_response({"error": "bad_action"}, headers=CORS)

# =========================================================
# МАРКЕТ: обмен TON на Telegram Stars между игроками (эскроу у бота)
#  1. Продавец выставляет N TON за S ⭐ — TON замораживаются у бота.
#  2. Покупатель жмёт «Купить» — объявление резервируется, продавцу приходит ЛС.
#  3. У покупателя 30 минут, чтобы отправить Stars продавцу и нажать «Я отправил».
#  4. Продавец жмёт «Получил Stars» — TON уходят покупателю.
#  Если продавец молчит — покупатель пишет владельцу, владелец делает /market_release ID.
# =========================================================
MARKET_FILE = "market.json"
MARKET_DEAL_SECONDS = 30 * 60
MARKET_MIN_TON = 10
MARKET_MAX_TON = 1_000_000_000_000
MARKET_MIN_STARS = 1
MARKET_MAX_STARS = 10_000_000
MARKET_MAX_LISTINGS = 5      # одновременных объявлений на игрока
MARKET_MAX_OPEN_DEALS = 3    # одновременных сделок покупателя
MARKET_ADMIN_USERNAME = os.getenv("MARKET_ADMIN_USERNAME", "").strip().lstrip("@")

market = load_json(MARKET_FILE, {"seq": 0, "listings": {}, "deals": {}})
market.setdefault("seq", 0)
market.setdefault("listings", {})
market.setdefault("deals", {})


def save_market():
    save_json(MARKET_FILE, market)


class MarketError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def _mk_next_id():
    market["seq"] = int(market.get("seq", 0)) + 1
    return str(market["seq"])


def _mk_esc(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _mk_name(uid):
    return clean_name(user_stats.get(str(uid), {}).get("name", ""), str(uid))


def _mk_uname(uid):
    u = (user_stats.get(str(uid), {}).get("username") or "").strip().lstrip("@")
    return u if re.fullmatch(r"[A-Za-z0-9_]{4,32}", u or "") else ""


def _mk_link(uid):
    name = _mk_esc(_mk_name(uid))
    u = _mk_uname(uid)
    if u:
        return f'<a href="https://t.me/{u}">{name}</a>'
    return f'<a href="tg://user?id={uid}">{name}</a>'


def _mk_rate(ton, stars):
    return ton / stars if stars else 0.0


def _mk_num(x):
    s = f"{x:,.2f}".replace(",", " ").rstrip("0").rstrip(".")
    return s or "0"


def _mk_money(x):
    return f"{int(x):,}".replace(",", " ")


async def _mk_send(chat_id, text, buttons=None):
    token = TOKEN or _tg_token() or ""
    if not token:
        print("[market] токен бота не найден — ЛС не отправлено")
        return False
    payload = {"chat_id": int(chat_id), "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": True}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}
    try:
        import aiohttp
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12)) as sess:
            async with sess.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload) as r:
                data = await r.json()
                if not data.get("ok"):
                    print("[market] sendMessage:", data.get("description"))
                    return False
                return True
    except Exception as e:
        print("[market] ошибка отправки:", e)
        return False


def _mk_notify(chat_id, text, buttons=None):
    try:
        asyncio.get_running_loop().create_task(_mk_send(chat_id, text, buttons))
    except RuntimeError:
        pass


def _mk_app_btn(text, deal_id=None):
    sep = "&" if "?" in MINIAPP_URL else "?"
    url = f"{MINIAPP_URL}{sep}mk={'d' + str(deal_id) if deal_id else 'list'}"
    return {"text": text, "web_app": {"url": url}}


def _mk_deal_line(d):
    return (f"<b>{_mk_money(d['ton'])}</b> TON {EMOJI_GEM} ⇄ <b>{_mk_money(d['stars'])}</b> {EMOJI_STAR} Stars "
            f"· курс <b>{_mk_num(_mk_rate(d['ton'], d['stars']))}</b> TON за 1 {EMOJI_STAR}")


# ---------- состояние ----------
def _mk_unreserve(d):
    l = market["listings"].get(d["listing"])
    if l and l["status"] == "reserved" and l.get("deal") == d["id"]:
        l["status"] = "active"
        l["deal"] = None


def _mk_expire_all():
    now = time.time()
    changed = False
    for d in list(market["deals"].values()):
        if d["status"] == "waiting_buyer" and now >= d["expires_at"]:
            d["status"] = "expired"
            d["closed"] = now
            _mk_unreserve(d)
            changed = True
            _mk_notify(d["buyer"], f"⌛ <b>Сделка #{d['id']} отменена</b>: 30 минут вышло, а перевод Stars не подтверждён.\n"
                                   f"Если вы всё-таки отправили Stars — срочно напишите владельцу бота.")
            _mk_notify(d["seller"], f"⌛ Сделка #{d['id']} отменена по времени — покупатель не отправил Stars.\n"
                                    f"Ваше объявление снова активно: {_mk_deal_line(d)}")
        elif d["status"] == "buyer_paid" and not d.get("remind") and now - d.get("paid_at", now) > 600:
            d["remind"] = True
            changed = True
            _mk_notify(d["seller"], f"🔔 Напоминание по сделке #{d['id']}: покупатель отметил, что отправил вам "
                                    f"<b>{_mk_money(d['stars'])}</b> {EMOJI_STAR}. Проверьте Stars и подтвердите.",
                       [[{"text": "✅ Получил Stars", "callback_data": f"mk_recv:{d['id']}"},
                         {"text": "⚠️ Не получил", "callback_data": f"mk_norecv:{d['id']}"}]])
    if len(market["deals"]) > 1500 or len(market["listings"]) > 1500:
        cutoff = now - 14 * 86400
        for k, d in list(market["deals"].items()):
            if d["status"] in ("completed", "expired", "cancelled", "released", "refunded") and d.get("closed", now) < cutoff:
                market["deals"].pop(k, None)
        for k, l in list(market["listings"].items()):
            if l["status"] in ("sold", "cancelled") and l.get("closed", now) < cutoff:
                market["listings"].pop(k, None)
        changed = True
    if changed:
        save_market()


# ---------- операции ----------
def _mk_create(uid, ton, stars):
    if ton < MARKET_MIN_TON:
        raise MarketError("min_ton", f"Минимум для продажи — {MARKET_MIN_TON} TON")
    if ton > MARKET_MAX_TON:
        raise MarketError("max_ton", "Слишком большая сумма")
    if stars < MARKET_MIN_STARS or stars > MARKET_MAX_STARS:
        raise MarketError("bad_stars", f"Цена: от {MARKET_MIN_STARS} до {_mk_money(MARKET_MAX_STARS)} ⭐")
    bal = int(round(float(balances.get(uid, 0))))
    if ton > bal:
        raise MarketError("balance", "Недостаточно TON на балансе")
    mine = sum(1 for l in market["listings"].values() if l["seller"] == uid and l["status"] in ("active", "reserved"))
    if mine >= MARKET_MAX_LISTINGS:
        raise MarketError("too_many", f"Не больше {MARKET_MAX_LISTINGS} активных объявлений")
    balances[uid] = bal - ton
    save_balances()
    add_history(uid, "Расход (Маркет)", ton, f"Заморожено на Маркете за {stars} Stars")
    lid = _mk_next_id()
    market["listings"][lid] = {"id": lid, "seller": uid, "ton": ton, "stars": stars, "created": time.time(),
                               "status": "active", "deal": None}
    save_market()
    return market["listings"][lid]


def _mk_cancel_listing(uid, lid):
    l = market["listings"].get(str(lid))
    if not l or l["seller"] != uid:
        raise MarketError("not_found", "Объявление не найдено")
    if l["status"] != "active":
        raise MarketError("busy", "Объявление уже в сделке — сначала завершите её")
    l["status"] = "cancelled"
    l["closed"] = time.time()
    balances[uid] = int(round(float(balances.get(uid, 0)))) + l["ton"]
    save_balances()
    add_history(uid, "Возврат (Маркет)", l["ton"], "Объявление снято, TON возвращены")
    save_market()
    return l


def _mk_buy(uid, lid):
    l = market["listings"].get(str(lid))
    if not l or l["status"] not in ("active", "reserved"):
        raise MarketError("gone", "Объявление уже недоступно")
    if l["seller"] == uid:
        raise MarketError("own", "Нельзя купить своё объявление")
    if l["status"] == "reserved":
        raise MarketError("reserved", "Кто-то уже оформляет эту сделку")
    opened = sum(1 for d in market["deals"].values()
                 if d["buyer"] == uid and d["status"] in ("waiting_buyer", "buyer_paid", "dispute"))
    if opened >= MARKET_MAX_OPEN_DEALS:
        raise MarketError("too_many_deals", f"Не больше {MARKET_MAX_OPEN_DEALS} незавершённых сделок")
    did = _mk_next_id()
    now = time.time()
    d = {"id": did, "listing": l["id"], "seller": l["seller"], "buyer": uid, "ton": l["ton"], "stars": l["stars"],
         "created": now, "expires_at": now + MARKET_DEAL_SECONDS, "status": "waiting_buyer"}
    market["deals"][did] = d
    l["status"] = "reserved"
    l["deal"] = did
    save_market()
    _mk_notify(d["seller"],
               f"🛒 <b>Новая сделка #{did}</b>\n\n"
               f"Игрок {_mk_link(uid)} хочет купить ваши TON:\n{_mk_deal_line(d)}\n\n"
               f"{EMOJI_TIME} У покупателя <b>30 минут</b>, чтобы отправить вам <b>{_mk_money(d['stars'])}</b> {EMOJI_STAR} Stars.\n"
               f"Когда он отметит перевод, я пришлю кнопки подтверждения. TON уйдут покупателю только после вашего "
               f"подтверждения.", [[_mk_app_btn("📂 Открыть сделку", did)]])
    _mk_notify(uid,
               f"🛒 <b>Сделка #{did} создана</b>\n\n{_mk_deal_line(d)}\n\n"
               f"1️⃣ Отправьте <b>{_mk_money(d['stars'])}</b> {EMOJI_STAR} Stars продавцу {_mk_link(d['seller'])}\n"
               f"2️⃣ Нажмите «Я отправил Stars» в приложении\n"
               f"3️⃣ После подтверждения продавца TON придут вам на баланс\n\n"
               f"{EMOJI_TIME} Время на перевод: <b>30 минут</b>.", [[_mk_app_btn("📂 Открыть сделку", did)]])
    return d


def _mk_get_deal(uid, did):
    d = market["deals"].get(str(did))
    if not d or uid not in (d["buyer"], d["seller"]):
        raise MarketError("not_found", "Сделка не найдена")
    return d


def _mk_paid(uid, did):
    d = _mk_get_deal(uid, did)
    if d["buyer"] != uid:
        raise MarketError("forbidden", "Это действие для покупателя")
    if d["status"] != "waiting_buyer":
        raise MarketError("bad_state", "Сделка уже не ждёт перевода")
    if time.time() >= d["expires_at"]:
        _mk_expire_all()
        raise MarketError("expired", "Время на перевод вышло")
    d["status"] = "buyer_paid"
    d["paid_at"] = time.time()
    save_market()
    _mk_notify(d["seller"],
               f"💸 <b>Сделка #{did}</b>: покупатель {_mk_link(d['buyer'])} отметил, что отправил вам "
               f"<b>{_mk_money(d['stars'])}</b> {EMOJI_STAR} Stars.\n\n"
               f"Проверьте баланс Stars. Если всё пришло — подтвердите, и {_mk_money(d['ton'])} TON {EMOJI_GEM} уйдут покупателю.",
               [[{"text": "✅ Получил Stars", "callback_data": f"mk_recv:{did}"},
                 {"text": "⚠️ Не получил", "callback_data": f"mk_norecv:{did}"}],
                [_mk_app_btn("📂 Открыть сделку", did)]])
    return d


def _mk_cancel_deal(uid, did):
    d = _mk_get_deal(uid, did)
    if d["buyer"] != uid:
        raise MarketError("forbidden", "Отменить может только покупатель")
    if d["status"] != "waiting_buyer":
        raise MarketError("bad_state", "Сделку уже нельзя отменить")
    d["status"] = "cancelled"
    d["closed"] = time.time()
    _mk_unreserve(d)
    save_market()
    _mk_notify(d["seller"], f"↩️ Покупатель отменил сделку #{did}. Ваше объявление снова активно:\n{_mk_deal_line(d)}")
    return d


def _mk_pay_buyer(d, status, note):
    d["status"] = status
    d["closed"] = time.time()
    l = market["listings"].get(d["listing"])
    if l:
        l["status"] = "sold"
        l["closed"] = time.time()
    balances[d["buyer"]] = int(round(float(balances.get(d["buyer"], 0)))) + d["ton"]
    save_balances()
    add_history(d["buyer"], "Доход (Маркет)", d["ton"], note)
    save_market()


def _mk_confirm(uid, did):
    d = _mk_get_deal(uid, did)
    if d["seller"] != uid:
        raise MarketError("forbidden", "Подтвердить получение может только продавец")
    if d["status"] == "waiting_buyer":
        raise MarketError("buyer_not_paid", "Покупатель ещё не отметил перевод Stars")
    if d["status"] not in ("buyer_paid", "dispute"):
        raise MarketError("bad_state", "Сделка уже закрыта")
    _mk_pay_buyer(d, "completed", f"Покупка на Маркете: {d['stars']} Stars")
    _mk_notify(d["buyer"], f"🎉 <b>Сделка #{did} завершена!</b>\nПродавец подтвердил получение Stars. "
                           f"<b>+{_mk_money(d['ton'])}</b> TON {EMOJI_GEM} уже на вашем балансе.")
    return d


def _mk_dispute(uid, did):
    d = _mk_get_deal(uid, did)
    if d["seller"] != uid:
        raise MarketError("forbidden", "Только продавец может оспорить")
    if d["status"] != "buyer_paid":
        raise MarketError("bad_state", "Спор можно открыть, когда покупатель отметил перевод")
    d["status"] = "dispute"
    d["dispute_at"] = time.time()
    save_market()
    _mk_notify(d["buyer"], f"⚠️ По сделке #{did} продавец сообщил, что Stars не пришли. Проверьте перевод. "
                           f"Если вы точно отправили {_mk_money(d['stars'])} {EMOJI_STAR} — напишите владельцу бота и укажите номер сделки.")
    _mk_notify(OWNER_ID, f"🚨 <b>Спор по сделке #{did}</b>\n{_mk_deal_line(d)}\n"
                         f"Продавец: {_mk_link(d['seller'])}\nПокупатель: {_mk_link(d['buyer'])}\n\n"
                         f"Отдать TON покупателю: <code>/market_release {did}</code>\n"
                         f"Вернуть TON продавцу: <code>/market_refund {did}</code>")
    return d


# ---------- представления ----------
def _mk_listing_view(l, uid):
    return {"id": l["id"], "ton": l["ton"], "stars": l["stars"], "rate": round(_mk_rate(l["ton"], l["stars"]), 4),
            "seller": _mk_name(l["seller"]), "mine": l["seller"] == uid, "status": l["status"],
            "deal": l.get("deal"), "created": l["created"]}


def _mk_deal_view(d, uid):
    role = "buyer" if d["buyer"] == uid else "seller"
    other = d["seller"] if role == "buyer" else d["buyer"]
    return {"id": d["id"], "role": role, "status": d["status"], "ton": d["ton"], "stars": d["stars"],
            "rate": round(_mk_rate(d["ton"], d["stars"]), 4), "created": d["created"],
            "expires_at": d["expires_at"], "left": max(0, int(d["expires_at"] - time.time())),
            "paid_at": d.get("paid_at"), "closed": d.get("closed"),
            "counter": {"id": other, "name": _mk_name(other), "username": _mk_uname(other)}}


def _mk_config():
    return {"min_ton": MARKET_MIN_TON, "min_stars": MARKET_MIN_STARS, "max_listings": MARKET_MAX_LISTINGS,
            "deal_minutes": MARKET_DEAL_SECONDS // 60,
            "admin": {"id": OWNER_ID, "username": MARKET_ADMIN_USERNAME}}


async def api_market(request):
    uid, payload = await _web_auth(request)
    if uid is None:
        return web.json_response({"error": "unauthorized"}, status=401, headers=CORS)
    _mk_expire_all()
    action = payload.get("action", "list")
    bal = lambda: int(round(float(balances.get(uid, 0))))

    def ival(key):
        try:
            return int(payload.get(key, 0))
        except (TypeError, ValueError):
            return 0

    try:
        if action == "list":
            act = sorted((l for l in market["listings"].values() if l["status"] in ("active", "reserved")),
                         key=lambda l: l["created"], reverse=True)[:120]
            mine = sorted((l for l in market["listings"].values() if l["seller"] == uid),
                          key=lambda l: l["created"], reverse=True)[:30]
            deals = sorted((d for d in market["deals"].values() if uid in (d["buyer"], d["seller"])),
                           key=lambda d: d["created"], reverse=True)[:30]
            return web.json_response({"listings": [_mk_listing_view(l, uid) for l in act],
                                      "mine": [_mk_listing_view(l, uid) for l in mine],
                                      "deals": [_mk_deal_view(d, uid) for d in deals],
                                      "config": _mk_config(), "balance": bal()}, headers=CORS)
        if action == "create":
            l = _mk_create(uid, ival("ton"), ival("stars"))
            return web.json_response({"ok": True, "listing": _mk_listing_view(l, uid), "balance": bal()}, headers=CORS)
        if action == "cancel_listing":
            l = _mk_cancel_listing(uid, payload.get("id"))
            return web.json_response({"ok": True, "balance": bal()}, headers=CORS)
        if action == "buy":
            d = _mk_buy(uid, payload.get("id"))
            return web.json_response({"ok": True, "deal": _mk_deal_view(d, uid), "config": _mk_config()}, headers=CORS)
        if action == "deal":
            d = _mk_get_deal(uid, payload.get("id"))
            return web.json_response({"deal": _mk_deal_view(d, uid), "config": _mk_config(), "balance": bal()}, headers=CORS)
        if action == "paid":
            d = _mk_paid(uid, payload.get("id"))
        elif action == "cancel_deal":
            d = _mk_cancel_deal(uid, payload.get("id"))
        elif action == "confirm":
            d = _mk_confirm(uid, payload.get("id"))
        elif action == "dispute":
            d = _mk_dispute(uid, payload.get("id"))
        else:
            return web.json_response({"error": "bad_action"}, headers=CORS)
        return web.json_response({"ok": True, "deal": _mk_deal_view(d, uid), "balance": bal()}, headers=CORS)
    except MarketError as e:
        return web.json_response({"error": e.code, "message": e.message}, headers=CORS)


# ---------- кнопки в ЛС ----------
async def market_callback(update, context):
    query = update.callback_query
    data = query.data or ""
    uid = str(query.from_user.id)
    try:
        action, did = data.split(":", 1)
    except ValueError:
        await query.answer()
        return
    try:
        if action == "mk_recv":
            d = _mk_confirm(uid, did)
            await query.answer("✅ Готово, TON отправлены покупателю")
            text = f"✅ <b>Сделка #{did} завершена</b>\n{_mk_deal_line(d)}\nTON переданы покупателю."
        elif action == "mk_norecv":
            _mk_dispute(uid, did)
            await query.answer("Принято, владелец уведомлён")
            text = (f"⚠️ <b>Сделка #{did}: вы сообщили, что Stars не пришли.</b>\n"
                    f"Владелец уведомлён и разберётся. Если Stars придут — нажмите «Получил Stars» в приложении.")
        else:
            await query.answer()
            return
        try:
            await query.edit_message_text(text, parse_mode="HTML", disable_web_page_preview=True)
        except Exception:
            pass
    except MarketError as e:
        await query.answer(e.message, show_alert=True)


# ---------- команды владельца ----------
def _mk_admin_ok(update):
    return update.effective_user and update.effective_user.id == OWNER_ID


async def market_deals_command(update, context):
    if not update.message or not _mk_admin_ok(update):
        return
    _mk_expire_all()
    open_deals = [d for d in market["deals"].values() if d["status"] in ("waiting_buyer", "buyer_paid", "dispute")]
    if not open_deals:
        await update.message.reply_text("Открытых сделок на Маркете нет.")
        return
    label = {"waiting_buyer": "⏳ ждём перевода", "buyer_paid": "💸 покупатель оплатил", "dispute": "🚨 спор"}
    lines = ["<b>Открытые сделки Маркета</b>\n"]
    for d in sorted(open_deals, key=lambda x: x["created"]):
        lines.append(f"#{d['id']} · {label[d['status']]}\n{_mk_deal_line(d)}\n"
                     f"Продавец: {_mk_link(d['seller'])} · Покупатель: {_mk_link(d['buyer'])}\n"
                     f"<code>/market_release {d['id']}</code> · <code>/market_refund {d['id']}</code>\n")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)


async def market_release_command(update, context):
    if not update.message or not _mk_admin_ok(update):
        return
    if not context.args:
        await update.message.reply_text("Использование: /market_release <номер сделки>")
        return
    d = market["deals"].get(context.args[0].lstrip("#"))
    if not d:
        await update.message.reply_text("❌ Сделка не найдена.")
        return
    if d["status"] not in ("buyer_paid", "dispute"):
        await update.message.reply_text(f"❌ Нельзя: статус сделки «{d['status']}». Отдать TON можно только после отметки покупателя об оплате или при споре.")
        return
    _mk_pay_buyer(d, "released", f"Маркет: решение владельца по сделке #{d['id']}")
    _mk_notify(d["buyer"], f"✅ <b>Сделка #{d['id']}</b>: владелец подтвердил оплату. "
                           f"<b>+{_mk_money(d['ton'])}</b> TON {EMOJI_GEM} на вашем балансе.")
    _mk_notify(d["seller"], f"ℹ️ По сделке #{d['id']} владелец принял решение в пользу покупателя, TON переданы ему.")
    await update.message.reply_text(f"✅ Сделка #{d['id']}: {_mk_money(d['ton'])} TON отправлены покупателю {_mk_link(d['buyer'])}.",
                                    parse_mode="HTML", disable_web_page_preview=True)


async def market_refund_command(update, context):
    if not update.message or not _mk_admin_ok(update):
        return
    if not context.args:
        await update.message.reply_text("Использование: /market_refund <номер сделки>")
        return
    d = market["deals"].get(context.args[0].lstrip("#"))
    if not d:
        await update.message.reply_text("❌ Сделка не найдена.")
        return
    if d["status"] not in ("buyer_paid", "dispute", "waiting_buyer"):
        await update.message.reply_text(f"❌ Нельзя: статус сделки «{d['status']}».")
        return
    d["status"] = "refunded"
    d["closed"] = time.time()
    l = market["listings"].get(d["listing"])
    if l:
        l["status"] = "cancelled"
        l["closed"] = time.time()
    balances[d["seller"]] = int(round(float(balances.get(d["seller"], 0)))) + d["ton"]
    save_balances()
    add_history(d["seller"], "Возврат (Маркет)", d["ton"], f"Решение владельца по сделке #{d['id']}")
    save_market()
    _mk_notify(d["seller"], f"↩️ По сделке #{d['id']} владелец вернул вам {_mk_money(d['ton'])} TON {EMOJI_GEM}.")
    _mk_notify(d["buyer"], f"ℹ️ Сделка #{d['id']} закрыта владельцем, TON возвращены продавцу.")
    await update.message.reply_text(f"✅ Сделка #{d['id']}: {_mk_money(d['ton'])} TON возвращены продавцу.")

# =========================================================
# Эмодзи для миниприложения: отдаёт картинку премиум-эмодзи бота (EMOJI_GEM / EMOJI_STAR),
# чтобы в приложении был тот же значок, что и в сообщениях бота.
# =========================================================
EMOJI_ASSETS = {"gem": EMOJI_GEM_ID, "star": EMOJI_STAR_ID}
_emoji_cache = {}

async def _fetch_emoji(eid):
    token = TOKEN or _tg_token() or ""
    if not token:
        return None
    try:
        import aiohttp
        base = f"https://api.telegram.org/bot{token}"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as sess:
            async with sess.get(f"{base}/getCustomEmojiStickers",
                                params={"custom_emoji_ids": json.dumps([str(eid)])}) as r:
                data = await r.json()
            res = data.get("result") or []
            if not res:
                print("[emoji] стикер не найден:", data.get("description"))
                return None
            st = res[0]
            # анимированные/видео-эмодзи отдаём статичной миниатюрой
            if st.get("is_animated") or st.get("is_video"):
                fid = (st.get("thumbnail") or {}).get("file_id")
            else:
                fid = st.get("file_id")
            if not fid:
                return None
            async with sess.get(f"{base}/getFile", params={"file_id": fid}) as r:
                fp = ((await r.json()).get("result") or {}).get("file_path")
            if not fp:
                return None
            async with sess.get(f"https://api.telegram.org/file/bot{token}/{fp}") as r:
                body = await r.read()
        low = fp.lower()
        ctype = ("image/png" if low.endswith(".png") else "image/jpeg" if low.endswith((".jpg", ".jpeg"))
                 else "image/webp")
        return body, ctype
    except Exception as e:
        print("[emoji] ошибка загрузки:", e)
        return None


async def api_emoji(request):
    eid = EMOJI_ASSETS.get(request.query.get("n", "gem"))
    if not eid:
        return web.Response(status=404, headers=CORS)
    hit = _emoji_cache.get(eid)
    if hit is None:
        hit = await _fetch_emoji(eid)
        if hit:
            _emoji_cache[eid] = hit
    if not hit:
        return web.Response(status=404, headers=CORS)
    body, ctype = hit
    return web.Response(body=body, content_type=ctype,
                        headers={**CORS, "Cache-Control": "public, max-age=604800"})

async def run_webapp():
    app = web.Application()
    app.router.add_get("/", lambda r: web.FileResponse(os.path.join("webapp", "index.html")))
    app.router.add_get("/api/state", api_state)
    app.router.add_post("/api/bonus", api_bonus)
    app.router.add_post("/api/play", api_play)
    app.router.add_post("/api/mines", api_mines)
    app.router.add_post("/api/bj", api_bj)
    app.router.add_post("/api/crash", api_crash)
    app.router.add_post("/api/plinko", api_plinko)
    app.router.add_post("/api/hilo", api_hilo)
    app.router.add_post("/api/market", api_market)
    app.router.add_get("/api/emoji", api_emoji)
    app.router.add_post("/api/bank", api_bank)
    app.router.add_post("/api/exchange", api_exchange)
    app.router.add_post("/api/top", api_top)
    app.router.add_post("/api/profile", api_profile)
    app.router.add_static("/", "webapp")
    port = int(os.getenv("PORT", "8080"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    print(f"✅ Миниап запущен на порту {port}")

async def set_menu_button(application):
    await asyncio.sleep(2)
    try:
        await application.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="🎮 Играть", web_app=WebAppInfo(url=MINIAPP_URL))
        )
        print("✅ Кнопка миниапа установлена")
    except Exception as e:
        print("Не удалось установить кнопку меню:", e)

# =========================================================
# МИНИАП v2: БАНК, БИРЖА, ТОПЫ, ПРОФИЛЬ
# =========================================================

def _bank_lots_reduce(acc, amount):
    remaining = amount
    lots = sorted(acc.get("lots", []), key=lambda lot: lot.get("since", 0))
    new_lots = []
    for lot in lots:
        lot_amount = int(lot.get("amount", 0))
        taken = min(remaining, lot_amount)
        remaining -= taken
        if lot_amount > taken:
            new_lots.append({"amount": lot_amount - taken, "since": lot.get("since", 0)})
    acc["lots"] = new_lots

async def api_bank(request):
    uid, payload = await _web_auth(request)
    if uid is None:
        return web.json_response({"error": "unauthorized"}, status=401, headers=CORS)
    acc = get_bank_account(uid)
    action = payload.get("action", "info")

    if action == "info":
        return web.json_response({
            "deposit": int(acc.get("balance", 0)),
            "bank_total": bank_total(),
            "balance": int(round(float(balances.get(uid, 0)))),
        }, headers=CORS)

    try:
        amount = int(payload.get("amount", 0))
    except (TypeError, ValueError):
        amount = 0
    if amount <= 0:
        return web.json_response({"error": "bad_amount"}, headers=CORS)

    if action == "deposit":
        bal = int(round(float(balances.get(uid, 0))))
        if amount > bal:
            return web.json_response({"error": "balance"}, headers=CORS)
        balances[uid] = bal - amount
        acc["balance"] = int(acc.get("balance", 0)) + amount
        acc.setdefault("lots", []).append({"amount": amount, "since": time.time()})
        save_balances()
        save_bank()
        add_history(uid, "Расход (Банк)", amount, "Пополнение депозита (миниап)")
        return web.json_response({"ok": True, "deposit": int(acc["balance"]),
                                  "balance": int(round(float(balances[uid])))}, headers=CORS)

    if action == "withdraw":
        if amount > int(acc.get("balance", 0)):
            return web.json_response({"error": "no_deposit"}, headers=CORS)
        acc["balance"] = int(acc["balance"]) - amount
        acc["last_withdrawal"] = time.time()
        _bank_lots_reduce(acc, amount)
        balances[uid] = int(round(float(balances.get(uid, 0)))) + amount
        save_balances()
        save_bank()
        add_history(uid, "Доход (Банк)", amount, "Снятие с депозита (миниап)")
        return web.json_response({"ok": True, "deposit": int(acc["balance"]),
                                  "balance": int(round(float(balances[uid])))}, headers=CORS)

    return web.json_response({"error": "bad_action"}, headers=CORS)

async def api_exchange(request):
    uid, payload = await _web_auth(request)
    if uid is None:
        return web.json_response({"error": "unauthorized"}, status=401, headers=CORS)
    action = payload.get("action", "info")

    if action == "info":
        ev = pumpkin_event_active()
        return web.json_response({
            "price": int(pumpkin_price()),
            "stock_pct": round(pumpkin_market["stock"] / PUMPKIN_TOTAL * 100, 2),
            "stock_left": int(pumpkin_market["stock"]),
            "my_pumpkins": pumpkin_get(uid),
            "balance": int(round(float(balances.get(uid, 0)))),
            "event": {"name": ev["name"], "text": ev["text"], "mult": ev["mult"]} if ev else None,
        }, headers=CORS)

    try:
        raw = str(payload.get("amount", "")).strip().lower()
        n = pumpkin_get(uid) if raw in {"all", "все", "всё"} else int(float(raw or 0))
    except (TypeError, ValueError):
        n = 0

    if action == "buy":
        bal = int(round(float(balances.get(uid, 0))))
        if raw in {"all", "все", "всё"}:
            n = pumpkin_max_affordable(bal)
        if n <= 0:
            return web.json_response({"error": "bad_amount"}, headers=CORS)
        left = max(int(pumpkin_market["stock"]) - PUMPKIN_MIN_STOCK, 0)
        if n > left:
            n = left
        if n <= 0:
            return web.json_response({"error": "no_stock"}, headers=CORS)
        cost = pumpkin_buy_cost(n)
        if cost > bal:
            return web.json_response({"error": "balance"}, headers=CORS)
        balances[uid] = bal - cost
        pumpkin_market["stock"] -= n
        pumpkin_add(uid, n)
        pumpkin_record_price()
        add_history(uid, "Расход (Тыквы)", cost, f"Куплено тыкв: {n} (миниап)")
        return web.json_response({"ok": True, "bought": n, "cost": cost,
                                  "pumpkins": pumpkin_get(uid),
                                  "balance": int(round(float(balances[uid]))),
                                  "price": int(pumpkin_price())}, headers=CORS)

    if action == "sell":
        have = pumpkin_get(uid)
        if raw in {"all", "все", "всё"}:
            n = have
        if n <= 0 or n > have:
            return web.json_response({"error": "no_pumpkins"}, headers=CORS)
        value = pumpkin_sell_value(n)
        balances[uid] = int(round(float(balances.get(uid, 0)))) + value
        pumpkin_market["stock"] += n
        pumpkin_add(uid, -n)
        pumpkin_record_price()
        add_history(uid, "Доход (Тыквы)", value, f"Продано тыкв: {n} (миниап)")
        return web.json_response({"ok": True, "sold": n, "value": value,
                                  "pumpkins": pumpkin_get(uid),
                                  "balance": int(round(float(balances[uid]))),
                                  "price": int(pumpkin_price())}, headers=CORS)

    return web.json_response({"error": "bad_action"}, headers=CORS)

async def api_top(request):
    uid, payload = await _web_auth(request)
    if uid is None:
        return web.json_response({"error": "unauthorized"}, status=401, headers=CORS)

    top_bal = sorted(balances.items(), key=lambda it: float(it[1]), reverse=True)[:20]
    top_win = sorted(
        ((u, int(d.get("win", 0))) for u, d in user_stats.items() if int(d.get("win", 0)) > 0),
        key=lambda it: it[1], reverse=True
    )[:20]

    def name_of(u):
        return clean_name(user_stats.get(u, {}).get("name", ""), u)

    return web.json_response({
        "balances": [{"name": name_of(u), "value": int(round(float(v)))} for u, v in top_bal],
        "wins": [{"name": name_of(u), "value": v} for u, v in top_win],
    }, headers=CORS)

async def api_profile(request):
    uid, payload = await _web_auth(request)
    if uid is None:
        return web.json_response({"error": "unauthorized"}, status=401, headers=CORS)
    u_game = game_stats.get(uid, {"won": 0, "lost": 0})
    hist = list(history_data.get(uid, []))[-20:][::-1]
    acc = get_bank_account(uid)
    return web.json_response({
        "name": clean_name(user_stats.get(uid, {}).get("name", ""), uid),
        "id": uid,
        "balance": int(round(float(balances.get(uid, 0)))),
        "pumpkins": pumpkin_get(uid),
        "deposit": int(acc.get("balance", 0)),
        "wins": int(u_game.get("won", 0)),
        "losses": int(u_game.get("lost", 0)),
        "history": [{"type": h.get("type", ""), "amount": int(h.get("amount", 0)),
                     "details": str(h.get("details", ""))[:60],
                     "time": str(h.get("timestamp", ""))} for h in hist],
    }, headers=CORS)

_orig_post_init = post_init
async def post_init(application: Application):
    await _orig_post_init(application)
    asyncio.create_task(run_webapp())
    asyncio.create_task(set_menu_button(application))

# =========================================================
# УНИВЕРСАЛЬНАЯ ПРОВЕРКА initData (mini app) — замена _web_auth
# =========================================================
import hashlib as _hh, hmac as _hm, json as _js
from urllib.parse import parse_qsl as _pq, unquote as _uq

def _tg_token():
    import re as _r
    _pat = _r.compile(r"\d{8,}:[A-Za-z0-9_-]{30,}")
    for _n, _v in list(globals().items()):
        if isinstance(_v, str):
            _m = _pat.search(_v)
            if _m:
                return _m.group(0)
    try:
        _b = globals().get("bot")
        if _b is not None:
            return str(_b.bot.token)
    except Exception:
        pass
    return ""

def _split_raw(s):
    out = []
    for part in s.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
        else:
            k, v = part, ""
        if k:
            out.append((k, v))
    return out

def _check_init_data(init_data):
    if not init_data:
        return None
    for src in (init_data, _uq(init_data)):
        fields = {}
        for k, v in _split_raw(src):
            fields.setdefault(k, v)
        h = fields.pop("hash", None)
        if not h:
            continue
        for dec in (False, True):
            items = [(k, _uq(v)) for k, v in fields.items()] if dec else list(fields.items())
            dcs = "\n".join(k + "=" + v for k, v in sorted(items))
            secret = _hm.new(b"WebAppData", _tg_token().encode(), _hh.sha256).digest()
            calc = _hm.new(secret, dcs.encode(), _hh.sha256).hexdigest()
            if calc == h:
                try:
                    user = _js.loads(fields.get("user", "{}"))
                except Exception:
                    user = {}
                uid = user.get("id")
                if uid is not None:
                    return str(uid)
    return None

async def _web_auth(request):
    payload = {}
    uid = _check_init_data(request.rel_url.query.get("initData", ""))
    if uid is None:
        try:
            text = await request.text()
        except Exception:
            text = ""
        if text:
            try:
                data = _js.loads(text)
            except Exception:
                data = None
            if isinstance(data, dict):
                payload = data
                uid = _check_init_data(str(payload.get("initData", "") or ""))
            else:
                uid = _check_init_data(text)
    if uid is None:
        return None, {}
    return uid, (payload if isinstance(payload, dict) else {})

# =========================================================
# АВТОРИЗАЦИЯ MINI APP — финальная (токен + подпись initData)
# =========================================================
import re as _re, os as _os, hashlib as _hh, hmac as _hm, json as _js
from urllib.parse import unquote as _uq

def _tg_token():
    _pat = _re.compile(r"\b(\d{6,10}:[A-Za-z0-9_-]{25,50})\b")
    def _scan(obj, depth=0):
        if depth > 4:
            return None
        if isinstance(obj, str):
            m = _pat.search(obj)
            if m:
                return m.group(1)
        elif isinstance(obj, dict):
            for v in obj.values():
                r = _scan(v, depth + 1)
                if r:
                    return r
        elif isinstance(obj, (list, tuple, set)):
            for v in obj:
                r = _scan(v, depth + 1)
                if r:
                    return r
        return None
    for _v in list(globals().values()):
        try:
            _r1 = _scan(_v)
        except Exception:
            _r1 = None
        if _r1:
            return _r1
    for _k, _v in _os.environ.items():
        m = _pat.search(str(_v))
        if m:
            return m.group(1)
    try:
        _b = globals().get("bot")
        if _b is not None:
            return str(_b.bot.token)
    except Exception:
        pass
    return ""

def _check_init_data(init_data):
    if not init_data:
        return None
    for src in (init_data, _uq(init_data)):
        fields = {}
        for part in src.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
            else:
                k, v = part, ""
            if k and k not in fields:
                fields[k] = v
        h = fields.pop("hash", None)
        if not h:
            continue
        for dec in (False, True):
            items = [(k, _uq(v)) for k, v in fields.items()] if dec else list(fields.items())
            dcs = "\n".join(k + "=" + v for k, v in sorted(items))
            secret = _hm.new(b"WebAppData", _tg_token().encode(), _hh.sha256).digest()
            if _hm.new(secret, dcs.encode(), _hh.sha256).hexdigest() == h:
                try:
                    user = _js.loads(fields.get("user", "{}"))
                except Exception:
                    user = {}
                if user.get("id") is not None:
                    return str(user["id"])
    return None

async def _web_auth(request):
    payload = {}
    uid = _check_init_data(request.rel_url.query.get("initData", ""))
    if uid is None:
        try:
            text = await request.text()
        except Exception:
            text = ""
        if text:
            try:
                data = _js.loads(text)
            except Exception:
                data = None
            if isinstance(data, dict):
                payload = data
                uid = _check_init_data(str(payload.get("initData", "") or ""))
            else:
                uid = _check_init_data(text)
    if uid is None:
        return None, {}
    return uid, (payload if isinstance(payload, dict) else {})

print("[webauth] токен:", "найден ✅" if _tg_token() else "НЕ НАЙДЕН ❌ — нужен вид строки Application.builder().token(...)")

if __name__ == "__main__":
    main()
