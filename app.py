import os
import requests
from datetime import datetime
from flask import Flask, request, make_response

app = Flask(__name__)

# ==========================================
# קונפיגורציה והגדרות משתנים
# ==========================================
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_TOKEN_123")
GOOGLE_SHEET_URL = os.environ.get("GOOGLE_SHEET_URL")
ADMIN_PHONE = os.environ.get("ADMIN_PHONE")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# קונפיגורציה של רוז ביוטי (מצב 1)
SHOP_URL = os.environ.get("SHOP_URL", "https://ros-beauty.co.il/")
PICKUP_LOCATION_TEXT = os.environ.get("PICKUP_LOCATION_TEXT", "אקדמיה")
GEL_COURSE_URL = os.environ.get("GEL_COURSE_URL", "https://ros-beauty.co.il/product/%D7%A7%D7%95%D7%A8%D7%A1-%E2%81%A0nails-master/")
PEDICURE_COURSE_URL = os.environ.get("PEDICURE_COURSE_URL", "https://ros-beauty.co.il/product/master-padicure-%D7%A7%D7%95%D7%A8%D7%A1-%D7%9C%D7%A7-%D7%92%D7%93%D7%9C-%D7%90%D7%95%D7%A0%D7%9C%D7%99%D7%99%D7%9F-%D7%93%D7%99%D7%92%D7%99%D7%98%D7%9C%D7%99-%D7%A4%D7%93%D7%99%D7%A7%D7%95/")
PHOTO_COURSE_URL = os.environ.get("PHOTO_COURSE_URL", "https://ros-beauty.co.il/product/master-catalog/")

FINAL_SUFFIX = "\n\nזמני מענה: עד יום עסקים אחד.\nתודה על הסבלנות 💙"

# זיכרון גלובלי למצב המשתמשים
USER_STATES = {}

def get_gateway_menu():
    return (
        "🚀 *ברוך הבא לבוט ההדגמות הרשמי שלי!* 🚀\n\n"
        "כאן תוכל לחוות את שני סוגי הבוטים המרכזיים שאני בונה לעסקים. "
        "בחר את סוג הבוט שברצונך לבחון מולי:\n\n"
        "1️⃣ *בוט שירות לקוחות מובנה (היברידי)* - עובד לפי תפריטים קשיחים ושלבים קבועים לאיסוף פרטים ופתיחת טיקטים (מבוסס על האפיון של רוז ביוטי).\n\n"
        "2️⃣ *בוט AI חופשי ואנושי (איש מכירות)* - בוט חכם שמדבר חופשי, מבין הקשר, עונה על שאלות ומנסה לסגור איתך פגישה.\n\n"
        "💡 *טיפ:* בכל שלב בשיחה (בשני המצבים), כתיבת המילה *התחלה* תאפס את הבוט ותחזיר אותך לתפריט הראשי הזה."
    )

def get_ros_beauty_welcome():
    return (
        "🤖 *הפעלת את דמו שירות הלקוחות (רוז ביוטי)* 🤖\n"
        "שים לב איך הבוט מנווט אותך בצורה מובנית:\n\n"
        "היי 💙 תודה שפנית אלינו.\n"
        "האקדמיה אינה פועלת יותר כחנות פיזית, וכל רכישה מתבצעת דרך האתר בלבד.\n\n"
        "אנחנו נמצאות בתקופת מעבר תפעולית, ולכן ייתכנו שינויים קלים בזמני טיפול ומשלוחים.\n"
        "כדי שנוכל לעזור לך בצורה הכי מהירה ומסודרת, בחרי את הנושא הרלוונטי 👇\n\n"
        "0️⃣ 🛒 מעבר לאתר לרכישה\n"
        "1️⃣ 📦 בירור סטטוס הזמנה\n"
        "2️⃣ 🧯 פגום / נזק / חוסר בהזמנה\n"
        "3️⃣ 📍 איסוף עצמי\n"
        "4️⃣ 🔁 שינוי / ביטול הזמנה\n"
        "5️⃣ 🎓 קורסים דיגיטליים\n"
        "6️⃣ ❓ שאלה כללית"
    )

