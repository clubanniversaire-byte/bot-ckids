import os
import time
import requests
from datetime import datetime
from flask import Flask, request, make_response

app = Flask(__name__)

# ==========================================
# קונפיגורציה והגדרות משתנים
# ==========================================
# משתנה שליטה: True = מציג שגיאות טכניות (בשבילך). False = מצב לקוח אמיתי (הודעות אנושיות)
DEBUG_MODE = True 

ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_TOKEN_123")
GOOGLE_SHEET_URL = os.environ.get("GOOGLE_SHEET_URL")
ADMIN_PHONE = os.environ.get("ADMIN_PHONE")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

GEMINI_MODEL = "gemini-2.5-flash"

# קונפיגורציה של רוז ביוטי
SHOP_URL = os.environ.get("SHOP_URL", "https://ros-beauty.co.il/")
PICKUP_LOCATION_TEXT = os.environ.get("PICKUP_LOCATION_TEXT", "אקדמיה")
GEL_COURSE_URL = os.environ.get("GEL_COURSE_URL", "https://ros-beauty.co.il/product/%D7%A7%D7%95%D7%A8%D7%A1-%E2%81%A0nails-master/")
PEDICURE_COURSE_URL = os.environ.get("PEDICURE_COURSE_URL", "https://ros-beauty.co.il/product/master-padicure-%D7%A7%D7%95%D7%A8%D7%A1-%D7%9C%D7%A7-%D7%92%D7%93%D7%9C-%D7%90%D7%95%D7%A0%D7%9C%D7%99%D7%99%D7%9F-%D7%93%D7%99%D7%92%D7%99%D7%98%D7%9C%D7%99-%D7%A4%D7%93%D7%99%D7%A7%D7%95/")
PHOTO_COURSE_URL = os.environ.get("PHOTO_COURSE_URL", "https://ros-beauty.co.il/product/master-catalog/")

FINAL_SUFFIX = "\n\nזמני מענה: עד יום עסקים אחד.\nתודה על הסבלנות 💙"

USER_STATES = {}

def get_gateway_menu():
    return (
        "🚀 *ברוך הבא לבוט ההדגמות הרשמי שלי!* 🚀\n\n"
        "1️⃣ *בוט שירות לקוחות מובנה (היברידי)* - עובד לפי תפריטים, אבל מבין טקסט חופשי (נסה לכתוב 'איפה החבילה שלי' במקום ללחוץ 1).\n\n"
        "2️⃣ *בוט AI חופשי ואנושי* - איש מכירות וירטואלי שמדבר חופשי לגמרי.\n\n"
        "💡 *טיפ:* כתוב *התחלה* בכל שלב כדי לחזור לכאן."
    )

def get_ros_beauty_welcome():
    return (
        "🤖 *הפעלת את דמו שירות הלקוחות (היברידי)* 🤖\n"
        "היי 💙 תודה שפנית אלינו.\n"
        "כדי שנוכל לעזור לך בצורה הכי מהירה ומסודרת, בחרי את הנושא הרלוונטי (או כתבי לי במשפט חופשי מה הבעיה) 👇\n\n"
        "0️⃣ 🛒 מעבר לאתר לרכישה\n"
        "1️⃣ 📦 בירור סטטוס הזמנה\n"
        "2️⃣ 🧯 פגום / נזק / חוסר בהזמנה\n"
        "3️⃣ 📍 איסוף עצמי\n"
        "4️⃣ 🔁 שינוי / ביטול הזמנה\n"
        "5️⃣ 🎓 קורסים דיגיטליים\n"
        "6️⃣ ❓ שאלה כללית"
    )

