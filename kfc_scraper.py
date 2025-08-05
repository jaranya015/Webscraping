import time
from selenium import webdriver
import chromedriver_autoinstaller
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def fetch_kfc_menu(url):
    chromedriver_autoinstaller.install()
    chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument('--headless')  # ปิดหน้าต่าง UI ถ้าต้องการ

    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)

    wait = WebDriverWait(driver, 20)

    try:
        # รอให้เมนูโหลด
        wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "#Meals .plp-item-card")
        ))
        print("[Fetch] ✅ Loaded product cards.")
    except Exception as e:
        print("[Fetch] ❌ Failed to load menu:", e)
        driver.quit()
        return []

    # คลิกปุ่ม Cookies ถ้ามี
    try:
        btn = wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
        btn.click()
        print("[Fetch] ✅ Accepted cookies.")
    except:
        print("[Fetch] ⚠️ No cookie button found or clickable.")

    # ดึงรายการเมนูจากทั้ง small และ medium
    cards = driver.find_elements(By.CSS_SELECTOR,
        "#Meals .plp-item-card.small-menu-product-card, "
        "#Meals .plp-item-card.medium-menu-product-card"
    )

    print(f"[Fetch] 🔍 Found {len(cards)} product cards.")

    items = []
    for idx, card in enumerate(cards[:10], start=1):
        try:
            driver.execute_script("arguments[0].scrollIntoView();", card)
            time.sleep(0.5)

            img_el = card.find_element(By.CSS_SELECTOR, "img")
            title_el = card.find_element(By.CSS_SELECTOR, ".small-menu-product-header, .menu-product-header")

            prod_id = card.get_attribute("id") or f"item_{idx}"
            title = title_el.text.strip()
            src = img_el.get_attribute("src")

            print(f"[Fetch] ✅ #{idx}: {title} ({src})")
            items.append({"id": prod_id, "title": title, "image": src})
        except Exception as e:
            print(f"[Fetch] ⚠️ Failed to process card #{idx}:", e)

    driver.quit()
    return items
