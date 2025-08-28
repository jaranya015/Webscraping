# main.py
import os
import json
import requests 
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from konvy_scraper import fetch_raw_html,  Lip_Gloss_Plumpers
from linebot.models import PostbackAction, PostbackEvent

from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage,
    CarouselTemplate, CarouselColumn, URITemplateAction,  MessageAction
)
from konvy_scraper import (
    fetch_konvy_products_by_category, fetch_skincare_subcategories,
    fetch_makeup_subcategories, fetch_lips_subcategories, parse_lip_category_html
)

app = Flask(__name__)

# LINE Channel credentials
CHANNEL_SECRET = '8674ab6dc94c264cbd939631c07940c7'
CHANNEL_ACCESS_TOKEN = 'cJMkFOjDwKWlJ0saZXXkhOGvdElQVClznOqYWVAYVveQflKbvRiXcbQYl0IWjwSQuYx9jvX+fy8cqtjDC2vY/NA/3wkCIYXWScTlDmNmhnA7hNEZourNou1ZeboRZtX3IGHBiJA/iGXx0Rr/tsoM4AdB04t89/1O/w1cDnyilFU='

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

OLLAMA_API_URL = "http://localhost:11434/api/generate"

def normalize_user_input(user_input, categories):   # <<< NEW
    """
    ส่งข้อความไปให้ Ollama เพื่อ normalize คำที่ผู้ใช้พิมพ์
    """
    prompt = f"""
    ผู้ใช้พิมพ์ว่า: "{user_input}"
    หมวดหมู่ที่รองรับ: {list(categories.keys())}

    จงตอบเพียงแค่ชื่อหมวดหมู่จากรายการด้านบนที่ใกล้เคียงที่สุด
    ถ้าไม่มีที่ตรงหรือใกล้เคียง ให้ตอบว่า "unknown"
    """

    try:
        response = requests.post(OLLAMA_API_URL, json={
            "model": "llama3:instruct",
            "prompt": prompt,
            "stream": False
        })

        if response.status_code == 200:
            result = response.json().get("response", "").strip().lower()
            return result
        else:
            return "unknown"
    except Exception as e:
        print("Ollama error:", e)
        return "unknown"


# เพิ่ม Dictionary สำหรับหมวดหมู่ย่อยของลิปสติก
LIPS_SUBCATEGORIES = {
    "lip gloss & plumpers": "https://www.konvy.com/list/lip-gloss/",
    "lip liner": "https://www.konvy.com/list/lip-liner/",
    "lip oil & color balm": "https://www.konvy.com/list/lip-oil-and-color-balm/",
    "lip primer & concealer": "https://www.konvy.com/list/lip-primer-and-concealer/",
    "lip stain & tint": "https://www.konvy.com/list/lip-stain-and-tint/",
    "lipstick": "https://www.konvy.com/list/lipstick/",
    "liquid lipsticks": "https://www.konvy.com/list/liquid-lipsticks/"
}