def ask_gemini_chat(user_message):
    """פונקציה למצב AI חופשי עם מנגנון הגנה מעומסים וקריסה אלגנטית"""
    if not GEMINI_API_KEY:
        return "שגיאה: משתנה GEMINI_API_KEY לא מוגדר בשרת Render."
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    system_instruction = (
        "אתה נציג מכירות וירטואלי חכם, כריזמטי, מקצועי ואדיב של סוכנות האוטומציה וה-AI שלי. "
        "התפקיד שלך הוא לנהל שיחה חופשית וקולחת עם בעלי עסקים שמנסים את הבוט כרגע. "
        "תסביר להם בשפה ברורה (עברית) איך בוטים חכמים ואוטומציות יכולים לחסוך לעסק שלהם המון זמן. "
        "התשובות שלך צריכות להיות קצרות, ממוקדות ומותאמות לוואטסאפ. "
        "המטרה הסופית היא להציע להם להשאיר שם ומספר טלפון כדי שנחזור אליהם לשיחת ייעוץ בחינם."
    )
    
    payload = {
        "contents": [{"parts": [{"text": user_message}]}],
        "systemInstruction": {"parts": [{"text": system_instruction}]}
    }
    
    # מנגנון Retry - מנסה עד 3 פעמים אם יש עומס
    for attempt in range(3):
        try:
            response = requests.post(url, json=payload, timeout=10)
            res_json = response.json()
            
            if "error" in res_json:
                error_msg = res_json["error"].get("message", "Unknown error")
                print(f"Gemini API Error (Attempt {attempt+1}):", error_msg)
                
                # אם מדובר בשגיאת עומס, נמתין שנייה וננסה שוב
                if "high demand" in error_msg.lower() or "quota" in error_msg.lower() or response.status_code == 429:
                    time.sleep(1)
                    continue
                
                # אם זו שגיאה אחרת ולא עומס, נעצור ונחזיר פלט לפי המצב
                if DEBUG_MODE:
                    return f"❌ שגיאת API מג'מיני: {error_msg}"
                return "אופס, חלה שגיאה זמנית בחיבור. נסה לשלוח שוב את ההודעה בעוד רגע! ✨"
                
            return res_json['candidates'][0]['content']['parts'][0]['text'].strip()
            
        except Exception as e:
            print(f"Gemini Exception (Attempt {attempt+1}): {e}")
            if attempt < 2:
                time.sleep(1)
            else:
                if DEBUG_MODE:
                    return f"❌ שגיאת מערכת (Exception): {e}"
                return "מצטער, השרת חווה עומס רגעי. נסה שוב בעוד כמה שניות. ✨"

def classify_intent_with_gemini(user_message):
    """פונקציה נסתרת לנתב השיחות - כוללת מנגנון הגנה מפני קריסות שרת"""
    if not GEMINI_API_KEY: return None
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f"""
    אתה נתב שיחות חכם. הלקוח כתב: "{user_message}"
    לאיזה מהנושאים הבאים הלקוח מתכוון?
    0 - רכישה באתר
    1 - סטטוס הזמנה / איפה החבילה / מתי מגיע
    2 - מוצר פגום / נזק / חסר משהו / שבור
    3 - איסוף עצמי
    4 - שינוי / ביטול הזמנה
    5 - קורסים דיגיטליים / לימודים
    6 - שאלה כללית או לא קשור לאף אחד מהנ"ל
    
    החזר רק מספר אחד בין 0 ל-6 ללא שום טקסט נוסף.
    """
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    for attempt in range(3):
        try:
            response = requests.post(url, json=payload, timeout=5)
            res_json = response.json()
            if "error" in res_json:
                print(f"Intent Classification Error (Attempt {attempt+1}):", res_json["error"].get("message"))
                time.sleep(1)
                continue
            if "candidates" in res_json:
                result = res_json['candidates'][0]['content']['parts'][0]['text'].strip()
                if result in ["0", "1", "2", "3", "4", "5", "6"]:
                    return result
            return None
        except Exception as e:
            print(f"Intent Classification Exception (Attempt {attempt+1}): {e}")
            if attempt < 2: time.sleep(1)
    return None # במקרה של קריסה מוחלטת, נחזיר None והבוט המובנה פשוט יציג שוב את התפריט באלגנטיות

@app.route("/", methods=["GET"])
def home():
    return "Showcase Agency Bot is Live and Protected!", 200

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return make_response(request.args.get("hub.challenge"), 200)
    return make_response("Verification failed", 403)

