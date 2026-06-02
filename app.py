import os
import time
import requests
from datetime import datetime
from flask import Flask, request, make_response

app = Flask(__name__)

# ==========================================
# CONFIGURATION DES VARIABLES
# ==========================================
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
WHATSAPP_TOKEN = os.environ.get("ACCESS_TOKEN") # משמש להורדת מדיה
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_TOKEN_123")
ADMIN_PHONE = os.environ.get("ADMIN_PHONE")
GOOGLE_SHEET_URL = os.environ.get("GOOGLE_SHEET_URL")

# Connexion WooCommerce / WordPress
WC_STORE_URL = os.environ.get("WC_STORE_URL") 
WC_CONSUMER_KEY = os.environ.get("WC_CONSUMER_KEY")
WC_CONSUMER_SECRET = os.environ.get("WC_CONSUMER_SECRET")

USER_STATES = {}

def get_media_url(media_id):
    """שליפת הקישור הישיר לתמונה שנשלחה על ידי המשתמש"""
    url = f"https://graph.facebook.com/v20.0/{media_id}"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            return res.json().get("url")
    except Exception as e:
        print(f"Erreur media URL: {e}")
    return None

def get_woocommerce_order(order_id):
    if not WC_STORE_URL or not WC_CONSUMER_KEY or not WC_CONSUMER_SECRET:
        return None
    base_url = f"{WC_STORE_URL.rstrip('/')}/wp-json/wc/v3/orders/{order_id}"
    params = {"consumer_key": WC_CONSUMER_KEY, "consumer_secret": WC_CONSUMER_SECRET}
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(base_url, params=params, headers=headers, timeout=10)
        if response.status_code == 200: return response.json()
        if response.status_code == 404: return "NOT_FOUND"
        return None
    except Exception as e:
        return None

def send_whatsapp_btn(to, text, buttons):
    """שליחת כפתורים לחיצים בוואטסאפ (מקסימום 3 כפתורים)"""
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    
    formatted_buttons = []
    for i, btn_text in enumerate(buttons):
        formatted_buttons.append({
            "type": "reply",
            "reply": {"id": f"btn_{i+1}", "title": btn_text[:20]} # הגבלה של פייסבוק עד 20 תווים
        })
        
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text},
            "action": {"buttons": formatted_buttons}
        }
    }
    response = requests.post(url, json=payload, headers=headers)
    print(f"Boutons envoyés à {to}: {response.status_code}")

def send_whatsapp_message(to, text):
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}}
    requests.post(url, json=payload, headers=headers)

@app.route("/", methods=["GET"])
def home(): return "Bot Français interactif sans emails actif !", 200

@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return make_response(request.args.get("hub.challenge"), 200)
    return "Failed", 403

