"""
Generate Telegram StringSession using GitHub Actions (2 steps)
"""

import os
import sys
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
PHONE = os.environ["PHONE"].strip()
STEP = os.environ.get("STEP", "")
LOGIN_CODE = os.environ.get("LOGIN_CODE", "").strip()
PHONE_CODE_HASH = os.environ.get("PHONE_CODE_HASH", "").strip()
PASSWORD = os.environ.get("PASSWORD", "").strip()


def step1_send_code():
    print("=" * 55)
    print(" STEP 1 → Sending login code to your phone/Telegram")
    print("=" * 55)

    client = TelegramClient(StringSession(), API_ID, API_HASH)
    client.connect()

    if client.is_user_authorized():
        session_str = client.session.save()
        print("\n✅ Account already logged in!")
        print("\nYour StringSession:\n")
        print(session_str)
        with open("string_session.txt", "w") as f:
            f.write(session_str)
        _write_summary(session_str)
        client.disconnect()
        return

    result = client.send_code_request(PHONE)
    phone_code_hash = result.phone_code_hash

    print(f"\n✅ Code sent successfully to → {PHONE}")
    print("\n" + "-" * 55)
    print("IMPORTANT – Copy this phone_code_hash:")
    print("-" * 55)
    print(phone_code_hash)
    print("-" * 55)

    print("\n👉 Next steps:")
    print("1. Open Telegram and copy the login code you just received")
    print("2. Go back to GitHub Actions")
    print("3. Run this workflow again")
    print("4. Choose:  \"2 - Create StringSession\"")
    print("5. Fill the same API ID, API Hash and Phone")
    print("6. Paste the login code")
    print("7. Paste the phone_code_hash shown above")
    print("8. Click Run workflow")

    # Also put in step summary
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a") as f:
            f.write("### Step 1 completed\n\n")
            f.write(f"- Code sent to: `{PHONE}`\n")
            f.write(f"- **phone_code_hash** (copy this):\n\n")
            f.write(f"`{phone_code_hash}`\n\n")
            f.write("Now run **Step 2** with the login code + this hash.\n")

    client.disconnect()


def step2_create_session():
    print("=" * 55)
    print(" STEP 2 → Creating StringSession")
    print("=" * 55)

    if not LOGIN_CODE:
        print("❌ login_code is missing. Go back and fill it.")
        sys.exit(1)
    if not PHONE_CODE_HASH:
        print("❌ phone_code_hash is missing.")
        print("   Copy it from the Step 1 logs / summary and paste it.")
        sys.exit(1)

    client = TelegramClient(StringSession(), API_ID, API_HASH)
    client.connect()

    try:
        try:
            client.sign_in(
                phone=PHONE,
                code=LOGIN_CODE,
                phone_code_hash=PHONE_CODE_HASH,
            )
        except SessionPasswordNeededError:
            if not PASSWORD:
                print("❌ Your account has 2FA enabled.")
                print("   Re-run Step 2 and also fill the password field.")
                sys.exit(1)
            client.sign_in(password=PASSWORD)

        session_str = client.session.save()

        print("\n" + "=" * 55)
        print("✅ SUCCESS! Your StringSession is ready")
        print("=" * 55)
        print("\n" + session_str + "\n")
        print("=" * 55)
        print("Copy the long string above.")
        print("Paste it into the downloader page (StringSession field).")
        print("=" * 55)

        with open("string_session.txt", "w") as f:
            f.write(session_str)

        _write_summary(session_str)

    except PhoneCodeInvalidError:
        print("❌ Invalid login code. Run Step 1 again to get a new code.")
        sys.exit(1)
    except PhoneCodeExpiredError:
        print("❌ Login code expired. Run Step 1 again.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        sys.exit(1)
    finally:
        client.disconnect()


def _write_summary(session_str: str):
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a") as f:
            f.write("### ✅ Your Telegram StringSession\n\n")
            f.write("```\n")
            f.write(session_str + "\n")
            f.write("```\n\n")
            f.write("**Keep this secret.** Paste it in the downloader page.\n")


if __name__ == "__main__":
    print(f"Phone  : {PHONE}")
    print(f"API ID : {API_ID}")
    print(f"Step   : {STEP}\n")

    if STEP.startswith("1"):
        step1_send_code()
    elif STEP.startswith("2"):
        step2_create_session()
    else:
        print("Unknown step")
        sys.exit(1)