@app.route("/webhook", methods=["POST"])
def message_received():
    data = request.get_json()
    if not (data.get("entry") and data["entry"][0].get("changes") and data["entry"][0]["changes"][0]["value"].get("messages")):
        return make_response("EVENT_RECEIVED", 200)

    message = data["entry"][0]["changes"][0]["value"]["messages"][0]
    from_number = message["from"]
    msg_type = message.get("type")
    
    text_body = message["text"]["body"].strip() if msg_type == "text" else ""
    media_id = message[msg_type]["id"] if msg_type in ["image", "video"] else None

    if text_body in ["התחלה", "start", "איתחול", "תפריט"]:
        USER_STATES[from_number] = {"mode": "GATEWAY", "state": "CHOOSE_MODE", "data": {}}
        send_whatsapp_message(from_number, get_gateway_menu())
        return make_response("EVENT_RECEIVED", 200)

    if from_number not in USER_STATES:
        USER_STATES[from_number] = {"mode": "GATEWAY", "state": "CHOOSE_MODE", "data": {}}
        send_whatsapp_message(from_number, get_gateway_menu())
        return make_response("EVENT_RECEIVED", 200)

    user_mode = USER_STATES[from_number]["mode"]
    current_state = USER_STATES[from_number].get("state")
    user_data = USER_STATES[from_number]["data"]

    # 1. שער כניסה
    if user_mode == "GATEWAY":
        if text_body == "1":
            USER_STATES[from_number] = {"mode": "STRUCTURED", "state": "MAIN_MENU", "data": {}}
            send_whatsapp_message(from_number, get_ros_beauty_welcome())
        elif text_body == "2":
            USER_STATES[from_number] = {"mode": "PURE_AI", "state": "CHAT", "data": {}}
            send_whatsapp_message(from_number, "✨ *הופעל מצב AI חופשי ואנושי* ✨\nאני פה כדי לשוחח. איך אוכל לעזור לעסק שלך?")
        else:
            send_whatsapp_message(from_number, "נא לבחור אפשרות:\n1️⃣ עבור בוט מובנה (היברידי)\n2️⃣ עבור בוט AI חופשי")

    # 2. מצב AI חופשי
    elif user_mode == "PURE_AI":
        ai_response = ask_gemini_chat(text_body)
        send_whatsapp_message(from_number, ai_response)

    # 3. מצב בוט מובנה (היברידי!)
    elif user_mode == "STRUCTURED":
        if current_state == "MAIN_MENU":
            choice = text_body
            if choice not in ["0", "1", "2", "3", "4", "5", "6"]:
                ai_intent = classify_intent_with_gemini(text_body)
                if ai_intent:
                    choice = ai_intent
            
            if choice == "0":
                send_whatsapp_message(from_number, f"מעבר לאתר לרכישה 🛒:\n{SHOP_URL}")
            elif choice == "1":
                USER_STATES[from_number]["state"] = "ORDER_STATUS_CHECK"
                send_whatsapp_message(from_number, "מומלץ קודם לבדוק את קישור המעקב שקיבלת.\nעדיין צריכה שנבדוק עבורך?\n1️⃣ כן\n2️⃣ לא")
            elif choice == "2":
                USER_STATES[from_number]["state"] = "DAMAGE_GET_ID"
                send_whatsapp_message(from_number, "מצטערות לשמוע 🙏 כדי שנוכל לבדוק, נא להשיב עם *מספר הזמנה*:")
            elif choice == "3":
                USER_STATES[from_number]["state"] = "PICKUP_GET_PAYMENT"
                send_whatsapp_message(from_number, f"איך בוצע התשלום?\n1️⃣ שולם מראש באתר\n2️⃣ תשלום במזומן")
            elif choice == "4":
                USER_STATES[from_number]["state"] = "CANCEL_GET_ID"
                send_whatsapp_message(from_number, "שינוי או ביטול הזמנה אפשריים כל עוד ההזמנה לא נארזה.\nנא להשיב עם *מספר הזמנה*:")
            elif choice == "5":
                USER_STATES[from_number]["state"] = "COURSES_MENU"
                send_whatsapp_message(from_number, "איזה כיף שהתעניינת בקורסים שלנו! בחרי:\n1️⃣ לק ג׳ל\n2️⃣ פדיקור\n3️⃣ צילום\n4️⃣ חזרה לתפריט")
            elif choice == "6":
                USER_STATES[from_number]["state"] = "GENERAL_GET_MSG"
                send_whatsapp_message(from_number, "נא לכתוב את פנייתך בפירוט:")
            else:
                # אם ה-AI נכשל והטקסט לא היה מספר חוקי, נחזיר את תפריט הבית באלגנטיות
                send_whatsapp_message(from_number, get_ros_beauty_welcome())

        # ... (שאר חלקי הלוגיקה של רוז ביוטי נשמרים זהים לחלוטין)
        elif current_state == "ORDER_STATUS_CHECK":
            if text_body == "2":
                send_whatsapp_message(from_number, "שמחות לשמוע 💙\n*(כתוב 'התחלה' כדי לחזור לשער)*")
                USER_STATES[from_number]["state"] = "MAIN_MENU"
            elif text_body == "1":
                USER_STATES[from_number]["state"] = "ORDER_STATUS_GET_ID"
                send_whatsapp_message(from_number, "נא להשיב עם *מספר הזמנה*:")
            else:
                send_whatsapp_message(from_number, "נא לבחור 1 או 2:")

        elif current_state == "ORDER_STATUS_GET_ID":
            user_data["order_id"] = text_body
            USER_STATES[from_number]["state"] = "ORDER_STATUS_GET_REASON"
            send_whatsapp_message(from_number, "מהי סיבת הפנייה?\n1️⃣ לא קיבלתי קישור מעקב\n2️⃣ עיכוב במשלוח\n3️⃣ סטטוס לא ברור\n4️⃣ אחר")

        elif current_state == "ORDER_STATUS_GET_REASON":
            reasons = {"1": "לא קיבלתי קישור מעקב", "2": "יש עיכוב במשלוח", "3": "סטטוס לא ברור", "4": "אחר"}
            if text_body in reasons:
                user_data["reason"] = reasons[text_body]
                process_completed_ticket(from_number, {"topic": "סטטוס הזמנה", "order_id": user_data["order_id"], "reason": user_data["reason"]})
                send_whatsapp_message(from_number, "תודה 💙 נחזור אלייך בהקדם." + FINAL_SUFFIX + "\n*(כתוב 'התחלה' לחזרה לשער)*")
                USER_STATES[from_number]["state"] = "MAIN_MENU"
            else:
                send_whatsapp_message(from_number, "נא לבחור סיבה בין 1 ל-4:")

        elif current_state == "DAMAGE_GET_ID":
            user_data["order_id"] = text_body
            USER_STATES[from_number]["state"] = "DAMAGE_GET_TYPE"
            send_whatsapp_message(from_number, "מהו סוג הבעיה?\n1️⃣ מוצר פגום\n2️⃣ נזק במשלוח\n3️⃣ פריט חסר")

        elif current_state == "DAMAGE_GET_TYPE":
            issues = {"1": "מוצר פגום", "2": "נזק במשלוח", "3": "פריט חסר"}
            if text_body in issues:
                user_data["issue_type"] = issues[text_body]
                USER_STATES[from_number]["state"] = "DAMAGE_GET_MEDIA"
                send_whatsapp_message(from_number, "נא לשלוח תמונה. אם אין, השיבי במילה *המשך* כדי לדלג:")
            else:
                send_whatsapp_message(from_number, "נא לבחור אפשרות בין 1 ל-3:")

        elif current_state == "DAMAGE_GET_MEDIA":
            user_data["media_url"] = f"Media ID: {media_id}" if media_id else "לא הועלה קובץ"
            process_completed_ticket(from_number, {"topic": "פגום / נזק", "order_id": user_data["order_id"], "issue_type": user_data["issue_type"], "media_url": user_data["media_url"]})
            send_whatsapp_message(from_number, "תודה 💙 נחזור אלייך עם פתרון בהקדם." + FINAL_SUFFIX + "\n*(כתוב 'התחלה' לחזרה לשער)*")
            USER_STATES[from_number]["state"] = "MAIN_MENU"

        elif current_state == "PICKUP_GET_PAYMENT":
            if text_body in ["1", "2"]:
                user_data["payment_method"] = "prepaid" if text_body == "1" else "cash"
                USER_STATES[from_number]["state"] = "PICKUP_GET_ID"
                send_whatsapp_message(from_number, "נא להשיב עם *מספר הזמנה*:")
            else:
                send_whatsapp_message(from_number, "נא לבחור 1 או 2:")

        elif current_state == "PICKUP_GET_ID":
            user_data["order_id"] = text_body
            USER_STATES[from_number]["state"] = "PICKUP_GET_NAME"
            send_whatsapp_message(from_number, "נא להשיב עם *שם מלא לאיסוף*:")

        elif current_state == "PICKUP_GET_NAME":
            user_data["full_name"] = text_body
            process_completed_ticket(from_number, {"topic": "איסוף עצמי", "order_id": user_data["order_id"], "full_name": user_data["full_name"], "payment_method": user_data["payment_method"], "pickup_location": PICKUP_LOCATION_TEXT})
            send_whatsapp_message(from_number, "תודה 💙 נחזור אלייך לתיאום מועד איסוף." + FINAL_SUFFIX + "\n*(כתוב 'התחלה' לחזרה לשער)*")
            USER_STATES[from_number]["state"] = "MAIN_MENU"

        elif current_state == "CANCEL_GET_ID":
            user_data["order_id"] = text_body
            USER_STATES[from_number]["state"] = "CANCEL_GET_TYPE"
            send_whatsapp_message(from_number, "סוג בקשה:\n1️⃣ שינוי הזמנה\n2️⃣ ביטול הזמנה")

        elif current_state == "CANCEL_GET_TYPE":
            if text_body in ["1", "2"]:
                user_data["request_type"] = "שינוי" if text_body == "1" else "ביטול"
                USER_STATES[from_number]["state"] = "CANCEL_GET_DETAILS"
                send_whatsapp_message(from_number, "נא לכתוב פירוט קצר:")
            else:
                send_whatsapp_message(from_number, "נא לבחור 1 או 2:")

        elif current_state == "CANCEL_GET_DETAILS":
            user_data["details"] = text_body
            process_completed_ticket(from_number, {"topic": "שינוי / ביטול", "order_id": user_data["order_id"], "request_type": user_data["request_type"], "details": user_data["details"]})
            send_whatsapp_message(from_number, "תודה 💙 הבקשה נקלטה." + FINAL_SUFFIX + "\n*(כתוב 'התחלה' לחזרה לשער)*")
            USER_STATES[from_number]["state"] = "MAIN_MENU"

        elif current_state == "COURSES_MENU":
            if text_body == "1": send_whatsapp_message(from_number, f"🖤 *לק ג׳ל*\n🔗 {GEL_COURSE_URL}")
            elif text_body == "2": send_whatsapp_message(from_number, f"🖤 *פדיקור*\n🔗 {PEDICURE_COURSE_URL}")
            elif text_body == "3": send_whatsapp_message(from_number, f"🖤 *צילום*\n🔗 {PHOTO_COURSE_URL}")
            elif text_body == "4": 
                USER_STATES[from_number]["state"] = "MAIN_MENU"
                send_whatsapp_message(from_number, get_ros_beauty_welcome())
            else: send_whatsapp_message(from_number, "נא לבחור אפשרות 1-4:")

        elif current_state == "GENERAL_GET_MSG":
            process_completed_ticket(from_number, {"topic": "שאלה כללית", "message": text_body})
            send_whatsapp_message(from_number, "תודה 💙 קיבלנו את הפנייה ונחזור אלייך בהקדם." + FINAL_SUFFIX + "\n*(כתוב 'התחלה' לחזרה לשער)*")
            USER_STATES[from_number]["state"] = "MAIN_MENU"

    return make_response("EVENT_RECEIVED", 200)

def process_completed_ticket(from_number, ticket):
    ticket["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ticket["user_phone"] = from_number

    if GOOGLE_SHEET_URL:
        try: requests.post(GOOGLE_SHEET_URL, json=ticket)
        except Exception as e: print(f"Sheet Error: {e}")

    if ADMIN_PHONE:
        summary = f"🚨 *טיקט שירות חדש (דמו רוז ביוטי)!*\n\n📌 *נושא:* {ticket.get('topic')}\n👤 *טלפון:* {ticket.get('user_phone')}\n"
        for k, v in ticket.items():
            if k not in ["topic", "user_phone", "timestamp"]: summary += f"🔹 *{k}:* {v}\n"
        send_whatsapp_message(ADMIN_PHONE, summary)

def send_whatsapp_message(to, text):
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}}
    response = requests.post(url, json=payload, headers=headers)
    print(f"סטטוס שליחה ל-{to}: {response.status_code}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
