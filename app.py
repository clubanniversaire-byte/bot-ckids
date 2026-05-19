import os
import requests
from datetime import datetime
from flask import Flask, request, make_response

app = Flask(__name__)

# ==========================================
# 8️⃣ קונפיגורציה (CONFIG) - פרמטרים הניתנים לעריכה
# ==========================================
SHOP_URL = os.environ.get("SHOP_URL", "https://ros-beauty.co.il/")
PICKUP_LOCATION_TEXT = os.environ.get("PICKUP_LOCATION_TEXT", "אקדמיה")
GEL_COURSE_URL = os.environ.get("GEL_COURSE_URL", "https://ros-beauty.co.il/product/%D7%A7%D7%95%D7%A8%D7%A1-%E2%81%A0nails-master/")
PEDICURE_COURSE_URL = os.environ.get("PEDICURE_COURSE_URL", "https://ros-beauty.co.il/product/master-padicure-%D7%A7%D7%95%D7%A8%D7%A1-%D7%9C%D7%A7-%D7%92%D7%93%D7%9C-%D7%90%D7%95%D7%A0%D7%9C%D7%99%D7%99%D7%9F-%D7%93%D7%99%D7%92%D7%99%D7%98%D7%9C%D7%99-%D7%A4%D7%93%D7%99%D7%A7%D7%95/")
PHOTO_COURSE_URL = os.environ.get("PHOTO_COURSE_URL", "https://ros-beauty.co.il/product/master-catalog/")

# מפתחות חיבור (מטא ורנדר)
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_TOKEN_123")
GOOGLE_SHEET_URL = os.environ.get("GOOGLE_SHEET_URL")
ADMIN_PHONE = os.environ.get("ADMIN_PHONE")

# הודעת סיום קבועה לכל טיקט
FINAL_SUFFIX = "\n\nזמני מענה: עד יום עסקים אחד.\nתודה על הסבלנות 💙"

# זיכרון זמני לשמירת מצב השיחה של הלקוחות (In-Memory State Machine)
USER_STATES = {}

def get_main_menu_text():
    return (
        "היי 💙\n"
        "תודה שפנית אלינו.\n"
        "האקדמיה אינה פועלת יותר כחנות פיזית, וכל רכישה מתבצעת דרך האתר בלבד.\n\n"
        "אנחנו נמצאות בתקופת מעבר תפעולית, ולכן ייתכנו שינויים קלים בזמני טיפול ומשלוחים.\n"
        "כדי שנוכל לעזור לך בצורה הכי מהירה ומסודרת, בחרי את הנושא הרלוונטי 👇\n\n"
        "0️⃣ 🛒 מעבר לאתר לרכישה\n"
        "1️⃣ 📦 בירור סטטוס הזמנה\n"
        "2️⃣ 🧯 פגום / נזק / חוסר בהזמנה\n"
        "3️⃣ 📍 איסוף עצמי\n"
        "4️⃣ 🔁 שינוי / ביטול הזמנה\n"
        "5️⃣ 🎓 קורסים דיגיטליים\n"
        "6️⃣ ❓ שאלה כללית\n\n"
        "💡 בכל שלב ניתן לכתוב *תפריט* כדי לחזור להתחלה."
    )