@app.route("/webhook", methods=["POST"])
def message_received():
    data = request.get_json()
    if not (data.get("entry") and data["entry"][0].get("changes") and data["entry"][0]["changes"][0]["value"].get("messages")):
        return make_response("EVENT_RECEIVED", 200)

    message = data["entry"][0]["changes"][0]["value"]["messages"][0]
    from_number = message["from"]
    
    # בדיקה אם מדובר בלחיצת כפתור או בטקסט רגיל
    text_body = ""
    if message.get("type") == "interactive" and message["interactive"].get("button_reply"):
        text_body = message["interactive"]["button_reply"]["title"].strip()
    elif message.get("type") == "text":
        text_body = message["text"]["body"].strip()
        
    text_lower = text_body.lower()

    if text_lower in ["debut", "début", "start", "menu", "bonjour"]:
        USER_STATES[from_number] = {"state": "MAIN_MENU", "data": {}}
        send_whatsapp_btn(from_number, "👋 *Bonjour ! Bienvenue sur notre service client* ✨\nComment puis-je vous aider aujourd'hui ?", ["Ma commande 📦", "Question générale ❓"])
        return make_response("EVENT_RECEIVED", 200)

    if from_number not in USER_STATES:
        USER_STATES[from_number] = {"state": "MAIN_MENU", "data": {}}
        send_whatsapp_btn(from_number, "👋 *Bonjour ! Bienvenue sur notre service client* ✨\nComment puis-je vous aider aujourd'hui ?", ["Ma commande 📦", "Question générale ❓"])
        return make_response("EVENT_RECEIVED", 200)

    current_state = USER_STATES[from_number]["state"]
    user_data = USER_STATES[from_number]["data"]

    # 1. תפריט ראשי
    if current_state == "MAIN_MENU":
        if "commande" in text_lower:
            USER_STATES[from_number]["state"] = "WAITING_FOR_ORDER_ID"
            send_whatsapp_message(from_number, "Parfait. Veuillez saisir votre **numéro de commande** (uniquement les chiffres, ex: 4205) :")
        elif "générale" in text_lower or "generale" in text_lower:
            USER_STATES[from_number]["state"] = "GENERAL_QA"
            send_whatsapp_message(from_number, "Avec plaisir ! Veuillez écrire votre question en détail ici 👇")
        else:
            send_whatsapp_btn(from_number, "Veuillez choisir l'une des options suivantes :", ["Ma commande 📦", "Question générale ❓"])

    # 2. קבלת מספר הזמנה ומשיכת נתונים
    elif current_state == "WAITING_FOR_ORDER_ID":
        order_id = "".join(filter(str.isdigit, text_body))
        if not order_id:
            send_whatsapp_message(from_number, "Je n'ai pas compris. Veuillez envoyer uniquement les chiffres de votre commande :")
            return make_response("EVENT_RECEIVED", 200)
            
        send_whatsapp_message(from_number, "Je vérifie cela sur le site... Un instant ⏳")
        order_info = get_woocommerce_order(order_id)
        
        if order_info == "NOT_FOUND":
            send_whatsapp_message(from_number, f"❌ Aucune commande trouvée avec le numéro {order_id}. Veuillez vérifier et réessayer :")
        elif order_info is None:
            user_data["order_id"] = order_id
            user_data["customer_email"] = "Inconnu (Erreur Site)"
            USER_STATES[from_number]["state"] = "REPORT_ORDER_ISSUE"
            send_whatsapp_message(from_number, "Commande reçue, mais le site est ralenti. Veuillez détailler votre demande ici, un conseiller prend le relais :")
        else:
            status_translations = {
                "pending": "En attente de paiement 💳", "processing": "En cours de préparation 📦",
                "on-hold": "En attente ⏳", "completed": "Terminée et expédiée ! 🚀",
                "cancelled": "Annulée ❌", "refunded": "Remboursée 💰", "failed": "Échouée ❌"
            }
            raw_status = order_info.get("status", "unknown")
            translated_status = status_translations.get(raw_status, raw_status)
            total_price = order_info.get("total", "0")
            currency = order_info.get("currency", "€")
            customer_name = order_info.get("billing", {}).get("first_name", "Client")
            customer_email = order_info.get("billing", {}).get("email", "Non spécifié")
            
            user_data["order_id"] = order_id
            user_data["customer_email"] = customer_email
            user_data["raw_info"] = f"Status: {translated_status}, Total: {total_price}"
            
            success_msg = f"""Bonjour {customer_name}, j'ai trouvé votre commande ! 📜
🔹 *Statut :* {translated_status}
🔹 *Montant :* {total_price} {currency}
🔹 *Email lié :* {customer_email}

Avez-vous une demande concernant cette commande ? Choisissez une option :"""
            
            USER_STATES[from_number]["state"] = "ORDER_MENU_OPTIONS"
            send_whatsapp_btn(from_number, success_msg, ["Remarque spéciale 📝", "Livraison 🚚", "Produit défectueux ⚠️"])

    # 3. תפריט מורחב של אפשרויות אחרי הזמנה
    elif current_state == "ORDER_MENU_OPTIONS":
        if "remarque" in text_lower:
            user_data["sub_topic"] = "הערה מיוחדת לגבי ההזמנה"
            USER_STATES[from_number]["state"] = "COLLECTING_ORDER_TEXT"
            send_whatsapp_message(from_number, "Veuillez écrire votre remarque ou modification demandée pour cette commande :")
        elif "livraison" in text_lower:
            user_data["sub_topic"] = "בעיה או שאלה לגבי המשלוח"
            USER_STATES[from_number]["state"] = "COLLECTING_ORDER_TEXT"
            send_whatsapp_message(from_number, "Veuillez détailler votre problème de livraison (retard, adresse, etc.) :")
        elif "défectueux" in text_lower or "defectueux" in text_lower:
            user_data["sub_topic"] = "מוצר פגום / בעיה במוצר"
            USER_STATES[from_number]["state"] = "WAITING_FOR_PHOTO"
            send_whatsapp_message(from_number, "Nous sommes désolés. Veuillez envoyer une photo du produit endommagé ici directement sur WhatsApp 📸 :")
        else:
            send_whatsapp_btn(from_number, "Veuillez cliquer sur un bouton :", ["Remarque spéciale 📝", "Livraison 🚚", "Produit défectueux ⚠️"])

    # 4. קבלת טקסט חופשי (הערה או משלוח)
    elif current_state == "COLLECTING_ORDER_TEXT":
        ticket = {
            "topic": f"הזמנה קיימת - {user_data.get('sub_topic')}",
            "order_id": user_data.get("order_id"),
            "customer_email": user_data.get("customer_email"),
            "site_info": user_data.get("raw_info", "N/A"),
            "user_message": text_body
        }
        process_completed_ticket(from_number, ticket)
        send_whatsapp_message(from_number, "Votre demande a bien été enregistrée. Notre équipe revient vers vous très vite ! 💙")
        USER_STATES[from_number] = {"state": "MAIN_MENU", "data": {}}

    # 5. קבלת תמונה (מוצר פגום)
    elif current_state == "WAITING_FOR_PHOTO":
        photo_url = "Aucune image envoyée"
        if message.get("type") == "image":
            media_id = message["image"]["id"]
            photo_url = get_media_url(media_id)
            caption = message["image"].get("caption", "Sans texte")
            text_body = f"[תמונה מצורפת] - כיתוב: {caption}"
        else:
            text_body = f"[הלקוח לא שלח תמונה, שלח טקסט]: {text_body}"

        ticket = {
            "topic": "הזמנה קיימת - מוצר פגום (צרפתית)",
            "order_id": user_data.get("order_id"),
            "customer_email": user_data.get("customer_email"),
            "site_info": user_data.get("raw_info", "N/A"),
            "user_message": text_body,
            "photo_url": photo_url
        }
        process_completed_ticket(from_number, ticket)
        send_whatsapp_message(from_number, "Merci pour la photo et les détails. Votre dossier a été transmis au service client, nous vous répondrons rapidement ! 💙")
        USER_STATES[from_number] = {"state": "MAIN_MENU", "data": {}}

    # 6. שאלה כללית
    elif current_state == "GENERAL_QA":
        ticket = {
            "topic": "שאלה כללית מהאתר (צרפתית)",
            "customer_email": "לא צוינה הזמנה",
            "user_message": text_body
        }
        process_completed_ticket(from_number, ticket)
        send_whatsapp_message(from_number, "Merci ! Nous avons bien reçu votre question et notre équipe vous répondra très rapidement. 💙")
        USER_STATES[from_number] = {"state": "MAIN_MENU", "data": {}}

    return make_response("EVENT_RECEIVED", 200)

