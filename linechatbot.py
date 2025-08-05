from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent,TextMessage, TextSendMessage
from selenium01 import search_advice_branch

app = Flask(__name__)

# Your LINE Channel Secret and Access Token
CHANNEL_SECRET = '8674ab6dc94c264cbd939631c07940c7'
CHANNEL_ACCESS_TOKEN = 'cJMkFOjDwKWlJ0saZXXkhOGvdElQVClznOqYWVAYVveQflKbvRiXcbQYl0IWjwSQuYx9jvX+fy8cqtjDC2vY/NA/3wkCIYXWScTlDmNmhnA7hNEZourNou1ZeboRZtX3IGHBiJA/iGXx0Rr/tsoM4AdB04t89/1O/w1cDnyilFU='

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# Webhook endpoint for LINE to call
@app.route("/", methods=['POST'])
def callback():
    # Get X-Line-Signature header value
    
    signature = request.headers['X-Line-Signature']

    # Get request body as text
    body = request.get_data(as_text=True)

    try:
        # Handle the webhook event
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_input = event.message.text.strip()
    branches = search_advice_branch(user_input)

    if branches:
        message = "📍 รายชื่อสาขา:\n" + "\n".join(f"{i+1}. {b}" for i, b in enumerate(branches))
    else:
        message = "ไม่พบสาขาในพื้นที่ที่คุณระบุ"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=message)  # ✅ ส่งเป็น string
    )

if __name__ == "__main__":
    app.run(port=5000)