# Telegram Video Downloader (Single Python Page)

One single Python file that is both the web page and the downloader.

## Features
- Enter API ID + API Hash
- Enter StringSession
- Paste Telegram link
- Download the video directly from the page

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy free (recommended)

### Option 1 – Streamlit Community Cloud (easiest)
1. Push this folder to a GitHub repository
2. Go to https://share.streamlit.io
3. Login with GitHub → New app
4. Select the repository and `app.py`
5. Deploy

Your page will be live at a link like:
`https://yourname-telegram-downloader.streamlit.app`

### Option 2 – Hugging Face Spaces
1. Create a new Space (SDK = Streamlit)
2. Upload `app.py` and `requirements.txt`
3. Space will automatically run the page

## Important
- First generate a **StringSession** on your computer (see instructions inside the app)
- Never share your API Hash or StringSession publicly
