import os
import requests
from flask import Flask, request, make_response

app = Flask(__name__)

# משיכת הנתונים ממשתני הסביבה של Render
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_TOKEN_123")

@app.route("/", methods=["GET"])
def home():
    return "Bot is running on Render!", 200

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    # פונקציה זו משמשת את מטא כדי לאמת את הכתובת של השרת שלך
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook verified successfully!")
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
            
            print(f"הודעה נכנסת: {text_body} מאת: {from_number}")

            # תשובה גנרית פשוטה כדי לבדוק שהכל עובד
            reply_text = f"היי! הבוט עובד. קיבלתי את ההודעה שלך: '{text_body}'"

            # שליחת התשובה ללקוח
            send_whatsapp_message(from_number, reply_text)

    return make_response("EVENT_RECEIVED", 200)

def send_whatsapp_message(to, text):
    # שים לב שעדכנתי את גרסת ה-API ל-v20.0 (גרסה יציבה ועדכנית)
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
    if response.status_code != 200:
        print("שגיאה בשליחה:", response.json())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
