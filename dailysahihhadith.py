import os
import sys
import requests
import random
from dotenv import load_dotenv

load_dotenv()

COLLECTIONS = {
    'eng-bukhari': {'name': 'Sahih Bukhari', 'books': 8},
    'eng-muslim':  {'name': 'Sahih Muslim',  'books': 56},
}

MAX_BODY_LENGTH = 3800  # leaves room for formatting + reference line


def get_random_hadith(max_attempts=10):
    """
    Fetch a random hadith from fawazahmed0/hadith-api via jsDelivr CDN.
    Retries with a different book if the chosen one has no valid text entries.
    """
    for attempt in range(1, max_attempts + 1):
        collection_key = random.choice(list(COLLECTIONS.keys()))
        collection = COLLECTIONS[collection_key]
        book_num = random.randint(1, collection['books'])
        url = f"https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/{collection_key}/{book_num}.json"

        try:
            print(f"Attempt {attempt}: GET {url}")
            response = requests.get(url, timeout=15)
            print(f"Status: {response.status_code}")

            if response.status_code != 200:
                print(f"Unexpected status, retrying...")
                continue

            data = response.json()
            hadiths = [h for h in data.get('hadiths', []) if h.get('text', '').strip()]

            if not hadiths:
                print(f"No valid hadiths in {collection['name']} book {book_num}, retrying...")
                continue

            hadith = random.choice(hadiths)
            hadith_text = hadith.get('text', '').strip()
            hadith_number = hadith.get('hadithnumber', 'Unknown')
            reference = f"{collection['name']} - Book {book_num}, Hadith {hadith_number}"

            # Truncate long hadiths at a word boundary to stay within Telegram's limit
            if len(hadith_text) > MAX_BODY_LENGTH:
                hadith_text = hadith_text[:MAX_BODY_LENGTH].rsplit(' ', 1)[0] + "..."

            return f"📖 *Daily Hadith* (Sahih)\n\n{hadith_text}\n\n_{reference}_"

        except requests.exceptions.Timeout:
            print(f"Attempt {attempt}: Timed out, retrying...")
        except requests.exceptions.ConnectionError as e:
            print(f"Attempt {attempt}: Connection error - {e}")
        except Exception as e:
            print(f"Attempt {attempt}: Unexpected error - {e}")

    return None


def send_hadith_to_user():
    """Send daily hadith to the configured Telegram user"""
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')

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
            'chat_id': chat_id,
            'text': hadith,
            'parse_mode': 'Markdown'
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
