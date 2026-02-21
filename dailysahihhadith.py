import os
import sys
import requests
import random
import time
from dotenv import load_dotenv

load_dotenv()

# Fallback: fawazahmed0/hadith-api via jsDelivr
COLLECTIONS = {
    'eng-bukhari': {'name': 'Sahih Bukhari', 'books': 8},
    'eng-muslim':  {'name': 'Sahih Muslim',  'books': 56},
}

def get_hadith_from_hadeethenc():
    """Primary: HadeethEnc API — authenticated hadiths, English, no key required"""
    url = "https://hadeethenc.com/api/v1/hadeeths/random/?language=en"

    for attempt in range(1, 4):
        try:
            print(f"Attempt {attempt}: GET {url}")
            response = requests.get(url, timeout=15)
            print(f"Status: {response.status_code}")

            if response.status_code != 200:
                print(f"Error response: {response.text[:300]}")
                time.sleep(2 ** attempt)
                continue

            data = response.json()
            hadith_text = data.get('hadeeth', '').strip()
            attribution = data.get('attribution', '').strip()
            grade = data.get('grade', '').strip()

            if not hadith_text:
                print(f"Empty hadith text in response: {data}")
                time.sleep(2 ** attempt)
                continue

            reference = attribution if attribution else "HadeethEnc"
            grade_str = f" • {grade}" if grade else ""

            return f"📖 *Daily Hadith*{grade_str}\n\n{hadith_text}\n\n_{reference}_"

        except requests.exceptions.Timeout:
            print(f"Attempt {attempt}: Timed out")
        except requests.exceptions.ConnectionError as e:
            print(f"Attempt {attempt}: Connection error - {e}")
        except Exception as e:
            print(f"Attempt {attempt}: Unexpected error - {e}")

        time.sleep(2 ** attempt)

    return None


def get_hadith_from_fawazahmed():
    """Fallback: fawazahmed0/hadith-api via jsDelivr CDN"""
    collection_key = random.choice(list(COLLECTIONS.keys()))
    collection = COLLECTIONS[collection_key]
    book_num = random.randint(1, collection['books'])
    url = f"https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/{collection_key}/{book_num}.json"

    try:
        print(f"Fallback: GET {url}")
        response = requests.get(url, timeout=15)
        print(f"Status: {response.status_code}")

        if response.status_code != 200:
            print(f"Error response: {response.text[:300]}")
            return None

        data = response.json()

        # Filter out entries with empty text upfront
        hadiths = [h for h in data.get('hadiths', []) if h.get('text', '').strip()]

        if not hadiths:
            print("No valid hadiths found in this book")
            return None

        hadith = random.choice(hadiths)
        hadith_text = hadith.get('text', '').strip()
        hadith_number = hadith.get('hadithnumber', 'Unknown')

        reference = f"{collection['name']} - Book {book_num}, Hadith {hadith_number}"
        return f"📖 *Daily Hadith* (Sahih)\n\n{hadith_text}\n\n_{reference}_"

    except requests.exceptions.Timeout:
        print("Fallback: Timed out")
    except requests.exceptions.ConnectionError as e:
        print(f"Fallback: Connection error - {e}")
    except Exception as e:
        print(f"Fallback: Unexpected error - {e}")

    return None


def get_random_hadith():
    """Try primary API first, fall back if needed"""
    hadith = get_hadith_from_hadeethenc()
    if hadith:
        return hadith

    print("⚠️ Primary API failed, switching to fallback...")
    return get_hadith_from_fawazahmed()


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
        print("❌ Failed to fetch hadith from all sources")
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