import os
import sys
import requests
import random
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_random_hadith():
    """Fetch a random hadith from Sahih collections only"""
    # Randomly choose between Bukhari and Muslim
    collections = ['bukhari', 'muslim']
    collection = random.choice(collections)
    
    try:
        # Using random hadith API for Sahih collections
        response = requests.get(f'https://random-hadith-generator.vercel.app/{collection}/')
        if response.status_code == 200:
            data = response.json()
            hadith_text = data['data']['hadith_english']
            
            # Format the collection name properly
            collection_name = "Sahih Bukhari" if collection == 'bukhari' else "Sahih Muslim"
            reference = f"{collection_name} - {data['data']['refno']}"
            
            return f"📖 *Daily Hadith* (Sahih)\n\n{hadith_text}\n\n_{reference}_"
        else:
            return None
    except Exception as e:
        print(f"Error fetching hadith: {e}")
        return None

def send_hadith_to_user():
    """Send daily hadith to the configured user"""
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
        # Send message using Telegram Bot API directly
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': hadith,
            'parse_mode': 'Markdown'
        }
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            print(f"✅ Successfully sent daily hadith to chat {chat_id}")
        else:
            print(f"❌ Failed to send hadith: {response.text}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Error sending hadith: {e}")
        sys.exit(1)

if __name__ == '__main__':
    send_hadith_to_user()