def process_completed_ticket(from_number, ticket):
    """שמירה בגוגל שיטס ושליחת סיכום לוואטסאפ של המנהל בלבד"""
    ticket["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ticket["user_phone"] = from_number

    # 1. שמירה בגוגל שיטס
    if GOOGLE_SHEET_URL:
        try: requests.post(GOOGLE_SHEET_URL, json=ticket)
        except Exception as e: print(f"Sheet Error: {e}")

    # תמלול עברי מלא ומסודר למנהל בוואטסאפ
    summary = f"""🚨 *פניית שירות חדשה מהאתר הצרפתי!*

📌 *נושא:* {ticket.get('topic')}
👤 *טלפון הלקוח:* {ticket.get('user_phone')}
📧 *מייל הלקוח:* {ticket.get('customer_email')}
📦 *מספר הזמנה:* {ticket.get('order_id', 'ללא')}
📊 *סטטוס באתר:* {ticket.get('site_info', 'ללא')}
💬 *תוכן הפנייה:* {ticket.get('user_message')}
🖼️ *קישור לתמונה:* {ticket.get('photo_url', 'אין תמונה')}
📅 *זמן:* {ticket.get('timestamp')}"""

    # 2. שליחת התראה לוואטסאפ של המנהל
    if ADMIN_PHONE:
        send_whatsapp_message(ADMIN_PHONE, summary)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
