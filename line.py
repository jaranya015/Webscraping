from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TemplateSendMessage,
    CarouselTemplate, CarouselColumn, URITemplateAction,
    PostbackTemplateAction
)
import time
from selenium import webdriver
import chromedriver_autoinstaller
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ✅ แก้จาก _name_ → __name__
app = Flask(__name__)
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TemplateSendMessage,
    CarouselTemplate, CarouselColumn, URITemplateAction,
    PostbackTemplateAction
)
import time
from selenium import webdriver
import chromedriver_autoinstaller
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ✅ แก้จาก _name_ → __name__
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
    if event.message.text.strip().lower() == "menu":
        print("[Bot] Received 'menu' command, fetching KFC menu...")
        items = fetch_kfc_menu("https://www.kfc.co.th/menu/meals")[:5]

        if not items:
            print("[Bot] ❌ No items fetched.")
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="ขออภัย ไม่สามารถดึงเมนูได้ในขณะนี้")
            )
            return

        print(f"[Bot] ✅ Fetched {len(items)} items, building carousel...")
        columns = []
        for idx, itm in enumerate(items, start=1):
            print(f"[Bot]  - Item {idx}: id={itm['id']} title={itm['title']} image={itm['image']}")
            columns.append(
                CarouselColumn(
                    thumbnail_image_url=itm["image"],
                    title=f"Item {idx}",
                    text=itm["title"][:40] or "No title",
                    actions=[
                        URITemplateAction(label="ดูภาพ", uri=itm["image"]),
                        PostbackTemplateAction(label="รายละเอียด", data=f"DETAILS_{itm['id']}")
                    ]
                )
            )

        template_message = TemplateSendMessage(
            alt_text="KFC Menu Carousel",
            template=CarouselTemplate(columns=columns)
        )
        line_bot_api.reply_message(event.reply_token, template_message)
        print("[Bot] ✅ Carousel sent.")
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="พิมพ์ ‘menu’ เพื่อดูเมนู KFC แบบ Carousel")
        )

def fetch_kfc_menu(url):
    chromedriver_autoinstaller.install()
    chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)

    wait = WebDriverWait(driver, 20)
    wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR,
         "#Meals.sopac-small-menu-container, #Meals.sopac-medium-menu-container")
    ))
    print("[Fetch] Container loaded.")

    try:
        btn = wait.until(EC.element_to_be_clickable(
            (By.ID, "onetrust-accept-btn-handler")))
        btn.click()
        print("[Fetch] Accepted cookies.")
    except:
        print("[Fetch] No cookies button.")

    cards = driver.find_elements(By.CSS_SELECTOR,
        "#Meals .plp-item-card.small-menu-product-card, "
        "#Meals .plp-item-card.medium-menu-product-card"
    )
    print(f"[Fetch] Found {len(cards)} product cards.")

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

            print(f"[Fetch] Card #{idx}: id={prod_id}, title={title}, src={src}")
            items.append({"id": prod_id, "title": title, "image": src})
        except Exception as e:
            print(f"[Fetch] ❌ Error reading card #{idx}: {e}")

    print(f"[Fetch] Successfully built {len(items)} items.")
    driver.quit()
    return items

# ✅ แก้จาก _name_ → __name__
if __name__ == "__main__":
    print("[App] Starting Flask server on port 5000...")
    app.run(port=5000)

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
    if event.message.text.strip().lower() == "menu":
        print("[Bot] Received 'menu' command, fetching KFC menu...")
        items = fetch_kfc_menu("https://www.kfc.co.th/menu/meals")[:5]

        if not items:
            print("[Bot] ❌ No items fetched.")
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="ขออภัย ไม่สามารถดึงเมนูได้ในขณะนี้")
            )
            return

        print(f"[Bot] ✅ Fetched {len(items)} items, building carousel...")
        columns = []
        for idx, itm in enumerate(items, start=1):
            print(f"[Bot]  - Item {idx}: id={itm['id']} title={itm['title']} image={itm['image']}")
            columns.append(
                CarouselColumn(
                    thumbnail_image_url=itm["image"],
                    title=f"Item {idx}",
                    text=itm["title"][:40] or "No title",
                    actions=[
                        URITemplateAction(label="ดูภาพ", uri=itm["image"]),
                        PostbackTemplateAction(label="รายละเอียด", data=f"DETAILS_{itm['id']}")
                    ]
                )
            )

        template_message = TemplateSendMessage(
            alt_text="KFC Menu Carousel",
            template=CarouselTemplate(columns=columns)
        )
        line_bot_api.reply_message(event.reply_token, template_message)
        print("[Bot] ✅ Carousel sent.")
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="พิมพ์ ‘menu’ เพื่อดูเมนู KFC แบบ Carousel")
        )

def fetch_kfc_menu(url):
    chromedriver_autoinstaller.install()
    chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)

    wait = WebDriverWait(driver, 20)
    wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR,
         "#Meals.sopac-small-menu-container, #Meals.sopac-medium-menu-container")
    ))
    print("[Fetch] Container loaded.")

    try:
        btn = wait.until(EC.element_to_be_clickable(
            (By.ID, "onetrust-accept-btn-handler")))
        btn.click()
        print("[Fetch] Accepted cookies.")
    except:
        print("[Fetch] No cookies button.")

    cards = driver.find_elements(By.CSS_SELECTOR,
        "#Meals .plp-item-card.small-menu-product-card, "
        "#Meals .plp-item-card.medium-menu-product-card"
    )
    print(f"[Fetch] Found {len(cards)} product cards.")

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

            print(f"[Fetch] Card #{idx}: id={prod_id}, title={title}, src={src}")
            items.append({"id": prod_id, "title": title, "image": src})
        except Exception as e:
            print(f"[Fetch] ❌ Error reading card #{idx}: {e}")

    print(f"[Fetch] Successfully built {len(items)} items.")
    driver.quit()
    return items

# ✅ แก้จาก _name_ → __name__
if __name__ == "__main__":
    print("[App] Starting Flask server on port 5000...")
    app.run(port=5000)
