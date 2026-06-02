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
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_TOKEN_123")
ADMIN_PHONE = os.environ.get("ADMIN_PHONE")
GOOGLE_SHEET_URL = os.environ.get("GOOGLE_SHEET_URL")

# Connexion WooCommerce / WordPress
WC_STORE_URL = os.environ.get("WC_STORE_URL") 
WC_CONSUMER_KEY = os.environ.get("WC_CONSUMER_KEY")
WC_CONSUMER_SECRET = os.environ.get("WC_CONSUMER_SECRET")

USER_STATES = {}

def get_welcome_menu():
    return f"""👋 *Bonjour ! Bienvenue sur notre service client* ✨
Comment puis-je vous aider aujourd'hui ? Veuillez choisir une option :

1️⃣ *J'ai une question concernant une commande existante* 📦
2️⃣ *J'ai une autre question générale* ❓

💡 _Vous pouvez écrire *Début* à tout moment pour revenir ici._"""

def get_woocommerce_order(order_id):
    """Récupération de la commande depuis WordPress en temps réel"""
    if not WC_STORE_URL or not WC_CONSUMER_KEY or not WC_CONSUMER_SECRET:
        print("Erreur: Variables WooCommerce manquantes sur le serveur Render.")
        return None
        
    url = f"{WC_STORE_URL.rstrip('/')}/wp-json/wc/v3/orders/{order_id}"
    
    try:
        response = requests.get(url, auth=(WC_CONSUMER_KEY, WC_CONSUMER_SECRET), timeout=8)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return "NOT_FOUND"
        else:
            print(f"WordPress Error Code: {response.status_code}")
            return None
    except Exception as e:
        print(f"Exception WooCommerce: {e}")
        return None

