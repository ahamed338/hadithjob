import os
import sys
import requests
import random
from dotenv import load_dotenv

load_dotenv()

COLLECTIONS = {
    'eng-bukhari': 'Sahih Bukhari',
    'eng-muslim':  'Sahih Muslim',
}

# Base URL for the all-hadiths file per collection
CDN_BASE = "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions"

MAX_BODY_LENGTH = 3800  # leaves room for formatting + reference line


def get_random_hadith(max_attempts=5):
    """
    Fetch a random hadith by pulling the full collection (all.json) and
    sampling uniformly from every hadith in it — no book-selection bias.
    """
    collection_keys = list(COLLECTIONS.keys())
    random.shuffle(collection_keys)          # try collections in random order

    for attempt in range(1, max_attempts + 1):
        collection_key = collection_keys[attempt % len(collection_keys)]
        collection_name = COLLECTIONS[collection_key]
        url = f"{CDN_BASE}/{collection_key}/all.json"

        try:
            print(f"Attempt {attempt}: GET {url}")
            response = requests.get(url, timeout=30)
            print(f"Status: {response.status_code}")

            if response.status_code != 200:
                print(f"Unexpected status {response.status_code}, retrying...")
                continue

            data = response.json()

            # The all.json schema: {"hadiths": [...], ...}
            hadiths = [
                h for h in data.get('hadiths', [])
                if isinstance(h.get('text'), str) and h['text'].strip()
            ]

            if not hadiths:
                print(f"No valid hadiths found in {collection_name}, retrying...")
                continue

            hadith = random.choice(hadiths)
            hadith_text = hadith['text'].strip()
            hadith_number = hadith.get('hadithnumber', 'Unknown')

            # hadithnumber can sometimes be a float like 1234.0 — clean it up
            if isinstance(hadith_number, float) and hadith_number.is_integer():
                hadith_number = int(hadith_number)

            reference = f"{collection_name}, Hadith {hadith_number}"

            # Truncate at a word boundary to stay within Telegram's limit
            if len(hadith_text) > MAX_BODY_LENGTH:
                hadith_text = (
                    hadith_text[:MAX_BODY_LENGTH].rsplit(' ', 1)[0] + "…"
                )

            return f"📖 *Daily Hadith* (Sahih)\n\n{hadith_text}\n\n_{reference}_"

        except requests.exceptions.Timeout:
            print(f"Attempt {attempt}: Timed out, retrying...")
        except requests.exceptions.ConnectionError as e:
            print(f"Attempt {attempt}: Connection error — {e}")
        except Exception as e:
            print(f"Attempt {attempt}: Unexpected error — {e}")

    return None


def send_hadith_to_user():
    """Send daily hadith to the configured Telegram user."""
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id   = os.getenv('TELEGRAM_CHAT_ID')

    if not bot_token:
        print("❌ Error: TELEGRAM_BOT_TOKEN not found in environment variables")
        sys.exit(1)
    if not chat_id:
        print("❌ Error: TELEGRAM_CHAT_ID not found in environment variables")
        sys.exit(1)

    hadith = get_random_hadith()
    if not hadith:
        print("❌ Failed to fetch hadith after all attempts")
        sys.exit(1)

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            'chat_id':    chat_id,
            'text':       hadith,
            'parse_mode': 'Markdown',
        }
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            print(f"✅ Successfully sent daily hadith to chat {chat_id}")
        else:
            print(f"❌ Failed to send message: {response.text}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Error sending hadith: {e}")
        sys.exit(1)


if __name__ == '__main__':
    send_hadith_to_user()
