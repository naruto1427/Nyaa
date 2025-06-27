import asyncio
import logging
import os
import re
import html

import requests
import feedparser
from bs4 import BeautifulSoup
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# ---------- CONFIG ----------
TOKEN = os.getenv("BOT_TOKEN")
TARGET_CHAT_ID = int(os.getenv("CHAT_ID"))  # e.g. -100xxxxxxxxxx
FEED_URL = "https://nyaa.si/?page=rss"

DEFAULT_INTERVAL = 1 * 20

# Filter only by uploader
ALLOWED_UPLOADERS = ["ToonsHub","varyg1001"]

# ---------- STATE ----------
posted_ids = set()
check_interval = DEFAULT_INTERVAL
periodic_task = None

# ---------- LOGGING ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


async def check_nyaa(context: ContextTypes.DEFAULT_TYPE):
    """
    Checks the Nyaa RSS feed and posts new torrents.
    """
    global posted_ids

    feed = feedparser.parse(FEED_URL)

    for entry in feed.entries:
        # Extract ID from URL
        m = re.search(r"/view/(\d+)", entry.link)
        if not m:
            continue
        torrent_id = m.group(1)

        if torrent_id in posted_ids:
            continue

        title = entry.title

        # Check uploader only
        uploader_match = False
        uploader = None
        uploader_match_obj = re.match(r"(.*?)", title)
        if uploader_match_obj:
            uploader = uploader_match_obj.group(1)
            uploader_match = uploader in ALLOWED_UPLOADERS

        if not uploader_match:
            logger.info(f"Skipped (uploader not matched): {title}")
            continue

        # Fetch extra info from page
        page = requests.get(entry.link)
        soup = BeautifulSoup(page.text, "html.parser")

        size_td = soup.find("td", string=re.compile(r"(GiB|MiB|TiB)"))
        size = size_td.text.strip() if size_td else "Unknown size"

        magnet_link = ""
        magnet_tag = soup.find("a", href=re.compile(r"^magnet:"))
        if magnet_tag:
            magnet_link = magnet_tag["href"]

        cat_tag = soup.find("a", href=re.compile(r"\?c="))
        category = cat_tag.text.strip() if cat_tag else "Unknown category"

        torrent_dl_link = f"https://nyaa.si/download/{torrent_id}.torrent"
        view_link = entry.link

        # Build message text
        message_text = (
            f"🎥 <b>{html.escape(title)}</b>\n"
            f"📦 Size: {size}\n"
            f"#{torrent_id} {category}"
        )

        # Create inline buttons
        buttons = [
            [
                InlineKeyboardButton("🔗 Download Torrent", url=torrent_dl_link),
                InlineKeyboardButton("🌐 View on Nyaa", url=view_link),
            ],
            [
                InlineKeyboardButton("🧲 Magnet", url=magnet_link),
            ],
        ]

        reply_markup = InlineKeyboardMarkup(buttons)

        await context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text=message_text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=reply_markup,
        )

        posted_ids.add(torrent_id)
        logger.info(f"Posted: {title}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Nyaa Bot running. I'll post new torrents to the channel."
    )


async def setinterval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global check_interval, periodic_task

    if not context.args:
        await update.message.reply_text("Usage: /setinterval <minutes>")
        return

    try:
        minutes = int(context.args[0])
        if minutes < 1:
            raise ValueError

        check_interval = minutes * 60

        if periodic_task:
            periodic_task.cancel()

        periodic_task = asyncio.create_task(periodic_checker(context.application))
        await update.message.reply_text(f"Interval set to {minutes} minutes.")

    except ValueError:
        await update.message.reply_text("Please provide a valid number of minutes.")


async def refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await check_nyaa(context)
    await update.message.reply_text("Manual refresh complete.")


async def periodic_checker(application):
    global check_interval

    while True:
        try:
            await check_nyaa(ContextTypes.DEFAULT_TYPE(application=application))
        except Exception as e:
            logger.error(f"Error in periodic check: {e}")
        await asyncio.sleep(check_interval)


async def main():
    global periodic_task

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setinterval", setinterval))
    app.add_handler(CommandHandler("refresh", refresh))

    periodic_task = asyncio.create_task(periodic_checker(app))

    await app.run_polling()


if __name__ == "__main__":
    import asyncio
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
