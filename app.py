import os
from flask import Flask, request, make_response

app = Flask(__name__)

# זה הקוד שאתה ממציא כדי לאמת את החיבור מול מטא
VERIFY_TOKEN = "MY_SECRET_TOKEN_123" 

@app.route("/", methods=["GET"])
def home():
    return "Bot is running!", 200

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return make_response(challenge, 200)
        else:
            return make_response("Verification failed", 403)

@app.route("/webhook", methods=["POST"])
def message_received():
    data = request.get_json()
    print("Received message:", data)
    return make_response("EVENT_RECEIVED", 200)

if __name__ == "__main__":
    # התיקון הקריטי: Render דורש לקרוא את הפורט מהסביבה
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
