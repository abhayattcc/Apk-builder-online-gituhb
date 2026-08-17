import streamlit as st
import asyncio
import re
import tempfile
from pathlib import Path
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    FloodWaitError,
    ChannelPrivateError,
    MessageIdInvalidError,
)

st.set_page_config(
    page_title="Telegram Video Downloader",
    page_icon="📥",
    layout="centered",
)

st.markdown("""
<style>
    .stDownloadButton > button {
        background: linear-gradient(90deg, #38bdf8, #818cf8) !important;
        color: #0b0f19 !important;
        font-weight: 600 !important;
        border: none !important;
    }
    .title {
        text-align: center;
        font-size: 1.9rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .subtitle {
        text-align: center;
        color: #94a3b8;
        margin-bottom: 1.8rem;
        font-size: 0.95rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="title">📥 Telegram Video Downloader</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Single Python page • Enter credentials → paste link → download</p>', unsafe_allow_html=True)

# ========== FORM ==========
with st.form("form"):
    st.markdown("#### 1. Your Telegram API Credentials")
    c1, c2 = st.columns(2)
    with c1:
        api_id = st.text_input("API ID", placeholder="12345678")
    with c2:
        api_hash = st.text_input("API Hash", placeholder="your_api_hash_here", type="password")

    st.markdown("#### 2. Session String (recommended)")
    session_string = st.text_input(
        "StringSession (leave empty only for first local test)",
        placeholder="1BVtsOHwBu...",
        type="password",
        help="Generate once on your computer (see instructions below)"
    )

    st.markdown("#### 3. Telegram Link")
    link = st.text_input(
        "Paste the Telegram post link",
        value="https://t.me/odiamahabharat/154",
        placeholder="https://t.me/channelname/123"
    )

    submit = st.form_submit_button("🚀 Download Video", use_container_width=True)


def parse_link(link: str):
    link = link.strip()
    for pattern in [
        r"(?:https?://)?t\.me/c/(\d+)/(\d+)",
        r"(?:https?://)?t\.me/([a-zA-Z0-9_]+)/(\d+)",
    ]:
        m = re.search(pattern, link)
        if m:
            return m.group(1), int(m.group(2))
    raise ValueError("Invalid link. Example: https://t.me/channel/123")


async def do_download(api_id: int, api_hash: str, session_str: str, link: str, status):
    if session_str:
        client = TelegramClient(StringSession(session_str), api_id, api_hash)
    else:
        client = TelegramClient(StringSession(), api_id, api_hash)

    status.info("Connecting to Telegram...")
    await client.connect()

    if not await client.is_user_authorized():
        await client.disconnect()
        return None, (
            "Account not authorized.\n\n"
            "You must generate a StringSession first (see the box below)."
        )

    try:
        entity_part, msg_id = parse_link(link)
        status.info(f"Fetching message {msg_id}...")

        if entity_part.isdigit():
            entity = await client.get_entity(int(entity_part))
        else:
            entity = await client.get_entity(entity_part)

        msg = await client.get_messages(entity, ids=msg_id)

        if not msg:
            return None, "Message not found or no access."
        if not msg.media:
            return None, "This message contains no downloadable media."

        status.info("Downloading... please wait ⏳")

        with tempfile.TemporaryDirectory() as tmp:
            path = await msg.download_media(file=tmp)
            if not path:
                return None, "Download failed."

            p = Path(path)
            data = p.read_bytes()
            return (data, p.name), None

    except ValueError as e:
        return None, str(e)
    except ChannelPrivateError:
        return None, "Channel is private. Join it with your account first."
    except MessageIdInvalidError:
        return None, "Invalid message ID."
    except FloodWaitError as e:
        return None, f"Flood wait: try again after {e.seconds} seconds."
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
    finally:
        await client.disconnect()


# ========== RUN ==========
if submit:
    if not api_id.strip() or not api_hash.strip() or not link.strip():
        st.error("Please fill API ID, API Hash and the Telegram link.")
    else:
        try:
            api_id_int = int(api_id.strip())
        except ValueError:
            st.error("API ID must be a number.")
            st.stop()

        status = st.empty()
        result, err = asyncio.run(
            do_download(
                api_id_int,
                api_hash.strip(),
                session_string.strip(),
                link.strip(),
                status,
            )
        )

        if err:
            status.empty()
            st.error(err)
        else:
            data, filename = result
            status.empty()
            st.success(f"✅ Ready: **{filename}**")
            st.download_button(
                label="⬇️ Save Video to your device",
                data=data,
                file_name=filename,
                mime="application/octet-stream",
                use_container_width=True,
            )

# ========== INSTRUCTIONS ==========
st.divider()

with st.expander("🔑 How to get API ID & API Hash", expanded=False):
    st.markdown("""
1. Open **[https://my.telegram.org](https://my.telegram.org)**
2. Login with your phone number
3. Click **API development tools**
4. Create an app → copy **api_id** and **api_hash**
""")

with st.expander("🔐 How to create StringSession (do this once)", expanded=True):
    st.markdown("""
Run this small code **on your own computer** (only once):

```python
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = 12345678                # ← put your API ID
api_hash = "your_api_hash_here"  # ← put your API Hash

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("\\nYour StringSession (copy everything):\\n")
    print(client.session.save())
```

1. Install telethon: `pip install telethon`
2. Run the code above
3. Enter the login code that Telegram sends you
4. Copy the long string that is printed
5. Paste it in the **StringSession** field on this page

After that you can download any public Telegram video without logging in again.
""")

st.caption("Personal use only • Respect Telegram ToS & copyrights")
