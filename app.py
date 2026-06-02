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
    return (
        "👋 *Bonjour ! Bienvenue sur notre service client* ✨\n"
        "Comment puis-je vous aider aujourd'hui ? Veuillez choisir une option :\n\n"
        "1️⃣ *J'ai une question concernant une commande existante* 📦\n"
        "2️⃣ *J'ai une autre question générale* ❓\n\n"
        "💡 _Vous pouvez écrire *Début* à tout moment pour revenir ici._"
    )

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
    return "Le bot WhatsApp Français est en ligne !", 200

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

    # Mots-clés de réinitialisation (Français & Anglais)
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
            # En cas de problème de connexion technique avec le site
            user_data["order_id"] = order_id
            USER_STATES[from_number]["state"] = "REPORT_ORDER_ISSUE"
            send_whatsapp_message(from_number, f"Bien reçu, il s'agit de la commande {order_id}. Notre site subit un léger ralentissement et je n'ai pas pu récupérer le statut automatiquement.\n\
