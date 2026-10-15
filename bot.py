"""
Awada Bot — Full Amharic Telegram Bot
Admin ID: 1766103612
Features: መዝሙር, Books, የመዝሙር ግጥሞች, አዳራሻችን, አስተያየት, Help
Includes HTTP ping server to stay alive on Render free tier
"""

import os
import asyncio
import threading
import psycopg
from psycopg.rows import dict_row
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, ContextTypes,
    filters
)
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]
ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "1766103612").split(",")]

# ─── States ────────────────────────────────────────────────────────────────
(
    MAIN_MENU,
    FEEDBACK_TEXT,
    ADMIN_MENU,
    ADMIN_ADD_SONG,
    ADMIN_ADD_SONG_AUDIO,
    ADMIN_ADD_BOOK,
    ADMIN_ADD_BOOK_FILE,
    ADMIN_ADD_LYRICS,
    ADMIN_ADD_LYRICS_PHOTO,
    ADMIN_ADD_HALL,
    ADMIN_REPLY_FEEDBACK,
    ADMIN_BROADCAST,
) = range(12)

# ─── Keyboards ─────────────────────────────────────────────────────────────

def main_keyboard():
    return ReplyKeyboardMarkup([
        ["🎵 መዝሙር", "📖 Books"],
        ["📝 የመዝሙር ግጥሞች", "🏛 አዳራሻችን"],
        ["💬 አስተያየት", "❓ Help"],
    ], resize_keyboard=True)


def admin_keyboard():
    return ReplyKeyboardMarkup([
        ["➕ መዝሙር ጨምር", "➕ Book ጨምር"],
        ["➕ ግጥም ጨምር", "➕ አዳራሻ ጨምር"],
        ["📨 ለሁሉም ላክ", "📋 አስተያየቶች"],
        ["🔙 ወደ ዋና ምናሌ"],
    ], resize_keyboard=True)


def back_keyboard():
    return ReplyKeyboardMarkup([["🔙 ተመለስ"]], resize_keyboard=True)


# ─── Database ──────────────────────────────────────────────────────────────