def ask_gemini(user_message):
    """פונקציה הפונה ל-Gemini API החינמי ומנהלת שיחה אנושית"""
    if not GEMINI_API_KEY:
        return "שגיאה: מפתח Gemini API לא הוגדר בשרת. נא להוסיף את GEMINI_API_KEY במשתני הסביבה."
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    # הנחיית מערכת (System Prompt) שמגדירה ל-AI בדיוק מי הוא ואיך להתנהג
    system_instruction = (
        "אתה נציג מכירות וירטואלי חכם, כריזמטי, מקצועי ואדיב של סוכנות האוטומציה וה-AI שלי (הסוכנות של המפתח שבנה אותך). "
        "התפקיד שלך הוא לנהל שיחה חופשית וקולחת עם בעלי עסקים שמנסים את הבוט כרגע. "
        "תסביר להם בשפה ברורה (עברית) איך בוטים חכמים ואוטומציות יכולים לחסוך לעסק שלהם המון זמן, לענות ללקוחות 24/7, "
        "למנוע עומס משירות הלקוחות ולסגור לידים אוטומטית. "
        "התשובות שלך צריכות להיות קצרות, ממוקדות ומותאמות לוואטסאפ (בלי פסקאות ארוכות מדי). "
        "המטרה הסופית שלך בשיחה היא לעניין אותם, ובשלב מתקדם להציע להם להשאיר שם ומספר טלפון כדי שהמפתח (הבעלים של הסוכנות) יחזור אליהם לשיחת ייעוץ בחינם. "
        "אם הם משאירים פרטים, תודה להם ותגיד שנחזור אליהם בקרוב."
    )
    
    payload = {
        "contents": [{"parts": [{"text": user_message}]}],
        "systemInstruction": {"parts": [{"text": system_instruction}]}
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        res_json = response.json()
        return res_json['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        print(f"Gemini Error: {e}")
        return "מצטער, חלה שגיאה זמנית בחיבור ה-AI שלי. נסה שוב בעוד רגע."

@app.route("/", methods=["GET"])
def home():
    return "Showcase Agency Bot is Live!", 200

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
    
    if not (data.get("entry") and data["entry"][0].get("changes") and data["entry"][0]["changes"][0]["value"].get("messages")):
        return make_response("EVENT_RECEIVED", 200)

    message = data["entry"][0]["changes"][0]["value"]["messages"][0]
    from_number = message["from"]
    msg_type = message.get("type")
    
    text_body = message["text"]["body"].strip() if msg_type == "text" else ""
    media_id = message[msg_type]["id"] if msg_type in ["image", "video"] else None

    # מילת מפתח גלובלית לאיפוס וחזרה לשער הראשי
    if text_body in ["התחלה", "start", "איתחול", "תפריט"]:
        USER_STATES[from_number] = {"mode": "GATEWAY", "state": "CHOOSE_MODE", "data": {}}
        send_whatsapp_message(from_number, get_gateway_menu())
        return make_response("EVENT_RECEIVED", 200)

    # יצירת יוזר חדש בזיכרון אם הוא לא קיים
    if from_number not in USER_STATES:
        USER_STATES[from_number] = {"mode": "GATEWAY", "state": "CHOOSE_MODE", "data": {}}
        send_whatsapp_message(from_number, get_gateway_menu())
        return make_response("EVENT_RECEIVED", 200)

    user_mode = USER_STATES[from_number]["mode"]
    current_state = USER_STATES[from_number].get("state")
    user_data = USER_STATES[from_number]["data"]

    # ==========================================
    # ניתוב לפי מצב על (MODE ROUTER)
    # ==========================================
    
    # 1. מצב שער כניסה (Gateway)
    if user_mode == "GATEWAY":
        if text_body == "1":
            USER_STATES[from_number]["mode"] = "STRUCTURED"
            USER_STATES[from_number]["state"] = "MAIN_MENU"
            send_whatsapp_message(from_number, get_ros_beauty_welcome())
        elif text_body == "2":
            USER_STATES[from_number]["mode"] = "PURE_AI"
            welcome_ai = (
                "✨ *הופעל מצב AI חופשי ואנושי* ✨\n"
                "מעכשיו אתה לא מוגבל למספרים או תפריטים. אתה מוזמן לשוחח איתי חופשי! "
                "שאל אותי שאלות כמו: 'איך בוט יכול לעזור לעסק שלי?', 'כמה עולה לבנות מערכת כזו?', או כל מה שתרצה."
            )
            send_whatsapp_message(from_number, welcome_ai)
        else:
            send_whatsapp_message(from_number, "נא לבחור אפשרות:\n1️⃣ עבור בוט תפריטים מובנה\n2️⃣ עבור בוט AI חופשי")

    # 2. מצב בוט AI חופשי (Pure AI Mode)
    elif user_mode == "PURE_AI":
        # כל הודעה חופשית נשלחת ישירות ל-Gemini
        ai_response = ask_gemini(text_body)
        send_whatsapp_message(from_number, ai_response)

    # 3. מצב בוט מובנה (Structured State Machine - Ros Beauty)
    elif user_mode == "STRUCTURED":
        
        if current_state == "MAIN_MENU":
            if text_body == "0":
                send_whatsapp_message(from_number, f"מעבר לאתר לרכישה 🛒:\n{SHOP_URL}")
            elif text_body == "1":
                USER_STATES[from_number]["state"] = "ORDER_STATUS_CHECK"
                msg = (
                    "ברגע שההזמנה יוצאת מאיתנו למשלוח, נשלח אלייך קישור מעקב אוטומטי מחברת המשלוחים בהודעה / מייל 📦\n"
                    "מומלץ קודם לבדוק את קישור המעקב שקיבלת.\n\n"
                    "עדיין צריכה שנבדוק עבורך?\n1️⃣ כן, אשמח שתבדקו\n2️⃣ לא, הסתדרתי"
                )
                send_whatsapp_message(from_number, msg)
            elif text_body == "2":
                USER_STATES[from_number]["state"] = "DAMAGE_GET_ID"
                send_whatsapp_message(from_number, "מצטערות לשמוע 🙏 כדי שנוכל לבדוק ולטפל במהירות, נצטרך כמה פרטים.\n\nנא להשיב עם *מספר הזמנה*:")
            elif text_body == "3":
                USER_STATES[from_number]["state"] = "PICKUP_GET_PAYMENT"
                msg = (
                    f"איסוף עצמי מתבצע בתיאום מראש בלבד 💙\n"
                    f"האקדמיה אינה פתוחה לקנייה במקום. כל רכישה מתבצעת דרך האתר בלבד:\n{SHOP_URL}\n\n"
                    f"איך בוצע / יבוצע התשלום עבור ההזמנה?\n1️⃣ שולם מראש באתר\n2️⃣ תשלום במזומן"
                )
                send_whatsapp_message(from_number, msg)
            elif text_body == "4":
                USER_STATES[from_number]["state"] = "CANCEL_GET_ID"
                send_whatsapp_message(from_number, "שינוי או ביטול הזמנה אפשריים כל עוד ההזמנה לא נארזה.\n\nנא להשיב עם *מספר הזמנה*:")
            elif text_body == "5":
                USER_STATES[from_number]["state"] = "COURSES_MENU"
                msg = (
                    "איזה כיף שהתעניינת בקורסים שלנו 💅📸\nבחרי קורס לקבלת פרטים:\n\n"
                    "1️⃣ קורס לק ג׳ל למקצועיות 💅\n2️⃣ קורס פדיקור 👣\n3️⃣ קורס צילום 📸\n4️⃣ 🔙 חזרה לתפריט הדמו"
                )
                send_whatsapp_message(from_number, msg)
            elif text_body == "6":
                USER_STATES[from_number]["state"] = "GENERAL_GET_MSG"
                send_whatsapp_message(from_number, "נא לכתוב את פנייתך/שאלתך בפירוט:")
            else:
                send_whatsapp_message(from_number, get_ros_beauty_welcome())

        elif current_state == "ORDER_STATUS_CHECK":
            if text_body == "2":
                send_whatsapp_message(from_number, "שמחות לשמוע 💙 אם תצטרכי משהו נוסף – אנחנו כאן.\n\n*(כתוב 'התחלה' כדי לחזור לשער הראשי)*")
                USER_STATES[from_number]["state"] = "MAIN_MENU"
            elif text_body == "1":
                USER_STATES[from_number]["state"] = "ORDER_STATUS_GET_ID"
                send_whatsapp_message(from_number, "נא להשיב עם *מספר הזמנה*:")
            else:
                send_whatsapp_message(from_number, "נא לבחור אפשרות 1 או 2:")

        elif current_state == "ORDER_STATUS_GET_ID":
            user_data["order_id"] = text_body
            USER_STATES[from_number]["state"] = "ORDER_STATUS_GET_REASON"
            msg = "מהי סיבת הפנייה?\n1️⃣ לא קיבלתי קישור מעקב\n2️⃣ יש עיכוב במשלוח\n3️⃣ סטטוס לא ברור\n4️⃣ אחר"
            send_whatsapp_message(from_number, msg)

        elif current_state == "ORDER_STATUS_GET_REASON":
            reasons = {"1": "לא קיבלתי קישור מעקב", "2": "יש עיכוב במשלוח", "3": "סטטוס לא ברור", "4": "אחר"}
            if text_body in reasons:
                user_data["reason"] = reasons[text_body]
                process_completed_ticket(from_number, {"topic": "סטטוס הזמנה", "order_id": user_data["order_id"], "reason": user_data["reason"]})
                send_whatsapp_message(from_number, "תודה 💙 קיבלנו את הפרטים ונבדוק עבורך. נחזור אלייך בהקדם האפשרי." + FINAL_SUFFIX + "\n\n*(כתוב 'התחלה' לחזרה לשער הראשי)*")
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
                send_whatsapp_message(from_number, "נא לשלוח כעת תמונה או וידאו של המוצר/נזק. אם אין ברשותך, השיבי במילה *המשך* כדי לדלג:")
            else:
                send_whatsapp_message(from_number, "נא לבחור אפשרות בין 1 ל-3:")

        elif current_state == "DAMAGE_GET_MEDIA":
            user_data["media_url"] = f"WhatsApp Media ID: {media_id}" if media_id else "לא הועלה קובץ"
            process_completed_ticket(from_number, {"topic": "פגום / נזק / חוסר", "order_id": user_data["order_id"], "issue_type": user_data["issue_type"], "media_url": user_data["media_url"]})
            send_whatsapp_message(from_number, "תודה 💙 הפנייה נקלטה ונבדקת. נחזור אלייך עם פתרון בהקדם האפשרי." + FINAL_SUFFIX + "\n\n*(כתוב 'התחלה' לחזרה לשער הראשי)*")
            USER_STATES[from_number]["state"] = "MAIN_MENU"

        elif current_state == "PICKUP_GET_PAYMENT":
            if text_body in ["1", "2"]:
                user_data["payment_method"] = "prepaid" if text_body == "1" else "cash"
                if text_body == "2":
                    send_whatsapp_message(from_number, "שימי לב 💙\nבתשלום במזומן, יש לוודא הגעה עם הסכום המדויק לתשלום ההזמנה. לא ניתן להתחייב לעודף.")
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
            send_whatsapp_message(from_number, "תודה 💙 קיבלנו את הפרטים ונבדוק שההזמנה מוכנה. נחזור אלייך לתיאום מועד ושעת איסוף." + FINAL_SUFFIX + "\n\n*(כתוב 'התחלה' לחזרה לשער הראשי)*")
            USER_STATES[from_number]["state"] = "MAIN_MENU"

        elif current_state == "CANCEL_GET_ID":
            user_data["order_id"] = text_body
            USER_STATES[from_number]["state"] = "CANCEL_GET_TYPE"
            send_whatsapp_message(from_number, "מהו סוג הבקשה?\n1️⃣ שינוי הזמנה\n2️⃣ ביטול הזמנה")

        elif current_state == "CANCEL_GET_TYPE":
            if text_body in ["1", "2"]:
                user_data["request_type"] = "שינוי" if text_body == "1" else "ביטול"
                USER_STATES[from_number]["state"] = "CANCEL_GET_DETAILS"
                send_whatsapp_message(from_number, "נא לכתוב פירוט קצר של הבקשה:")
            else:
                send_whatsapp_message(from_number, "נא לבחור 1 או 2:")

        elif current_state == "CANCEL_GET_DETAILS":
            user_data["details"] = text_body
            process_completed_ticket(from_number, {"topic": "שינוי / ביטול", "order_id": user_data["order_id"], "request_type": user_data["request_type"], "details": user_data["details"]})
            send_whatsapp_message(from_number, "תודה 💙 הבקשה נקלטה ונבדקת. נחזור אלייך בהקדם." + FINAL_SUFFIX + "\n\n*(כתוב 'התחלה' לחזרה לשער הראשי)*")
            USER_STATES[from_number]["state"] = "MAIN_MENU"

        elif current_state == "COURSES_MENU":
            if text_body == "1":
                send_whatsapp_message(from_number, f"🖤 *קורס לק ג׳ל למקצועיות* 💅\nלמידע ולרכישה לחצי כאן 👇\n🔗 {GEL_COURSE_URL}")
            elif text_body == "2":
                send_whatsapp_message(from_number, f"🖤 *קורס פדיקור* 👣\nלמידע ולרכישה לחצי כאן 👇\n🔗 {PEDICURE_COURSE_URL}")
            elif text_body == "3":
                send_whatsapp_message(from_number, f"🖤 *קורס צילום* 📸\nלמידע ולרכישה לחצי כאן 👇\n🔗 {PHOTO_COURSE_URL}")
            elif text_body == "4":
                USER_STATES[from_number]["state"] = "MAIN_MENU"
                send_whatsapp_message(from_number, get_ros_beauty_welcome())
            else:
                send_whatsapp_message(from_number, "נא לבחור אפשרות בין 1 ל-4:")

        elif current_state == "GENERAL_GET_MSG":
            process_completed_ticket(from_number, {"topic": "שאלה כללית", "message": text_body})
            send_whatsapp_message(from_number, "תודה 💙 קיבלנו את הפנייה ונחזור אלייך בהקדם." + FINAL_SUFFIX + "\n\n*(כתוב 'התחלה' לחזרה לשער הראשי)*")
            USER_STATES[from_number]["state"] = "MAIN_MENU"

    return make_response("EVENT_RECEIVED", 200)

# ==========================================
# פונקציות סנכרון ושליחה
# ==========================================

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