@app.route("/", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

STATIC_CATEGORIES = {
    "skincare": {
        "link": "https://www.konvy.com/mall/list.php?param=113-0-0-0&from=category",
        "image": "https://s3.konvy.com/static/mall/2017/0517/14950106604061.jpg"
    },
    "personal care": {
        "link": "https://www.konvy.com/mall/list.php?param=116-0-0-0&from=category",
        "image": "https://s3.konvy.com/static/mall/2025/0320/17424554306761.jpg"
    },
    "makeup": {
        "link": "https://www.konvy.com/mall/list.php?param=114-0-0-0&from=category",
        "image": "https://s3.konvy.com/static/mall/2018/0718/15318964499369.jpg"
    },
    "fragrance": {
        "link": "https://www.konvy.com/mall/list.php?param=115-0-0-0&from=category",
        "image": "https://s3.konvy.com/static/mall/2025/0318/17422805869901.jpg"
    },
    "beauty tools": {
        "link": "https://www.konvy.com/mall/list.php?param=8009-0-0-0&from=category",
        "image": "https://s3.konvy.com/static/mall/2025/0326/17429751669801.jpg"
    },
    "health care & supply": {
        "link": "https://www.konvy.com/mall/list.php?param=119-0-0-0&from=category",
        "image": "https://i.ibb.co/k2D8YjF/health-care-supply-category.jpg"
    },
    "baby & mom": {
        "link": "https://www.konvy.com/mall/list.php?param=2993-0-0-0&from=category",
        "image": "https://s3.konvy.com/static/mall/2022/1122/16691116597927.jpg"
    },
    "fashion & lifestyle": {
        "link": "https://www.konvy.com/mall/list.php?param=5996-0-0-0&from=category",
        "image": "https://i.ibb.co/V9h431X/fashion-lifestyle-category.jpg"
    },
    "household": {
        "link": "https://www.konvy.com/mall/list.php?param=6894-0-0-0&from=category",
        "image": "https://i.ibb.co/gJFkS0p/household-category.jpg"
    },
    "toys & games": {
        "link": "https://www.konvy.com/mall/list.php?param=7730-0-0-0&from=category",
        "image": "https://i.ibb.co/gV8Y3Rj/toys-games-category.jpg"
    }
}

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_input = event.message.text.strip().lower()

    print(f"[Bot] Received user input: {user_input}")

    # 1️⃣ ตรวจสอบคำเฉพาะก่อน normalize
    if "lip gloss" in user_input:
        normalized = "lip gloss & plumpers"
    elif any(word in user_input for word in ["lips", "ลิป", "ปากสวย", "ขอลิป"]):
        normalized = "lips"
    elif any(word in user_input for word in ["makeup", "เครื่องสำอาง", "เมคอัพ"]):
        normalized = "makeup"
    elif any(word in user_input for word in ["skincare", "สกินแคร์", "ผิวหน้า"]):
        normalized = "skincare"
    else:
        # 2️⃣ Normalize ด้วย Ollama สำหรับคำอื่น ๆ
        ALL_CATEGORIES = {k.lower(): v for k, v in {**STATIC_CATEGORIES, **LIPS_SUBCATEGORIES}.items()}
        normalized = normalize_user_input(user_input, ALL_CATEGORIES)

    print(f"[Bot] Normalized input: {normalized}")

    # 3️⃣ ถ้าไม่พบหมวดหมู่
    if normalized == "unknown":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="ไม่พบหมวดหมู่ที่ใกล้เคียงค่ะ ลองพิมพ์ใหม่อีกครั้ง 🧐")
        )
        return

    # 4️⃣ ถ้า user พิมพ์ "อยากสวย" ส่ง Static Categories
    if "อยากสวย" in user_input:
        columns = []
        for name, data in list(STATIC_CATEGORIES.items())[:5]:
            columns.append(
                CarouselColumn(
                    thumbnail_image_url=data.get("image", "https://placehold.co/300x300/f9fafb/0f172a?text=Category"),
                    title=name.title()[:40],
                    text="คลิกเพื่อดูหมวดหมู่",
                    actions=[URITemplateAction(label="ดูหมวดหมู่", uri=data["link"])]
                )
            )
        template_message = TemplateSendMessage(
            alt_text="Konvy Category Carousel",
            template=CarouselTemplate(columns=columns)
        )
        line_bot_api.reply_message(event.reply_token, template_message)
        return

    # 5️⃣ Lip Gloss & Plumpers
    if normalized == "lip gloss & plumpers":
        products = Lip_Gloss_Plumpers()
        if not products:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="ไม่พบสินค้าในหมวด Lip Gloss & Plumpers 😔")
            )
            return

        columns = []
        for prod in products[:5]:
            columns.append(
                CarouselColumn(
                    thumbnail_image_url=prod.get("image", "https://placehold.co/300x300/f9fafb/0f172a?text=Product"),
                    title=prod.get("name", "N/A")[:40],
                    text=f"ราคา: ฿{prod.get('price', 'N/A')}",
                    actions=[
                        URITemplateAction(label="ดูสินค้า", uri=prod["link"]),
                        PostbackAction(label="รายละเอียดสินค้า", data=f"desc|{prod['name']}|{prod.get('price','N/A')}|{prod['link']}")
                    ]
                )
            )
        template_message = TemplateSendMessage(
            alt_text="Lip Gloss & Plumpers",
            template=CarouselTemplate(columns=columns)
        )
        line_bot_api.reply_message(event.reply_token, template_message)
        return




    # 6️⃣ Lips Subcategories
    if normalized == "lips":
        subcategories = fetch_lips_subcategories()
        if not subcategories:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="ไม่สามารถดึงหมวดหมู่ย่อยของ Lips ได้ 😔")
            )
            return

        columns = []
        for cat in subcategories[:10]:
            columns.append(
                CarouselColumn(
                    thumbnail_image_url=cat.get("image", "https://placehold.co/300x300/f9fafb/0f172a?text=Subcategory"),
                    title=cat.get("name", "N/A")[:40],
                    text=f"ดูสินค้าในหมวด {cat.get('name', 'N/A')}",
                    actions=[URITemplateAction(label="ดูสินค้า", uri=cat["link"])]
                )
            )

        template_message = TemplateSendMessage(
            alt_text="Konvy Lips Subcategories",
            template=CarouselTemplate(columns=columns)
        )
        line_bot_api.reply_message(event.reply_token, template_message)
        return

    # 7️⃣ Makeup Subcategories
    if normalized == "makeup":
        subcategories = fetch_makeup_subcategories()
        if not subcategories:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="ไม่สามารถดึงหมวดหมู่ย่อยของ Makeup ได้ 😔")
            )
            return

        columns = []
        for cat in subcategories[:10]:
            columns.append(
                CarouselColumn(
                    thumbnail_image_url=cat.get("image", "https://placehold.co/300x300/f9fafb/0f172a?text=Subcategory"),
                    title=cat.get("name", "N/A")[:40],
                    text=f"ดูสินค้าในหมวด {cat.get('name', 'N/A')}",
                    actions=[URITemplateAction(label="ดูสินค้า", uri=cat["link"])]
                )
            )
        template_message = TemplateSendMessage(
            alt_text="Konvy Makeup Subcategories",
            template=CarouselTemplate(columns=columns)
        )
        line_bot_api.reply_message(event.reply_token, template_message)
        return

    # 8️⃣ Skincare Subcategories
    if normalized == "skincare":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="ตอนนี้ยังไม่รองรับการแสดงผล Skincare ค่ะ")
        )
        return

    # 9️⃣ Static Categories
    if normalized in STATIC_CATEGORIES:
        category_data = STATIC_CATEGORIES[normalized]
        products = fetch_konvy_products_by_category(category_data["link"])
        if not products:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"ไม่พบสินค้าในหมวดหมู่ {normalized} 😔")
            )
            return

        columns = []
        for prod in products[:5]:
            columns.append(
                CarouselColumn(
                    thumbnail_image_url=prod.get("image", "https://placehold.co/300x300/f9fafb/0f172a?text=Product"),
                    title=prod.get("name", "N/A")[:40],
                    text=f"ราคา: {prod.get('price', 'N/A')}",
                    actions=[URITemplateAction(label="ดูสินค้า", uri=prod["link"])]
                )
            )
        template_message = TemplateSendMessage(
            alt_text=f"สินค้าหมวด {normalized}",
            template=CarouselTemplate(columns=columns)
        )
        line_bot_api.reply_message(event.reply_token, template_message)
        return

    #  🔟 Fallback
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="กรุณาพิมพ์ 'อยากสวย' เพื่อดูหมวดหมู่ หรือพิมพ์ชื่อหมวดหมู่ที่คุณสนใจ")
    )
@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data
    if data.startswith("desc|"):
        parts = data.split("|")
        product_name = parts[1]
        product_price = parts[2] if len(parts) > 2 else "N/A"
        product_link = parts[3] if len(parts) > 3 else "#"

        product_descriptions = {
            "Jabs x Bellygom Lip Gloss Plumper SPF50+ PA++++ 3g": 
                "Jabs x Bellygom Lip Gloss Plumper SPF50+ PA++++ 3g ลิปพลัมเพอร์กันแดด...",
            "ROM&amp;ND Glasting Color Gloss 4g #06 Deepen Moor":
                "ROM&amp;ND Glasting Color Gloss 4g #06 Deepen Moor ลิปกลอส...",
            "Time Phoria Lunara Frost 3D Lip Gloss 4ml #011 Odyssey":
                "Time Phoria Lunara Frost 3D Lip Gloss 4ml #011 Odyssey..."
        }

        text = product_descriptions.get(product_name, "ไม่พบรายละเอียดสินค้า 😔")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"{product_name}\nราคา: {product_price}\n{text}\nดูสินค้าเพิ่มเติม: {product_link}")
        )



if __name__ == "__main__":
    app.run(port=5000, debug=True)
