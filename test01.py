from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    TemplateSendMessage, CarouselTemplate, CarouselColumn,
    URIAction, PostbackEvent, PostbackTemplateAction
)
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import chromedriver_autoinstaller
import time

app = Flask(__name__)

# LINE credentials
CHANNEL_SECRET = '8674ab6dc94c264cbd939631c07940c7'  # 🔁 Replace with your Channel Secret
CHANNEL_ACCESS_TOKEN = 'cJMkFOjDwKWlJ0saZXXkhOGvdElQVClznOqYWVAYVveQflKbvRiXcbQYl0IWjwSQuYx9jvX+fy8cqtjDC2vY/NA/3wkCIYXWScTlDmNmhnA7hNEZourNou1ZeboRZtX3IGHBiJA/iGXx0Rr/tsoM4AdB04t89/1O/w1cDnyilFU='  # 🔁 Replace with your Channel Access Token

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

def fetch_kfc_menu(url):
    chromedriver_autoinstaller.install()
    chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument("--headless")  # ถ้าไม่ต้องการเปิด browser
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)

    wait = WebDriverWait(driver, 20)
    wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR,
         "#Meals.sopac-small-menu-container, #Meals.sopac-medium-menu-container")
    ))

    try:
        btn = wait.until(EC.element_to_be_clickable(
            (By.ID, "onetrust-accept-btn-handler")))
        btn.click()
    except:
        pass

    cards = driver.find_elements(By.CSS_SELECTOR,
        "#Meals .plp-item-card.small-menu-product-card, "
        "#Meals .plp-item-card.medium-menu-product-card"
    )

    items = []
    for idx, card in enumerate(cards[:5], start=1):
        driver.execute_script("arguments[0].scrollIntoView();", card)
        time.sleep(0.5)

        try:
            img_el = card.find_element(By.CSS_SELECTOR,
                "img.small-menu-product-image, img.medium-menu-product-image"
            )
            title_el = card.find_element(By.CSS_SELECTOR,
                ".small-menu-product-header, .menu-product-header"
            )

            prod_id = card.get_attribute("id") or f"item_{idx}"
            title = title_el.text.strip()
            src = img_el.get_attribute("src")

            items.append({"id": prod_id, "title": title, "image": src})
        except Exception as e:
            print(f"[Fetch] Error reading card #{idx}: {e}")

    driver.quit()
    return items


def get_menu_details_by_name(product_name: str):
    chromedriver_autoinstaller.install()
    driver = webdriver.Chrome()

    driver.get("https://www.kfc.co.th/menu/meals")

    try:
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
        ).click()
    except:
        pass

    try:
        name_element = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (By.XPATH, f"//div[contains(@class,'menu-product-header') and text()='{product_name}']"))
        )
    except:
        driver.quit()
        return f"ไม่พบเมนูชื่อ: {product_name}", ""

    product_card = name_element.find_element(By.XPATH, "./ancestor::div[contains(@class,'plp-item-card')]")
    product_id = product_card.get_attribute("id")

    product_url = f"https://www.kfc.co.th/menu/meals/{product_id}-prod"
    driver.get(product_url)

    # รายการย่อย 1: badge_text
    try:
        detail_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "textbadgecontainer"))
        )
        badge_text = detail_element.text.strip()
    except:
        badge_text = "ไม่มีข้อมูลเพิ่มเติม"

    # รายการย่อย 2: คำอธิบาย (ถ้ามี)
    try:
        desc_element = driver.find_element(By.CLASS_NAME, "product-description")
        description = desc_element.text.strip()
    except:
        description = "ไม่มีคำอธิบายเมนู"

    driver.quit()
    return badge_text, description



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
    text = event.message.text.strip()

    if text.lower() == "menu":
        items = fetch_kfc_menu("https://www.kfc.co.th/menu/meals")[:5]

        if not items:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="ขออภัย ไม่สามารถดึงเมนูได้ในขณะนี้")
            )
            return

        columns = []
        for idx, itm in enumerate(items, start=1):
            columns.append(
                CarouselColumn(
                    thumbnail_image_url=itm["image"],
                    title=itm["title"][:40],
                    text="กดดูรายละเอียดหรือภาพเมนู 🍗",
                    actions=[
                        URIAction(label="ดูภาพ", uri=itm["image"]),
                        PostbackTemplateAction(label="รายละเอียด", data=f"DETAILS_{itm['id']}")
                    ]
                )
            )

        template_message = TemplateSendMessage(
            alt_text="KFC Menu Carousel",
            template=CarouselTemplate(columns=columns)
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    else:
        # ผู้ใช้พิมพ์ชื่อเมนูเอง
        product_name = text
        badge_text, description = get_menu_details_by_name(product_name)

        if "ไม่พบเมนูชื่อ" in badge_text:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=badge_text)
            )
            return

        # แสดงรายละเอียดเมนูทั้งหมดในข้อความเดียว
        reply_text = (
            f"📋 รายละเอียดเมนู '{product_name}':\n\n"
            f"{badge_text}\n2 PCS. WINGZ ZABB"
            
        )

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )




@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data
    if data.startswith("DETAILS_"):
        menu_id = data.replace("DETAILS_", "")
        all_items = fetch_kfc_menu("https://www.kfc.co.th/menu/meals")
        target_item = next((item for item in all_items if item["id"] == menu_id), None)

        if not target_item:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="❌ ไม่พบข้อมูลเมนูที่เลือก")
            )
            return

        # รับข้อมูล 2 รายการจากฟังก์ชัน
        badge_text, description = get_menu_details_by_name(target_item["title"])

        # รวมข้อความให้แสดง 2 รายการย่อย
        reply_text = (
            f"🍗 รายละเอียดของเมนู\n『{target_item['title']}』\n\n"
            f"📌 รายละเอียด: {badge_text}\n"
            f"📝 คำอธิบาย: {description}"
        )

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))


if __name__ == "__main__":
    app.run(port=5000)
