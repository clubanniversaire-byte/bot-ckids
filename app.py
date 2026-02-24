import os
from flask import Flask, request, make_response

app = Flask(__name__)

# זה הקוד שאתה ממציא כדי לאמת את החיבור מול מטא
VERIFY_TOKEN = "MY_SECRET_TOKEN_123" 

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    # שלב האימות מול מטא
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
    # כאן יגיעו ההודעות מהלקוחות
    data = request.get_json()
    print("Received message:", data)
    return make_response("EVENT_RECEIVED", 200)

if __name__ == "__main__":
    app.run(port=5000)