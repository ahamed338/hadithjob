import os
import sys
import requests
import random
from dotenv import load_dotenv

load_dotenv()

CDN_BASE = "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions"

# Correct book counts per collection (all.json is too large for jsDelivr — 403).
# Individual per-book files work fine; these counts were verified from the repo.
COLLECTIONS = {
    'eng-bukhari': {'name': 'Sahih Bukhari', 'books': 97},
    'eng-muslim':  {'name': 'Sahih Muslim',  'books': 56},
}

MAX_BODY_LENGTH = 3800  # leaves room for formatting + reference line


def fetch_book(collection_key: str, book_num: int) -> list[dict]:
    """Return a list of valid hadith dicts from a single book file, or []."""
    url = f"{CDN_BASE}/{collection_key}/{book_num}.json"
    print(f"  GET {url}")
    resp = requests.get(url, timeout=15)
    print(f"  Status: {resp.status_code}")
    if resp.status_code != 200:
        return []
    data = resp.json()
    return [
        h for h in data.get('hadiths', [])
        if isinstance(h.get('text'), str) and h['text'].strip()
    ]


def get_random_hadith(max_attempts=20):
    """
    Pick a random collection and book, accept the first book that contains
    at least one valid hadith. No rejection sampling — the API's books are
    too sparse for that to work reliably.
    """
    for attempt in range(1, max_attempts + 1):
        print(f"Attempt {attempt}:")
        collection_key = random.choice(list(COLLECTIONS.keys()))
        collection = COLLECTIONS[collection_key]
        book_num = random.randint(1, collection['books'])

        try:
            hadiths = fetch_book(collection_key, book_num)
        except Exception as e:
            print(f"  Error fetching book: {e}, retrying...")
            continue

        if not hadiths:
            print(f"  No valid hadiths in {collection['name']} book {book_num}, retrying...")
            continue

        hadith = random.choice(hadiths)
        hadith_text = hadith['text'].strip()
        hadith_number = hadith.get('hadithnumber', 'Unknown')

        if isinstance(hadith_number, float) and hadith_number.is_integer():
            hadith_number = int(hadith_number)

        reference = f"{collection['name']} - Book {book_num}, Hadith {hadith_number}"

        if len(hadith_text) > MAX_BODY_LENGTH:
            hadith_text = hadith_text[:MAX_BODY_LENGTH].rsplit(' ', 1)[0] + "..."

        print(f"  Got hadith {hadith_number} from {collection['name']} book {book_num}")
        return f"📖 *Daily Hadith* (Sahih)\n\n{hadith_text}\n\n_{reference}_"

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
