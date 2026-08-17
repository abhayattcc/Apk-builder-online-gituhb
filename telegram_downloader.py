#!/usr/bin/env python3
"""
Telegram Media Downloader (GitHub Actions ready)
------------------------------------------------
Downloads video / photo / document from a public Telegram link.

Usage (local):
    export TELEGRAM_API_ID=39250553
    export TELEGRAM_API_HASH=3624e420a0a197cf5fc620605ce4e929
    python telegram_downloader.py "https://t.me/channel/123"

Usage (GitHub Actions):
    API_ID and API_HASH are passed as secrets.
    Link is passed as workflow input.
"""

from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChannelPrivateError, MessageIdInvalidError
from telethon.sessions import StringSession
import asyncio
import os
import re
import sys
from pathlib import Path

# Read from environment (safe for GitHub Actions secrets)
API_ID = int(os.getenv("TELEGRAM_API_ID", "39250553"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "3624e420a0a197cf5fc620605ce4e929")
SESSION_STRING = os.getenv("TELEGRAM_SESSION", "")  # optional string session
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")


def parse_telegram_link(link: str):
    """Extract username/channel-id and message-id from t.me links."""
    link = link.strip()
    patterns = [
        r"(?:https?://)?t\.me/c/(\d+)/(\d+)",          # private style
        r"(?:https?://)?t\.me/([a-zA-Z0-9_]+)/(\d+)",  # public username
    ]
    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            return match.group(1), int(match.group(2))
    raise ValueError(
        "Invalid Telegram link.\n"
        "Expected format: https://t.me/channelname/123"
    )


def progress_callback(current, total):
    if total and total > 0:
        percent = current * 100 / total
        bar_len = 30
        filled = int(bar_len * current // total)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(
            f"\r  [{bar}] {percent:5.1f}%  "
            f"({current/1024/1024:.1f} / {total/1024/1024:.1f} MB)",
            end="",
            flush=True,
        )
        if current >= total:
            print()


async def download_from_link(link: str):
    if not API_ID or not API_HASH:
        print("❌ TELEGRAM_API_ID or TELEGRAM_API_HASH is missing.")
        print("   Set them as environment variables or GitHub Secrets.")
        sys.exit(1)

    # Prefer string session (good for CI), otherwise create a normal session file
    if SESSION_STRING:
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        print("Using StringSession...")
    else:
        client = TelegramClient("tg_session", API_ID, API_HASH)
        print("Using file session (tg_session.session)...")

    print("Connecting to Telegram...")
    await client.start()

    try:
        entity_part, msg_id = parse_telegram_link(link)
        print(f"Parsed → entity: {entity_part} | message id: {msg_id}")

        if entity_part.isdigit():
            entity = await client.get_entity(int(entity_part))
        else:
            entity = await client.get_entity(entity_part)

        title = getattr(entity, "title", None) or getattr(entity, "username", entity_part)
        print(f"Channel/Chat: {title}")

        message = await client.get_messages(entity, ids=msg_id)

        if not message:
            print("❌ Message not found or inaccessible.")
            return False

        if not message.media:
            print("ℹ️  This message has no downloadable media.")
            if message.message:
                print(f"Text: {message.message[:300]}")
            return False

        Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)

        print("Media found. Starting download...")
        if message.message:
            print(f"Caption: {(message.message or '')[:100]}...")

        path = await message.download_media(
            file=DOWNLOAD_DIR,
            progress_callback=progress_callback,
        )

        if path:
            print(f"\n✅ Successfully downloaded → {path}")
            # Write path to a file so GitHub Actions can find it
            with open("downloaded_file.txt", "w") as f:
                f.write(str(path))
            return True
        else:
            print("\n❌ Download failed.")
            return False

    except ValueError as e:
        print(f"❌ {e}")
        return False
    except ChannelPrivateError:
        print("❌ Channel is private. Join it first with the account used for the session.")
        return False
    except MessageIdInvalidError:
        print("❌ Invalid message ID.")
        return False
    except FloodWaitError as e:
        print(f"❌ Rate limited. Wait {e.seconds} seconds.")
        return False
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        return False
    finally:
        await client.disconnect()
        print("Disconnected.")


def main():
    if len(sys.argv) > 1:
        link = sys.argv[1]
    else:
        link = os.getenv("TELEGRAM_LINK", "").strip()
        if not link:
            link = input("Paste Telegram link: ").strip()

    if not link:
        print("No link provided.")
        sys.exit(1)

    print(f"Link: {link}")
    success = asyncio.run(download_from_link(link))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
