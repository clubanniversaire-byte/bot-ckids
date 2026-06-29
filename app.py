import os
import time
import requests
from datetime import datetime
from flask import Flask, request, make_response, send_from_directory

app = Flask(__name__)

MEDIA_DIR = "stored_media"
if not os.path.exists(MEDIA_DIR):
    os.makedirs(MEDIA_DIR)

# ==========================================
# CONFIGURATION DES VARIABLES
# ==========================================
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_TOKEN_123")
ADMIN_PHONE = os.environ.get("ADMIN_PHONE")
GOOGLE_SHEET_URL = os.environ.get("GOOGLE_SHEET_URL")

# Connexion WooCommerce
WC_STORE_URL = os.environ.get("WC_STORE_URL") 
WC_CONSUMER_KEY = os.environ.get("WC_CONSUMER_KEY")
WC_CONSUMER_SECRET = os.environ.get("WC_CONSUMER_SECRET")

USER_STATES = {}

def download_whatsapp_media(media_id):
    if not ACCESS_TOKEN: return "Aucun token configuré"
    url = f"https://graph.facebook.com/v20.0/{media_id}"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    try:
        res = requests.get(url, headers=headers)
        if res.status_code != 200: return f"Erreur FB API: {res.status_code}"
        fb_url = res.json().get("url")
        if not fb_url: return "URL média introuvable"
        
        media_res = requests.get(fb_url, headers=headers)
        if media_res.status_code == 200:
            filename = f"photo_{media_id}_{int(time.time())}.jpg"
            filepath = os.path.join(MEDIA_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(media_res.content)
            render_host = request.host_url.rstrip('/')
            return f"{render_host}/media/{filename}"
        return f"Erreur téléch.: {media_res.status_code}"
    except Exception as e:
        return f"Exception: {e}"

def get_woocommerce_order(order_id):
    if not WC_STORE_URL or not WC_CONSUMER_KEY or not WC_CONSUMER_SECRET: return None
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
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    formatted_buttons = []
    for i, btn_text in enumerate(buttons):
        formatted_buttons.append({
            "type": "reply",
            "reply": {"id": f"btn_{i+1}", "title": btn_text[:20]}
        })
    payload = {
        "messaging_product": "whatsapp", "to": to, "type": "interactive",
        "interactive": {"type": "button", "body": {"text": text}, "action": {"buttons": formatted_buttons}}
    }
    requests.post(url, json=payload, headers=headers)

def send_whatsapp_message(to, text):
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}}
    
    try:
        res = requests.post(url, json=payload, headers=headers)
        # שורות אלו ידפיסו ללוגים של Render בדיוק מה פייסבוק חושבת על ההודעה!
        print(f"Envoi WhatsApp à {to} - Status: {res.status_code}")
        if res.status_code != 200:
            print(f"Erreur WhatsApp API: {res.text}")
    except Exception as e:
        print(f"Erreur de connexion WhatsApp: {e}")

def send_whatsapp_template(to, template_name, variables):
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    
    # הפיכת רשימת המשתנים שלנו לפורמט שפייסבוק דורשת
    parameters = [{"type": "text", "text": str(var)[:1000]} for var in variables]
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "he"}, # שפת התבנית שהגדרנו
            "components": [
                {
                    "type": "body",
                    "parameters": parameters
                }
            ]
        }
    }
    
    try:
        res = requests.post(url, json=payload, headers=headers)
        print(f"Envoi Template à {to} - Status: {res.status_code}")
        if res.status_code != 200:
            print(f"Erreur Template API: {res.text}")
    except Exception as e:
        print(f"Erreur de connexion WhatsApp: {e}")

@app.route("/", methods=["GET"])
def home(): return "Bot Français Google Sheets Flat JSON Actif !", 200