@app.route("/", methods=["GET"])
def home():
    return "Ros Beauty Bot is Live and Running!", 200

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
    
    # חילוץ הטקסט או המדיה מהודעת הלקוח
    text_body = message["text"]["body"].strip() if msg_type == "text" else ""
    text_lower = text_body.lower()
    media_id = message[msg_type]["id"] if msg_type in ["image", "video"] else None

    # מילת מפתח גלובלית לחזרה לתפריט הראשי
    if text_body in ["תפריט", "menu", "חזרה"]:
        USER_STATES[from_number] = {"state": "MAIN_MENU", "data": {}}
        send_whatsapp_message(from_number, get_main_menu_text())
        return make_response("EVENT_RECEIVED", 200)

    # אם המשתמש חדש, נגדיר לו את מצב ההתחלה
    if from_number not in USER_STATES:
        USER_STATES[from_number] = {"state": "MAIN_MENU", "data": {}}

    current_state = USER_STATES[from_number]["state"]
    user_data = USER_STATES[from_number]["data"]

    # ==========================================
    # לוגיקת ניהול המצבים (STATE MACHINE)
    # ==========================================
    
    if current_state == "MAIN_MENU":
        if text_body == "0":
            send_whatsapp_message(from_number, f"מעבר לאתר לרכישה 🛒:\n{SHOP_URL}")
        elif text_body == "1":
            USER_STATES[from_number]["state"] = "ORDER_STATUS_CHECK"
            msg = (
                "ברגע שההזמנה יוצאת מאיתנו למשלוח, נשלח אלייך קישור מעקב אוטומטי מחברת המשלוחים בהודעה / מייל 📦\n"
                "מומלץ קודם לבדוק את קישור המעקב שקיבלת.\n\n"
                "עדיין צריכה שנבדוק עבורך?\n"
                "1️⃣ כן, אשמח שתבדקו\n"
                "2️⃣ לא, הסתדרתי"
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
                f"איך בוצע / יבוצע התשלום עבור ההזמנה?\n"
                f"1️⃣ שולם מראש באתר\n"
                f"2️⃣ תשלום במזומן"
            )
            send_whatsapp_message(from_number, msg)
        elif text_body == "4":
            USER_STATES[from_number]["state"] = "CANCEL_GET_ID"
            send_whatsapp_message(from_number, "שינוי או ביטול הזמנה אפשריים כל עוד ההזמנה לא נארזה.\n\nנא להשיב עם *מספר הזמנה*:")
        elif text_body == "5":
            USER_STATES[from_number]["state"] = "COURSES_MENU"
            msg = (
                "איזה כיף שהתעניינת בקורסים שלנו 💅📸\n"
                "בחרי קורס לקבלת פרטים:\n\n"
                "1️⃣ קורס לק ג׳ל למקצועיות 💅\n"
                "2️⃣ קורס פדיקור 👣\n"
                "3️⃣ קורס צילום 📸\n"
                "4️⃣ 🔙 חזרה לתפריט הראשי"
            )
            send_whatsapp_message(from_number, msg)
        elif text_body == "6":
            USER_STATES[from_number]["state"] = "GENERAL_GET_MSG"
            send_whatsapp_message(from_number, "נא לכתוב את פנייתך/שאלתך בפירוט:")
        else:
            send_whatsapp_message(from_number, get_main_menu_text())

    # --- 📦 1) בירור סטטוס הזמנה ---
    elif current_state == "ORDER_STATUS_CHECK":
        if text_body == "2":
            send_whatsapp_message(from_number, "שמחות לשמוע 💙 אם תצטרכי משהו נוסף – אנחנו כאן.")
            USER_STATES[from_number] = {"state": "MAIN_MENU", "data": {}}
        elif text_body == "1":
            USER_STATES[from_number]["state"] = "ORDER_STATUS_GET_ID"
            send_whatsapp_message(from_number, "נא להשיב עם *מספר הזמנה*:")
        else:
            send_whatsapp_message(from_number, "נא לבחור אפשרות 1 או 2:")

    elif current_state == "ORDER_STATUS_GET_ID":
        user_data["order_id"] = text_body
        USER_STATES[from_number]["state"] = "ORDER_STATUS_GET_REASON"
        msg = (
            "מהי סיבת הפנייה?\n"
            "1️⃣ לא קיבלתי קישור מעקב\n"
            "2️⃣ יש עיכוב במשלוח\n"
            "3️⃣ סטטוס לא ברור\n"
            "4️⃣ אחר"
        )
        send_whatsapp_message(from_number, msg)

    elif current_state == "ORDER_STATUS_GET_REASON":
        reasons = {"1": "לא קיבלתי קישור מעקב", "2": "יש עיכוב במשלוח", "3": "סטטוס לא ברור", "4": "אחר"}
        if text_body in reasons:
            user_data["reason"] = reasons[text_body]
            ticket = {
                "topic": "סטטוס הזמנה",
                "order_id": user_data["order_id"],
                "reason": user_data["reason"]
            }
            process_completed_ticket(from_number, ticket)
            send_whatsapp_message(from_number, "תודה 💙 קיבלנו את הפרטים ונבדוק עבורך. נחזור אלייך בהקדם האפשרי." + FINAL_SUFFIX)
            USER_STATES[from_number] = {"state": "MAIN_MENU", "data": {}}
        else:
            send_whatsapp_message(from_number, "נא לבחור סיבה בין 1 ל-4:")

    # --- 🧯 2) פגום / נזק / חוסר ---
    elif current_state == "DAMAGE_GET_ID":
        user_data["order_id"] = text_body
        USER_STATES[from_number]["state"] = "DAMAGE_GET_TYPE"
        msg = (
            "מהו סוג הבעיה?\n"
            "1️⃣ מוצר פגום\n"
            "2️⃣ נזק במשלוח\n"
            "3️⃣ פריט חסר"
        )
        send_whatsapp_message(from_number, msg)

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
        ticket = {
            "topic": "פגום / נזק / חוסר",
            "order_id": user_data["order_id"],
            "issue_type": user_data["issue_type"],
            "media_url": user_data["media_url"]
        }
        process_completed_ticket(from_number, ticket)
        send_whatsapp_message(from_number, "תודה 💙 הפנייה נקלטה ונבדקת. נחזור אלייך עם פתרון בהקדם האפשרי." + FINAL_SUFFIX)
        USER_STATES[from_number] = {"state": "MAIN_MENU", "data": {}}

    # --- 📍 3) איסוף עצמי ---
    elif current_state == "PICKUP_GET_PAYMENT":
        if text_body in ["1", "2"]:
            if text_body == "1":
                user_data["payment_method"] = "prepaid"
            else:
                user_data["payment_method"] = "cash"
                send_whatsapp_message(from_number, "שימי לב 💙\nבתשלום במזומן, יש לוודא הגעה עם הסכום המדויק לתשלום ההזמנה. לא ניתן להתחייב לעודף.")
            
            USER_STATES[from_number]["state"] = "PICKUP_GET_ID"
            send_whatsapp_message(from_number, "נא להשיב עם *מספר הזמנה*:")
        else:
            send_whatsapp_message(from_number, "נא לבחור 1 (שולם באתר) או 2 (מזומן):")

    elif current_state == "PICKUP_GET_ID":
        user_data["order_id"] = text_body
        USER_STATES[from_number]["state"] = "PICKUP_GET_NAME"
        send_whatsapp_message(from_number, "נא להשיב עם *שם מלא לאיסוף*:")

    elif current_state == "PICKUP_GET_NAME":
        user_data["full_name"] = text_body
        ticket = {
            "topic": "איסוף עצמי",
            "order_id": user_data["order_id"],
            "full_name": user_data["full_name"],
            "payment_method": user_data["payment_method"],
            "pickup_location": PICKUP_LOCATION_TEXT
        }
        process_completed_ticket(from_number, ticket)
        send_whatsapp_message(from_number, "תודה 💙 קיבלנו את הפרטים ונבדוק שההזמנה מוכנה. נחזור אלייך לתיאום מועד ושעת איסוף." + FINAL_SUFFIX)
        USER_STATES[from_number] = {"state": "MAIN_MENU", "data": {}}

    # --- 🔁 4) שינוי / ביטול הזמנה ---
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
            send_whatsapp_message(from_number, "נא לבחור 1 (שינוי) או 2 (ביטול):")

    elif current_state == "CANCEL_GET_DETAILS":
        user_data["details"] = text_body
        ticket = {
            "topic": "שינוי / ביטול",
            "order_id": user_data["order_id"],
            "request_type": user_data["request_type"],
            "details": user_data["details"]
        }
        process_completed_ticket(from_number, ticket)
        send_whatsapp_message(from_number, "תודה 💙 הבקשה נקלטה ונבדקת. נחזור אלייך בהקדם." + FINAL_SUFFIX)
        USER_STATES[from_number] = {"state": "MAIN_MENU", "data": {}}

    # --- 🎓 5) קורסים דיגיטליים ---
    elif current_state == "COURSES_MENU":
        if text_body == "1":
            msg = (
                "🖤 *קורס לק ג׳ל למקצועיות* 💅\n"
                "קורס דיגיטלי מלא שייקח את הידע שלך לגבוה הבא.\n"
                f"למידע על הקורס ולרכישה לחצי כאן 👇\n🔗 {GEL_COURSE_URL}"
            )
            send_whatsapp_message(from_number, msg)
        elif text_body == "2":
            msg = (
                "🖤 *קורס פדיקור* 👣\n"
                "קורס דיגיטלי מקיף ומעמיק – תיאוריה + פרקטיקה.\n"
                f"למידע על הקורס ולרכישה לחצי כאן 👇\n🔗 {PEDICURE_COURSE_URL}"
            )
            send_whatsapp_message(from_number, msg)
        elif text_body == "3":
            msg = (
                "🖤 *קורס צילום* 📸\n"
                "קורס דיגיטלי להכנת תמונות מקצועיות למדיה ופרסום.\n"
                f"למידע על הקורס ולרכישה לחצי כאן 👇\n🔗 {PHOTO_COURSE_URL}"
            )
            send_whatsapp_message(from_number, msg)
        elif text_body == "4":
            USER_STATES[from_number] = {"state": "MAIN_MENU", "data": {}}
            send_whatsapp_message(from_number, get_main_menu_text())
        else:
            send_whatsapp_message(from_number, "נא לבחור אפשרות בין 1 ל-4:")

    # --- ❓ 6) שאלה כללית ---
    elif current_state == "GENERAL_GET_MSG":
        ticket = {
            "topic": "שאלה כללית",
            "message": text_body
        }
        process_completed_ticket(from_number, ticket)
        send_whatsapp_message(from_number, "תודה 💙 קיבלנו את הפנייה ונחזור אלייך בהקדם." + FINAL_SUFFIX)
        USER_STATES[from_number] = {"state": "MAIN_MENU", "data": {}}

    return make_response("EVENT_RECEIVED", 200)

