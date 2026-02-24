import os
import requests
from flask import Flask, request, make_response

app = Flask(__name__)

# הגדרות - המערכת תמשוך את המידע מה-Environment Variables ב-Render
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
PHONE_NUMBER_ID = "1000407146489466"
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_TOKEN_123")

@app.route("/", methods=["GET"])
def home():
    return "Bot is running!", 200

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
            text_body = message["text"]["body"].strip().lower() # הופך לאותיות קטנות כדי שיהיה קל להשוות
            
            print(f"הודעה נכנסת: {text_body}")

            # לוגיקת התשובות (כאן קורה הקסם)
            if text_body in ["salut", "bonjour", "hello"]:
                reply_text = "Salut ! Comment ça va ?"
            elif text_body in ["ça va", "ca va"]:
                reply_text = "Ça va très bien, merci ! Et toi ?"
            elif "merci" in text_body:
                reply_text = "Avec plaisir ! 😊"
            else:
                reply_text = f"Désolé, je ne comprends pas '{text_body}'. Essayez de dire 'Salut' !"

            # שליחת התשובה
            send_whatsapp_message(from_number, reply_text)

    return make_response("EVENT_RECEIVED", 200)

def send_whatsapp_message(to, text):
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
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
    print(f"סטטוס שליחה: {response.status_code}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
