import os
import requests
from flask import Flask, request, make_response

app = Flask(__name__)

# משיכת הנתונים ממשתני הסביבה של Render
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_TOKEN_123")
GOOGLE_SHEET_URL = os.environ.get("GOOGLE_SHEET_URL")
ADMIN_PHONE = os.environ.get("ADMIN_PHONE")

@app.route("/", methods=["GET"])
def home():
    return "Bot is running perfectly!", 200

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return make_response(challenge, 200)
    return make_response("Verification failed", 403)

@app.route("/webhook", methods=["POST"])
def message_received():
    data = request.get_json()
    
    # בדיקה שיש הודעה נכנסת מסוג טקסט
    if data.get("entry") and data["entry"][0].get("changes") and data["entry"][0]["changes"][0]["value"].get("messages"):
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]
        
        if message.get("type") == "text":
            from_number = message["from"]
            text_body = message["text"]["body"].strip()
            text_lower = text_body.lower()
            
            print(f"הודעה נכנסת: {text_body} מאת: {from_number}")

            # 1. שמירת ההודעה בגוגל שיטס (אם הוגדר קישור)
            if GOOGLE_SHEET_URL:
                save_to_google_sheets(from_number, text_body)

            # 2. לוגיקת התשובות
            if text_lower in ["salut", "bonjour", "hello"]:
                reply_text = "Salut ! Comment ça va ?"
            elif text_lower in ["ça va", "ca va"]:
                reply_text = "Ça va très bien, merci ! Et toi ?"
            elif "merci" in text_lower:
                reply_text = "Avec plaisir ! 😊"
            elif text_lower == "fin":
                reply_text = "Merci ! J'ai transféré votre demande à notre équipe. On vous contacte vite."
                
                # יצירת הודעת הסיכום למנהל ושליחתה (אם הוגדר מספר מנהל)
                if ADMIN_PHONE:
                    summary_text = f"🚨 התראה למנהל:\nלקוח עם המספר {from_number} סיים כעת שיחה עם הבוט וביקש שיחזרו אליו."
                    send_whatsapp_message(ADMIN_PHONE, summary_text)
            else:
                reply_text = f"Désolé, je ne comprends pas '{text_body}'. Essayez de dire 'Salut' ou tapez 'fin' pour terminer la discussion."

            # 3. שליחת התשובה ללקוח בוואטסאפ
            send_whatsapp_message(from_number, reply_text)

    return make_response("EVENT_RECEIVED", 200)

def save_to_google_sheets(from_number, text):
    """פונקציה השולחת את הנתונים ל-Google Apps Script"""
    payload = {
        "from": from_number,
        "text": text
    }
    try:
        response = requests.post(GOOGLE_SHEET_URL, json=payload)
        print(f"סטטוס שמירה בגוגל שיטס: {response.status_code}")
    except Exception as e:
        print(f"שגיאה בשמירה לגוגל שיטס: {e}")

def send_whatsapp_message(to, text):
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    response = requests.post(url, json=payload, headers=headers)
    print(f"סטטוס שליחה ל-{to}: {response.status_code}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