# ==========================================
# פונקציות עזר וסנכרון נתונים
# ==========================================

def process_completed_ticket(from_number, ticket):
    """מרכזת את שליחת הטיקט המוגמר למנהל ולגוגל שיטס"""
    ticket["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ticket["user_phone"] = from_number

    # 1. שליחה לגוגל שיטס
    if GOOGLE_SHEET_URL:
        try:
            requests.post(GOOGLE_SHEET_URL, json=ticket)
        except Exception as e:
            print(f"שגיאה בסנכרון לגוגל שיטס: {e}")

    # 2. בניית הודעת סיכום מעוצבת למנהל
    if ADMIN_PHONE:
        summary = f"🚨 *טיקט שירות חדש נוצר!*\n\n" \
                  f"📌 *נושא:* {ticket.get('topic')}\n" \
                  f"👤 *טלפון לקוח:* {ticket.get('user_phone')}\n" \
                  f"⏰ *זמן:* {ticket.get('timestamp')}\n"
        
        if "order_id" in ticket: summary += f"🔢 *מספר הזמנה:* {ticket['order_id']}\n"
        if "reason" in ticket: summary += f"❓ *סיבה:* {ticket['reason']}\n"
        if "issue_type" in ticket: summary += f"⚠️ *סוג בעיה:* {ticket['issue_type']}\n"
        if "media_url" in ticket: summary += f"📸 *מדיה:* {ticket['media_url']}\n"
        if "full_name" in ticket: summary += f"📛 *שם מלא:* {ticket['full_name']}\n"
        if "payment_method" in ticket: summary += f"💳 *אופן תשלום:* {ticket['payment_method']}\n"
        if "pickup_location" in ticket: summary += f"📍 *מיקום איסוף:* {ticket['pickup_location']}\n"
        if "request_type" in ticket: summary += f"🔄 *סוג בקשה:* {ticket['request_type']}\n"
        if "details" in ticket: summary += f"📝 *פירוט:* {ticket['details']}\n"
        if "message" in ticket: summary += f"💬 *הודעה:* {ticket['message']}\n"

        send_whatsapp_message(ADMIN_PHONE, summary)

def send_whatsapp_message(to, text):
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