def get_db():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id         BIGINT PRIMARY KEY,
                username   TEXT,
                first_name TEXT,
                joined_at  TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS songs (
                id         SERIAL PRIMARY KEY,
                title      TEXT NOT NULL,
                file_id    TEXT NOT NULL,
                added_at   TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id         SERIAL PRIMARY KEY,
                title      TEXT NOT NULL,
                file_id    TEXT NOT NULL,
                added_at   TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lyrics (
                id         SERIAL PRIMARY KEY,
                title      TEXT NOT NULL,
                file_id    TEXT NOT NULL,
                added_at   TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hall_posts (
                id         SERIAL PRIMARY KEY,
                caption    TEXT,
                file_id    TEXT,
                file_type  TEXT,
                content    TEXT,
                added_at   TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id          SERIAL PRIMARY KEY,
                user_id     BIGINT NOT NULL,
                username    TEXT,
                first_name  TEXT,
                message     TEXT NOT NULL,
                replied     BOOLEAN DEFAULT FALSE,
                sent_at     TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()
    print("[db] Database initialized.")


def register_user(user):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO users (id, username, first_name)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
            username=EXCLUDED.username, first_name=EXCLUDED.first_name
        """, (user.id, user.username, user.first_name))
        conn.commit()


# ─── HTTP Keep-alive server ─────────────────────────────────────────────────

class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Awada Bot is running!")

    def log_message(self, format, *args):
        pass


def start_ping_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    print(f"[ping] HTTP server on port {port}")
    server.serve_forever()


# ─── Helpers ───────────────────────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ─── Start ─────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user)
    name = update.effective_user.first_name or "እንኳን ደህና መጡ"
    await update.message.reply_text(
        f"ሰላም {name}! 👋\nወደ አዋዳ ቤተ ክርስቲያን ቦቱ እንኳን ደህና መጡ።\nከታች ካሉት ምናሌዎች ይምረጡ።",
        reply_markup=main_keyboard()
    )
    return MAIN_MENU


# ─── Main Menu Handler ─────────────────────────────────────────────────────

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    register_user(update.effective_user)

    if text == "🎵 መዝሙር":
        return await show_songs(update, context)
    elif text == "📖 Books":
        return await show_books(update, context)
    elif text == "📝 የመዝሙር ግጥሞች":
        return await show_lyrics(update, context)
    elif text == "🏛 አዳራሻችን":
        return await show_hall(update, context)
    elif text == "💬 አስተያየት":
        await update.message.reply_text(
            "💬 አስተያየትዎን ይፃፉ:\n(ወደ ኋላ ለመመለስ 🔙 ተመለስ ይጫኑ)",
            reply_markup=back_keyboard()
        )
        return FEEDBACK_TEXT
    elif text == "❓ Help":
        await update.message.reply_text(
            "❓ *እርዳታ*\n\n"
            "🎵 *መዝሙር* — የቤተ ክርስቲያን መዝሙሮችን ያዳምጡ\n"
            "📖 *Books* — መጻሕፍትን ያንብቡ\n"
            "📝 *የመዝሙር ግጥሞች* — የመዝሙር ግጥሞችን ይመልከቱ\n"
            "🏛 *አዳራሻችን* — ስለ አዳራሻችን መረጃ\n"
            "💬 *አስተያየት* — አስተያየትዎን ያካፍሉ\n\n"
            "ለተጨማሪ መረጃ ወደ አስተዳዳሪ ይደርሱ።",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
        return MAIN_MENU

    return MAIN_MENU


# ─── Songs ─────────────────────────────────────────────────────────────────

async def show_songs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with get_db() as conn:
        songs = conn.execute("SELECT * FROM songs ORDER BY added_at DESC").fetchall()
    if not songs:
        await update.message.reply_text("😔 እስካሁን ምንም መዝሙር አልተጨመረም።", reply_markup=main_keyboard())
        return MAIN_MENU
    await update.message.reply_text(f"🎵 *{len(songs)} መዝሙሮች አሉ:*", parse_mode="Markdown")
    for song in songs:
        await update.message.reply_audio(audio=song["file_id"], title=song["title"], caption=f"🎵 {song['title']}")
    await update.message.reply_text("ሌላ ለማዳመጥ ከዋና ምናሌ ይምረጡ።", reply_markup=main_keyboard())
    return MAIN_MENU


# ─── Books ─────────────────────────────────────────────────────────────────

async def show_books(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with get_db() as conn:
        books = conn.execute("SELECT * FROM books ORDER BY added_at DESC").fetchall()
    if not books:
        await update.message.reply_text("😔 እስካሁን ምንም መጽሐፍ አልተጨመረም።", reply_markup=main_keyboard())
        return MAIN_MENU
    await update.message.reply_text(f"📖 *{len(books)} መጻሕፍት አሉ:*", parse_mode="Markdown")
    for book in books:
        await update.message.reply_document(document=book["file_id"], caption=f"📖 {book['title']}")
    await update.message.reply_text("ሌላ ለማንበብ ከዋና ምናሌ ይምረጡ።", reply_markup=main_keyboard())
    return MAIN_MENU


# ─── Lyrics ────────────────────────────────────────────────────────────────

async def show_lyrics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with get_db() as conn:
        lyrics = conn.execute("SELECT * FROM lyrics ORDER BY added_at DESC").fetchall()
    if not lyrics:
        await update.message.reply_text("😔 እስካሁን ምንም ግጥም አልተጨመረም።", reply_markup=main_keyboard())
        return MAIN_MENU
    await update.message.reply_text(f"📝 *{len(lyrics)} ግጥሞች አሉ:*", parse_mode="Markdown")
    for lyric in lyrics:
        await update.message.reply_photo(photo=lyric["file_id"], caption=f"📝 {lyric['title']}")
    await update.message.reply_text("ሌላ ለማየት ከዋና ምናሌ ይምረጡ።", reply_markup=main_keyboard())
    return MAIN_MENU


# ─── Hall ──────────────────────────────────────────────────────────────────

async def show_hall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with get_db() as conn:
        posts = conn.execute("SELECT * FROM hall_posts ORDER BY added_at DESC LIMIT 10").fetchall()
    if not posts:
        await update.message.reply_text("😔 እስካሁን ምንም መረጃ አልተጨመረም።", reply_markup=main_keyboard())
        return MAIN_MENU
    await update.message.reply_text("🏛 *አዳራሻችን:*", parse_mode="Markdown")
    for post in posts:
        try:
            if post["file_type"] == "photo" and post["file_id"]:
                await update.message.reply_photo(photo=post["file_id"], caption=post["caption"] or "")
            elif post["file_type"] == "video" and post["file_id"]:
                await update.message.reply_video(video=post["file_id"], caption=post["caption"] or "")
            elif post["content"]:
                await update.message.reply_text(post["content"])
        except Exception as e:
            print(f"[hall] Error: {e}")
    await update.message.reply_text("ለተጨማሪ መረጃ ያግኙን።", reply_markup=main_keyboard())
    return MAIN_MENU


# ─── Feedback ──────────────────────────────────────────────────────────────

async def feedback_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    if text == "🔙 ተመለስ":
        await update.message.reply_text("ወደ ዋና ምናሌ ተመልሰዋል።", reply_markup=main_keyboard())
        return MAIN_MENU
    with get_db() as conn:
        conn.execute(
            "INSERT INTO feedback (user_id, username, first_name, message) VALUES (%s, %s, %s, %s)",
            (user.id, user.username, user.first_name, text)
        )
        conn.commit()
        result = conn.execute(
            "SELECT id FROM feedback WHERE user_id=%s ORDER BY sent_at DESC LIMIT 1", (user.id,)
        ).fetchone()
        feedback_id = result["id"] if result else 0

    username_str = f"@{user.username}" if user.username else "ምንም username የለም"
    admin_msg = (
        f"📨 *አዲስ አስተያየት!*\n\n"
        f"👤 ስም: {user.first_name}\n"
        f"🔗 Username: {username_str}\n"
        f"🆔 ID: `{user.id}`\n\n"
        f"💬 መልእክት:\n{text}"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("↩️ መልስ ላክ", callback_data=f"reply_{feedback_id}_{user.id}")]
    ])
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=admin_msg, parse_mode="Markdown", reply_markup=keyboard)
        except Exception as e:
            print(f"[feedback] Could not notify admin {admin_id}: {e}")
    await update.message.reply_text("✅ አስተያየትዎ ተልኳል! ለምላሽ ትንሽ ይጠብቁ።", reply_markup=main_keyboard())
    return MAIN_MENU


# ─── Admin Reply ───────────────────────────────────────────────────────────

async def admin_reply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    parts = query.data.split("_")
    feedback_id = parts[1]
    user_id = int(parts[2])
    context.user_data["reply_to_user_id"] = user_id
    context.user_data["reply_to_feedback_id"] = feedback_id
    await query.message.reply_text(f"↩️ ለ ID {user_id} መልስ ይፃፉ:", reply_markup=back_keyboard())
    return ADMIN_REPLY_FEEDBACK


async def admin_send_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 ተመለስ":
        await update.message.reply_text("ተሰርዟል።", reply_markup=admin_keyboard())
        return ADMIN_MENU
    user_id = context.user_data.get("reply_to_user_id")
    feedback_id = context.user_data.get("reply_to_feedback_id")
    if not user_id:
        await update.message.reply_text("ስህተት።", reply_markup=admin_keyboard())
        return ADMIN_MENU
    try:
        await context.bot.send_message(chat_id=user_id, text=f"📩 *ከአስተዳዳሪ መልስ:*\n\n{text}", parse_mode="Markdown")
        with get_db() as conn:
            conn.execute("UPDATE feedback SET replied=TRUE WHERE id=%s", (feedback_id,))
            conn.commit()
        await update.message.reply_text("✅ መልሱ ተልኳል!", reply_markup=admin_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ አልተሳካም: {e}", reply_markup=admin_keyboard())
    return ADMIN_MENU


# ─── Admin Menu ────────────────────────────────────────────────────────────

async def admin_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🔙 ወደ ዋና ምናሌ":
        await update.message.reply_text("ወደ ዋና ምናሌ ተመልሰዋል።", reply_markup=main_keyboard())
        return MAIN_MENU
    elif text == "➕ መዝሙር ጨምር":
        await update.message.reply_text("🎵 የዘፈኑን ስም ይፃፉ:", reply_markup=back_keyboard())
        return ADMIN_ADD_SONG
    elif text == "➕ Book ጨምር":
        await update.message.reply_text("📖 የመጽሐፉን ስም ይፃፉ:", reply_markup=back_keyboard())
        return ADMIN_ADD_BOOK
    elif text == "➕ ግጥም ጨምር":
        await update.message.reply_text("📝 የግጥሙን ስም ይፃፉ:", reply_markup=back_keyboard())
        return ADMIN_ADD_LYRICS
    elif text == "➕ አዳራሻ ጨምር":
        await update.message.reply_text("🏛 ጽሑፍ፣ ፎቶ ወይም ቪዲዮ ይላኩ:", reply_markup=back_keyboard())
        return ADMIN_ADD_HALL
    elif text == "📋 አስተያየቶች":
        with get_db() as conn:
            feedbacks = conn.execute("SELECT * FROM feedback ORDER BY sent_at DESC LIMIT 20").fetchall()
        if not feedbacks:
            await update.message.reply_text("😔 ምንም አስተያየት የለም።", reply_markup=admin_keyboard())
        else:
            await update.message.reply_text(f"📋 *{len(feedbacks)} አስተያየቶች:*", parse_mode="Markdown")
            for fb in feedbacks:
                replied = "✅" if fb["replied"] else "⏳"
                username_str = f"@{fb['username']}" if fb["username"] else "—"
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("↩️ መልስ ላክ", callback_data=f"reply_{fb['id']}_{fb['user_id']}")]
                ]) if not fb["replied"] else None
                await update.message.reply_text(
                    f"{replied} *{fb['first_name']}* ({username_str})\n`{fb['message']}`",
                    parse_mode="Markdown", reply_markup=keyboard
                )
        return ADMIN_MENU
    elif text == "📨 ለሁሉም ላክ":
        await update.message.reply_text("📨 ለሁሉም ተጠቃሚዎች የሚላከውን መልእክት ይፃፉ:", reply_markup=back_keyboard())
        return ADMIN_BROADCAST

    return ADMIN_MENU


# ─── Admin Add Song ────────────────────────────────────────────────────────

async def admin_add_song_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 ተመለስ":
        await update.message.reply_text("ተሰርዟል።", reply_markup=admin_keyboard())
        return ADMIN_MENU
    context.user_data["song_title"] = update.message.text
    await update.message.reply_text("🎵 አሁን ኦዲዮውን ይላኩ:")
    return ADMIN_ADD_SONG_AUDIO


async def admin_add_song_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text and update.message.text == "🔙 ተመለስ":
        await update.message.reply_text("ተሰርዟል።", reply_markup=admin_keyboard())
        return ADMIN_MENU
    if not update.message.audio and not update.message.voice:
        await update.message.reply_text("❌ እባክዎ ኦዲዮ ፋይል ይላኩ።")
        return ADMIN_ADD_SONG_AUDIO
    file_id = update.message.audio.file_id if update.message.audio else update.message.voice.file_id
    title = context.user_data.get("song_title", "ያልታወቀ")
    with get_db() as conn:
        conn.execute("INSERT INTO songs (title, file_id) VALUES (%s, %s)", (title, file_id))
        conn.commit()
    await update.message.reply_text(f"✅ '{title}' ተጨምሯል!", reply_markup=admin_keyboard())
    return ADMIN_MENU


# ─── Admin Add Book ────────────────────────────────────────────────────────

async def admin_add_book_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 ተመለስ":
        await update.message.reply_text("ተሰርዟል።", reply_markup=admin_keyboard())
        return ADMIN_MENU
    context.user_data["book_title"] = update.message.text
    await update.message.reply_text("📖 አሁን PDF ፋይሉን ይላኩ:")
    return ADMIN_ADD_BOOK_FILE


async def admin_add_book_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text and update.message.text == "🔙 ተመለስ":
        await update.message.reply_text("ተሰርዟል።", reply_markup=admin_keyboard())
        return ADMIN_MENU
    if not update.message.document:
        await update.message.reply_text("❌ እባክዎ PDF ፋይል ይላኩ።")
        return ADMIN_ADD_BOOK_FILE
    file_id = update.message.document.file_id
    title = context.user_data.get("book_title", "ያልታወቀ")
    with get_db() as conn:
        conn.execute("INSERT INTO books (title, file_id) VALUES (%s, %s)", (title, file_id))
        conn.commit()
    await update.message.reply_text(f"✅ '{title}' ተጨምሯል!", reply_markup=admin_keyboard())
    return ADMIN_MENU


# ─── Admin Add Lyrics ──────────────────────────────────────────────────────

async def admin_add_lyrics_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 ተመለስ":
        await update.message.reply_text("ተሰርዟል።", reply_markup=admin_keyboard())
        return ADMIN_MENU
    context.user_data["lyrics_title"] = update.message.text
    await update.message.reply_text("📝 አሁን የግጥሙን ፎቶ ይላኩ:")
    return ADMIN_ADD_LYRICS_PHOTO


async def admin_add_lyrics_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text and update.message.text == "🔙 ተመለስ":
        await update.message.reply_text("ተሰርዟል።", reply_markup=admin_keyboard())
        return ADMIN_MENU
    if not update.message.photo:
        await update.message.reply_text("❌ እባክዎ ፎቶ ይላኩ።")
        return ADMIN_ADD_LYRICS_PHOTO
    file_id = update.message.photo[-1].file_id
    title = context.user_data.get("lyrics_title", "ያልታወቀ")
    with get_db() as conn:
        conn.execute("INSERT INTO lyrics (title, file_id) VALUES (%s, %s)", (title, file_id))
        conn.commit()
    await update.message.reply_text(f"✅ '{title}' ተጨምሯል!", reply_markup=admin_keyboard())
    return ADMIN_MENU


# ─── Admin Add Hall ────────────────────────────────────────────────────────

async def admin_add_hall_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text and update.message.text == "🔙 ተመለስ":
        await update.message.reply_text("ተሰርዟል።", reply_markup=admin_keyboard())
        return ADMIN_MENU
    with get_db() as conn:
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
            caption = update.message.caption or ""
            conn.execute("INSERT INTO hall_posts (caption, file_id, file_type) VALUES (%s, %s, %s)", (caption, file_id, "photo"))
        elif update.message.video:
            file_id = update.message.video.file_id
            caption = update.message.caption or ""
            conn.execute("INSERT INTO hall_posts (caption, file_id, file_type) VALUES (%s, %s, %s)", (caption, file_id, "video"))
        elif update.message.text:
            conn.execute("INSERT INTO hall_posts (content, file_type) VALUES (%s, %s)", (update.message.text, "text"))
        else:
            await update.message.reply_text("❌ ጽሑፍ፣ ፎቶ ወይም ቪዲዮ ብቻ ነው የሚቀበለው።")
            return ADMIN_ADD_HALL
        conn.commit()
    await update.message.reply_text("✅ ተጨምሯል!", reply_markup=admin_keyboard())
    return ADMIN_MENU


# ─── Admin Broadcast ───────────────────────────────────────────────────────

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 ተመለስ":
        await update.message.reply_text("ተሰርዟል።", reply_markup=admin_keyboard())
        return ADMIN_MENU
    with get_db() as conn:
        users = conn.execute("SELECT id FROM users").fetchall()
    sent = failed = 0
    for user in users:
        try:
            await context.bot.send_message(chat_id=user["id"], text=text)
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(
        f"✅ ተልኳል!\n📤 ደርሷል: {sent}\n❌ አልደረሰም: {failed}",
        reply_markup=admin_keyboard()
    )
    return ADMIN_MENU


# ─── Admin Command ─────────────────────────────────────────────────────────

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ ይህ ትዕዛዝ ለአስተዳዳሪዎች ብቻ ነው።")
        return MAIN_MENU
    await update.message.reply_text("👨‍💼 *አስተዳዳሪ ምናሌ*", parse_mode="Markdown", reply_markup=admin_keyboard())
    return ADMIN_MENU


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ተሰርዟል።", reply_markup=main_keyboard())
    return MAIN_MENU


# ─── Main ──────────────────────────────────────────────────────────────────

def main():
    init_db()

    # Start ping server in background thread
    threading.Thread(target=start_ping_server, daemon=True).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("admin", admin_command),
        ],
        states={
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler)],
            FEEDBACK_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, feedback_text)],
            ADMIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_menu_handler)],
            ADMIN_ADD_SONG: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_song_title)],
            ADMIN_ADD_SONG_AUDIO: [MessageHandler(filters.AUDIO | filters.VOICE | filters.TEXT, admin_add_song_audio)],
            ADMIN_ADD_BOOK: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_book_title)],
            ADMIN_ADD_BOOK_FILE: [MessageHandler(filters.Document.ALL | filters.TEXT, admin_add_book_file)],
            ADMIN_ADD_LYRICS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_lyrics_title)],
            ADMIN_ADD_LYRICS_PHOTO: [MessageHandler(filters.PHOTO | filters.TEXT, admin_add_lyrics_photo)],
            ADMIN_ADD_HALL: [MessageHandler(filters.PHOTO | filters.VIDEO | filters.TEXT, admin_add_hall_post)],
            ADMIN_REPLY_FEEDBACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_send_reply)],
            ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(admin_reply_callback, pattern="^reply_"))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
