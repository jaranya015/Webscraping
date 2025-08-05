# main.py
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from kfc_scraper import fetch_kfc_menu  # ✅ Import ฟังก์ชันจากไฟล์แยก

app = Flask(__name__)

# LINE Channel credentials
CHANNEL_SECRET = '8674ab6dc94c264cbd939631c07940c7'
CHANNEL_ACCESS_TOKEN = 'cJMkFOjDwKWlJ0saZXXkhOGvdElQVClznOqYWVAYVveQflKbvRiXcbQYl0IWjwSQuYx9jvX+fy8cqtjDC2vY/NA/3wkCIYXWScTlDmNmhnA7hNEZourNou1ZeboRZtX3IGHBiJA/iGXx0Rr/tsoM4AdB04t89/1O/w1cDnyilFU='

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

@app.route("/", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_input = event.message.text.strip().lower()

    if user_input == "menu" or "เมนู" in user_input:
        result = fetch_kfc_menu("https://www.kfc.co.th/menu/meals")
        if result["menu_items"]:
            menu_text = "📋 เมนู KFC:\n" + "\n".join(f"{i+1}. {item}" for i, item in enumerate(result["menu_items"]))
        else:
            menu_text = "ไม่สามารถดึงเมนูได้ในขณะนี้ 😔"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=menu_text)
        )
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="พิมพ์ 'menu' หรือ 'เมนู' เพื่อดูเมนู KFC 🍗")
        )

if __name__ == "__main__":
    app.run(port=5000)
