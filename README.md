# Telegram Video Downloader (GitHub Actions Only)

Download videos, photos and documents from any public Telegram link **using only GitHub Actions*([https://abhayattcc.github.io/Apk-builder-online-gituhb/])

No need to keep a computer running. Just trigger the workflow and download the artifact.

---

## Live Page

After you push the repo and enable Pages, the page will be available at:

```
https://YOUR_USERNAME.github.io/telegram-video-downloader/
```

---

## One-time Setup

### 1. Push this repository to GitHub

Create a new repo and push all files to the `main` branch.

### 2. Add Secrets

Go to your repository → **Settings → Secrets and variables → Actions → New repository secret**

Add these two secrets:

| Secret Name          | Value                          |
|----------------------|--------------------------------|
| `TELEGRAM_API_ID`    | Your API ID (number)           |
| `TELEGRAM_API_HASH`  | Your API Hash (string)         |

(Optional but recommended)  
`TELEGRAM_SESSION` → StringSession (so the action does not need to ask for phone code every time)

### 3. Enable GitHub Pages

- Go to **Settings → Pages**
- Source = **GitHub Actions**

The page will deploy automatically on every push to `main`.

---

## How to Download a Telegram Video

1. Open your repository on GitHub
2. Click the **Actions** tab
3. Select **“Download Telegram Media”** on the left
4. Click **Run workflow**
5. Paste the Telegram link (example: `https://t.me/odiamahabharat/154`)
6. Click the green **Run workflow** button
7. Wait 30–90 seconds
8. Open the finished run → scroll down → download the **telegram-media** artifact

That’s it. The video will be inside the artifact.

---

## Generate StringSession (Recommended)

Running the action the first time without a session will fail because GitHub Actions cannot receive the login code interactively.

Do this **once** on your computer:

```bash
pip install telethon
python -c "
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
api_id = 12345678          # your api_id
api_hash = 'your_api_hash'
with TelegramClient(StringSession(), api_id, api_hash) as client:
    print('Your TELEGRAM_SESSION string:')
    print(client.session.save())
"
```

Copy the long string that is printed and add it as the secret `TELEGRAM_SESSION`.

After that the GitHub Action will work fully automatically.

---

## Project Structure

```
telegram-video-downloader/
├── index.html                      # Downloader page (deployed by Actions)
├── telegram_downloader.py          # Downloader script
├── requirements.txt
├── README.md
├── .gitignore
└── .github/workflows/
    ├── deploy.yml                  # Deploys the page to GitHub Pages
    └── download.yml                # Downloads media when you trigger it
```

---

## Local usage (optional)

```bash
export TELEGRAM_API_ID=your_id
export TELEGRAM_API_HASH=your_hash
# optional: export TELEGRAM_SESSION=your_string_session

python telegram_downloader.py "https://t.me/odiamahabharat/154"
```

---

## Notes

- Works only with public channels or channels your account has joined.
- Files are kept as artifacts for 5 days.
- Never commit your API credentials or session file.
- For personal / educational use only.

---

## License

MIT
