import os
import sys
import requests
import random
from dotenv import load_dotenv

load_dotenv()

# Available Sahih collections in fawazahmed0/hadith-api
COLLECTIONS = {
    'eng-bukhari': {'name': 'Sahih Bukhari', 'books': 8},
    'eng-muslim':  {'name': 'Sahih Muslim',  'books': 56},
}

def get_random_hadith():
    """Fetch a random hadith from fawazahmed0/hadith-api (jsDelivr CDN)"""
    collection_key = random.choice(list(COLLECTIONS.keys()))
    collection = COLLECTIONS[collection_key]
    book_num = random.randint(1, collection['books'])

    url = f"https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/{collection_key}/{book_num}.json"

    try:
        print(f"Fetching: {url}")
        response = requests.get(url, timeout=15)
        print(f"Status: {response.status_code}")

        if response.status_code != 200:
            print(f"Error response: {response.text[:300]}")
            return None

        data = response.json()
        hadiths = data.get('hadiths', [])

        if not hadiths:
            print("No hadiths found in response")
            return None

        hadith = random.choice(hadiths)
        hadith_text = hadith.get('text', '').strip()
        hadith_number = hadith.get('hadithnumber', 'Unknown')

        if not hadith_text:
            print(f"Empty hadith text. Entry: {hadith}")
            return None

        reference = f"{collection['name']} - Book {book_num}, Hadith {hadith_number}"
        return f"📖 *Daily Hadith* (Sahih)\n\n{hadith_text}\n\n_{reference}_"

    except requests.exceptions.Timeout:
        print("Request timed out")
    except requests.exceptions.ConnectionError as e:
        print(f"Connection error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

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
        print("❌ Failed to fetch hadith")
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