@app.route("/", methods=["GET"])
def home(): 
    return "Le bot WhatsApp Français est en ligne et corrigé !", 200

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
    text_body = message["text"]["body"].strip() if message.get("type") == "text" else ""
    text_lower = text_body.lower()

    # Mots-clés de réinitialisation
    if text_lower in ["debut", "début", "start", "menu", "bonjour", "salut"]:
        USER_STATES[from_number] = {"state": "MAIN_MENU", "data": {}}
        send_whatsapp_message(from_number, get_welcome_menu())
        return make_response("EVENT_RECEIVED", 200)

    if from_number not in USER_STATES:
        USER_STATES[from_number] = {"state": "MAIN_MENU", "data": {}}
        send_whatsapp_message(from_number, get_welcome_menu())
        return make_response("EVENT_RECEIVED", 200)

    current_state = USER_STATES[from_number]["state"]
    user_data = USER_STATES[from_number]["data"]

    # --- LOGIQUE DU BOT ---
    
    # 1. Menu Principal
    if current_state == "MAIN_MENU":
        if text_body == "1":
            USER_STATES[from_number]["state"] = "WAITING_FOR_ORDER_ID"
            send_whatsapp_message(from_number, "Parfait. Pour que je puisse vérifier, veuillez saisir votre **numéro de commande** (uniquement les chiffres, ex: 4205) :")
        elif text_body == "2":
            USER_STATES[from_number]["state"] = "GENERAL_QA"
            send_whatsapp_message(from_number, "Avec plaisir ! Veuillez écrire votre question en détail ici, et notre équipe vous répondra dans les plus brefs délais 👇")
        else:
            send_whatsapp_message(from_number, "Veuillez choisir une option valide :\n1️⃣ Pour une commande\n2️⃣ Pour une question générale")

    # 2. Vérification de la commande sur WordPress
    elif current_state == "WAITING_FOR_ORDER_ID":
        order_id = "".join(filter(str.isdigit, text_body))
        
        if not order_id:
            send_whatsapp_message(from_number, "Je n'ai pas compris le numéro de commande. Veuillez envoyer uniquement des chiffres (ex: 5014) :")
            return make_response("EVENT_RECEIVED", 200)
            
        send_whatsapp_message(from_number, "C'est noté, je vérifie cela sur le site... Un instant ⏳")
        
        order_info = get_woocommerce_order(order_id)
        
        if order_info == "NOT_FOUND":
            send_whatsapp_message(from_number, f"❌ Je n'ai trouvé aucune commande avec le numéro {order_id}. Veuillez vérifier le numéro et réessayer :")
        elif order_info is None:
            user_data["order_id"] = order_id
            USER_STATES[from_number]["state"] = "REPORT_ORDER_ISSUE"
            error_fallback_msg = f"""Bien reçu, il s'agit de la commande {order_id}. Notre site subit un léger ralentissement et je n'ai pas pu récupérer le statut automatiquement.

Veuillez détailler votre demande ou votre problème concernant cette commande, un conseiller va prendre le relais :"""
            send_whatsapp_message(from_number, error_fallback_msg)
        else:
            status_translations = {
                "pending": "En attente de paiement 💳",
                "processing": "En cours de préparation 📦",
                "on-hold": "En attente ⏳",
                "completed": "Terminée et expédiée ! 🚀",
                "cancelled": "Annulée ❌",
                "refunded": "Remboursée 💰",
                "failed": "Échouée ❌"
            }
            
            raw_status = order_info.get("status", "unknown")
            translated_status = status_translations.get(raw_status, raw_status)
            total_price = order_info.get("total", "0")
            currency = order_info.get("currency", "€")
            customer_name = order_info.get("billing", {}).get("first_name", "Client")
            
            success_msg = f"""Bonjour {customer_name}, j'ai trouvé votre commande ! 📜

🔹 *Numéro de commande :* {order_id}
🔹 *Statut actuel :* {translated_status}
🔹 *Montant total :* {total_price} {currency}

Tout est-il correct, ou avez-vous une autre question concernant cette commande ?
1️⃣ Tout est correct, merci !
2️⃣ J'ai un problème / besoin d'un conseiller"""

            user_data["order_id"] = order_id
            user_data["raw_info"] = f"Status: {translated_status}, Total: {total_price}"
            USER_STATES[from_number]["state"] = "ORDER_FOLLOW_UP"
            send_whatsapp_message(from_number, success_msg)

    # 3. Options après affichage de la commande
    elif current_state == "ORDER_FOLLOW_UP":
        if text_body == "1":
            send_whatsapp_message(from_number, "Ravi d'avoir pu vous aider ! 😊 Si vous avez besoin d'autre chose, écrivez simplement *Début*.")
            USER_STATES[from_number] = {"state": "MAIN_MENU", "data": {}}
        elif text_body == "2":
            USER_STATES[from_number]["state"] = "REPORT_ORDER_ISSUE"
            send_whatsapp_message(from_number, "Désolé d'entendre cela. Veuillez détailler votre problème ici (produit défectueux, retard, changement d'adresse, etc.) et un conseiller vous répondra dans les plus brefs délais :")
        else:
            send_whatsapp_message(from_number, "Veuillez choisir option 1 ou 2 :")

    # 4. Enregistrement d'un problème sur commande
    elif current_state == "REPORT_ORDER_ISSUE":
        ticket = {
            "topic": "בעיה בהזמנה קיימת (צרפתית)",
            "order_id": user_data.get("order_id"),
            "site_info": user_data.get("raw_info", "Non récupéré"),
            "user_message": text_body
        }
        process_completed_ticket(from_number, ticket)
        send_whatsapp_message(from_number, "Votre demande a bien été enregistrée. Un conseiller va vérifier la situation et reviendra vers vous très vite ! 💙")
        USER_STATES[from_number] = {"state": "MAIN_MENU", "data": {}}

    # 5. Question générale
    elif current_state == "GENERAL_QA":
        ticket = {
            "topic": "שאלה כללית מהאתר (צרפתית)",
            "user_message": text_body
        }
        process_completed_ticket(from_number, ticket)
        
        general_success_msg = f"""Merci pour votre message. Nous avons bien reçu votre question et un membre de notre équipe vous répondra très rapidement ! 💙

_(Écrivez *Début* pour revenir au menu principal)_"""
        send_whatsapp_message(from_number, general_success_msg)
        USER_STATES[from_number] = {"state": "MAIN_MENU", "data": {}}

    return make_response("EVENT_RECEIVED", 200)

def process_completed_ticket(from_number, ticket):
    """Enregistrement du ticket dans Google Sheets et alerte Admin"""
    ticket["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ticket["user_phone"] = from_number

    if GOOGLE_SHEET_URL:
        try: requests.post(GOOGLE_SHEET_URL, json=ticket)
        except Exception as e: print(f"Sheet Error: {e}")

    if ADMIN_PHONE:
        summary = f"🚨 *פניית שירות חדשה בבוט הצרפתי!*\n\n📌 *סוג:* {ticket.get('topic')}\n👤 *טלפון:* {ticket.get('user_phone')}\n📦 *מספר הזמנה:* {ticket.get('order_id', 'ללא')}\n"
        summary += f"💬 *תוכן הפנייה:* {ticket.get('user_message')}"
        send_whatsapp_message(ADMIN_PHONE, summary)

def send_whatsapp_message(to, text):
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}}
    response = requests.post(url, json=payload, headers=headers)
    print(f"Envoi à {to}: {response.status_code}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