@app.route("/media/<filename>", methods=["GET"])
def serve_media(filename): return send_from_directory(MEDIA_DIR, filename)

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

    # 1. Menu Principal
    if current_state == "MAIN_MENU":
        if "commande" in text_lower:
            USER_STATES[from_number]["state"] = "WAITING_FOR_ORDER_ID"
            send_whatsapp_message(from_number, "Parfait. Veuillez saisir votre **numéro de commande** :")
        elif "générale" in text_lower or "generale" in text_lower:
            USER_STATES[from_number]["state"] = "GENERAL_QA"
            send_whatsapp_message(from_number, "Avec plaisir ! Veuillez écrire votre question en détail ici 👇")
        else:
            send_whatsapp_btn(from_number, "Veuillez choisir une option :", ["Ma commande 📦", "Question générale ❓"])

    # 2. Numéro de commande
    elif current_state == "WAITING_FOR_ORDER_ID":
        order_id = "".join(filter(str.isdigit, text_body))
        if not order_id:
            send_whatsapp_message(from_number, "Veuillez envoyer uniquement les chiffres de votre commande :")
            return make_response("EVENT_RECEIVED", 200)
            
        send_whatsapp_message(from_number, "Je vérifie cela sur le site... Un instant ⏳")
        order_info = get_woocommerce_order(order_id)
        
        if order_info == "NOT_FOUND":
            send_whatsapp_message(from_number, f"❌ Aucune commande trouvée avec le numéro {order_id}. Veuillez réessayer :")
        elif order_info is None:
            user_data["order_id"] = order_id
            user_data["customer_email"] = "Inconnu (Erreur)"
            USER_STATES[from_number]["state"] = "REPORT_ORDER_ISSUE"
            send_whatsapp_message(from_number, "Commande reçue. Veuillez détailler votre demande ici :")
        else:
            status_translations = {
                "pending": "En attente 💳", "processing": "En préparation 📦",
                "on-hold": "En attente ⏳", "completed": "Expédiée ! 🚀",
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
            
            success_msg = f"""Bonjour {customer_name}, commande #{order_id} trouvée !
🔹 *Statut :* {translated_status}
🔹 *Montant :* {total_price} {currency}
🔹 *Email :* {customer_email}

Choisissez une option pour continuer :"""
            
            USER_STATES[from_number]["state"] = "ORDER_MENU_OPTIONS"
            send_whatsapp_btn(from_number, success_msg, ["Remarque spéciale 📝", "Livraison 🚚", "Produit défectueux ⚠️"])

    # 3. Options commande
    elif current_state == "ORDER_MENU_OPTIONS":
        if "remarque" in text_lower:
            user_data["sub_topic"] = "הערה מיוחדת לגבי ההזמנה"
            USER_STATES[from_number]["state"] = "COLLECTING_ORDER_TEXT"
            send_whatsapp_message(from_number, "Veuillez écrire votre remarque ou modification demandée :")
        elif "livraison" in text_lower:
            user_data["sub_topic"] = "בעיה או שאלה לגבי המשלוח"
            USER_STATES[from_number]["state"] = "COLLECTING_ORDER_TEXT"
            send_whatsapp_message(from_number, "Veuillez détailler votre problème de livraison :")
        elif "défectueux" in text_lower or "defectueux" in text_lower:
            user_data["sub_topic"] = "מוצר פגום / בעיה במוצר"
            USER_STATES[from_number]["state"] = "WAITING_FOR_PHOTO"
            send_whatsapp_message(from_number, "Veuillez envoyer une photo du produit endommagé ici 📸 :")
        else:
            send_whatsapp_btn(from_number, "Veuillez cliquer sur un bouton :", ["Remarque spéciale 📝", "Livraison 🚚", "Produit défectueux ⚠️"])

    # 4. Collecte texte
    elif current_state == "COLLECTING_ORDER_TEXT":
        ticket = {
            "topic": f"הזמנה קיימת - {user_data.get('sub_topic')}",
            "order_id": user_data.get("order_id"),
            "customer_email": user_data.get("customer_email"),
            "site_info": user_data.get("raw_info", "N/A"),
            "user_message": text_body,
            "photo_url": "Pas d'image"
        }
        process_completed_ticket(from_number, ticket)
        send_whatsapp_message(from_number, "Votre demande a bien été enregistrée ! 💙")
        USER_STATES[from_number] = {"state": "MAIN_MENU", "data": {}}

    # 5. Collecte Photo
    elif current_state == "WAITING_FOR_PHOTO":
        photo_url = "Aucune image"
        if message.get("type") == "image":
            media_id = message["image"]["id"]
            photo_url = download_whatsapp_media(media_id)
            caption = message["image"].get("caption", "Sans texte")
            text_body = f"[תמונה מצורפת] - כיתוב: {caption}"
        else:
            text_body = f"[טקסט במקום תמונה]: {text_body}"

        ticket = {
            "topic": "הזמנה קיימת - מוצר פגום (צרפתית)",
            "order_id": user_data.get("order_id"),
            "customer_email": user_data.get("customer_email"),
            "site_info": user_data.get("raw_info", "N/A"),
            "user_message": text_body,
            "photo_url": photo_url
        }
        process_completed_ticket(from_number, ticket)
        send_whatsapp_message(from_number, "Merci pour la photo. Votre dossier a été transmis ! 💙")
        USER_STATES[from_number] = {"state": "MAIN_MENU", "data": {}}

    # 6. Question générale
    elif current_state == "GENERAL_QA":
        ticket = {
            "topic": "שאלה כללית מהאתר (צרפתית)",
            "order_id": "Lien Général",
            "customer_email": "Non spécifié",
            "site_info": "N/A",
            "user_message": text_body,
            "photo_url": "Pas d'image"
        }
        process_completed_ticket(from_number, ticket)
        send_whatsapp_message(from_number, "Merci ! Nous avons bien reçu votre question. 💙")
        USER_STATES[from_number] = {"state": "MAIN_MENU", "data": {}}

    return make_response("EVENT_RECEIVED", 200)

def process_completed_ticket(from_number, ticket):
    """עיבוד הפנייה: שליחת JSON שטוח ונקי לגוגל שיטס והתראת וואטסאפ למנהל"""
    ticket["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ticket["user_phone"] = from_number

    # החזרה ל-json=ticket בצירוף headers קשיחים כדי לוודא שגוגל שיטס יקרא את כל השדות בצורה נקייה
    if GOOGLE_SHEET_URL:
        try: 
            headers = {"Content-Type": "application/json"}
            requests.post(GOOGLE_SHEET_URL, json=ticket, headers=headers, timeout=7)
        except Exception as e: 
            print(f"Sheet Error: {e}")

    # בניית הסיכום בעברית לוואטסאפ של המנהל
    summary = f"""🚨 *פניית שירות חדשה מהאתר הצרפתי!*

📌 *נושא:* {ticket.get('topic')}
👤 *טלפון הלקוח:* {ticket.get('user_phone')}
📧 *מייל הלקוח:* {ticket.get('customer_email')}
📦 *מספר הזמנה:* {ticket.get('order_id')}
📊 *סטטוס באתר:* {ticket.get('site_info')}
💬 *תוכן הפנייה:* {ticket.get('user_message')}
🖼️ *קישור ישיר לתמונה:* {ticket.get('photo_url')}
📅 *זמן:* {ticket.get('timestamp')}"""

    # השהיה של שנייה למניעת חסימת כפל הודעות מהירה בפייסבוק
    time.sleep(1)

    # שליחת הודעת וואטסאפ למנהל
    if ADMIN_PHONE:
        send_whatsapp_message(ADMIN_PHONE, summary)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
