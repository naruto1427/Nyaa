import os
import json
import asyncio
import feedparser
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
TARGET_CHAT_ID = int(os.getenv("TARGET_CHAT_ID"))  # group, channel, or user ID

if not BOT_TOKEN or not TARGET_CHAT_ID:
    raise Exception("BOT_TOKEN and TARGET_CHAT_ID must be set in environment variables.")

# --- File helpers ---
def load_json(filename, default_value):
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return default_value

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

# Filenames
sources_file = "sources.json"
posted_file = "posted.json"
config_file = "config.json"

# Load on startup
sources = load_json(sources_file, {})
posted_links = load_json(posted_file, [])
config = load_json(config_file, {"quality": ""})

# --- Commands ---
async def add_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        return await update.message.reply_text("Usage: /addsource <name> <rss_url>")
    name, url = context.args[0], context.args[1]
    sources[name] = url
    save_json(sources_file, sources)
    await update.message.reply_text(f"✅ Source `{name}` added.")

async def remove_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /removesource <name>")
    name = context.args[0]
    if name in sources:
        del sources[name]
        save_json(sources_file, sources)
        await update.message.reply_text(f"🗑️ Source `{name}` removed.")
    else:
        await update.message.reply_text(f"❌ Source `{name}` not found.")

async def list_sources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not sources:
        return await update.message.reply_text("No sources added.")
    text = "\n".join(f"• `{name}`: {url}" for name, url in sources.items())
    await update.message.reply_text(text)

async def set_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /setquality <value>")
    config["quality"] = context.args[0].lower()
    save_json(config_file, config)
    await update.message.reply_text(f"✅ Quality filter set to `{config['quality']}`.")

async def test_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "✅ Test message from your RSS bot!"
    await context.bot.send_message(chat_id=TARGET_CHAT_ID, text=msg)
    await update.message.reply_text("Test message sent.")

# --- RSS polling loop ---
async def poll_feeds(app):
    while True:
        logging.info("Checking feeds...")
        for name, url in sources.items():
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.title
                link = entry.link
                if config["quality"] and config["quality"] not in title.lower():
                    continue
                if link in posted_links:
                    continue
                message = f"🎬 <b>{title}</b>\n🔗 <a href='{link}'>Download</a>"
                try:
                    await app.bot.send_message(
                        chat_id=TARGET_CHAT_ID,
                        text=message,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                    posted_links.append(link)
                    save_json(posted_file, posted_links)
                    logging.info(f"Posted: {title}")
                except Exception as e:
                    logging.error(f"Error sending message: {e}")
        await asyncio.sleep(300)  # 5 minutes

# --- Main ---
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("addsource", add_source))
    app.add_handler(CommandHandler("removesource", remove_source))
    app.add_handler(CommandHandler("listsources", list_sources))
    app.add_handler(CommandHandler("setquality", set_quality))
    app.add_handler(CommandHandler("testpost", test_post))

    asyncio.create_task(poll_feeds(app))
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.get_event_loop().run_until_complete(main())
