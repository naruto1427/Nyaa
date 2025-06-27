import os
import asyncio
import feedparser
from telegram import Bot

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

bot = Bot(BOT_TOKEN)

UPLOADERS = ["ToonsHub", "varyg1001", "SubsPlease"]
QUALITY = "1080p"

# Track already-posted torrents
seen_links = set()

async def check_feeds():
    while True:
        for uploader in UPLOADERS:
            rss_url = (
                f"https://nyaa.si/?page=rss&q={QUALITY}"
                f"&uploader={uploader}&c=1_2"
            )
            feed = feedparser.parse(rss_url)
            
            for entry in feed.entries:
                torrent_page = entry.link
                infohash = getattr(entry, "nyaa_infohash", None)
                magnet_link = f"magnet:?xt=urn:btih:{infohash}" if infohash else "Unavailable"

                # Build direct .torrent link
                torrent_id = torrent_page.split("/")[-1]
                torrent_file_link = f"https://nyaa.si/download/{torrent_id}.torrent"

                if torrent_page not in seen_links:
                    seen_links.add(torrent_page)

                    text = (
                        f"**{entry.title}**\n"
                        f"Size: {entry.get('nyaa_size', 'Unknown')}\n"
                        f"Seeders: {entry.get('nyaa_seeders', '0')}\n"
                        f"Leechers: {entry.get('nyaa_leechers', '0')}\n\n"
                        f"[Torrent Page]({torrent_page})\n"
                        f"[Magnet Link]({magnet_link})\n"
                        f"[Torrent File (.torrent)]({torrent_file_link})"
                    )

                    try:
                        await bot.send_message(
                            chat_id=CHANNEL_ID,
                            text=text,
                            parse_mode="Markdown",
                            disable_web_page_preview=True
                        )
                        print(f"Posted: {entry.title}")
                    except Exception as e:
                        print(f"Error posting: {e}")
        
        await asyncio.sleep(30)  # 5 minutes

if __name__ == "__main__":
    asyncio.run(check_feeds())
