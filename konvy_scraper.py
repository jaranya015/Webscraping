# konvy_scraper.py
import time
import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

def parse_lip_category_html(html):
    """
    ดึงข้อมูลสินค้าจาก HTML ของหน้าหมวดหมู่ย่อยลิป
    คืนค่า list ของ dict: [{"name":..., "link":..., "price":..., "image":...}, ...]
    """
    soup = BeautifulSoup(html, "html.parser")
    products = []

def get_driver():
    """Helper function to set up and return a Chrome WebDriver."""
    chromedriver_autoinstaller.install()
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=options)


def fetch_konvy_categories(url="https://www.konvy.com/"):
    driver = get_driver()
    driver.get(url)

    try:
        close_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div.dialog_guide .close"))
        )
        close_btn.click()
    except:
        pass

    try:
        close_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div.v-modal .login_close_btn"))
        )
        close_btn.click()
    except:
        pass

    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    categories = []
    for cat in soup.select("a#topNavBtn, a.topNavBtn"):
        name = cat.get_text(strip=True)
        link = cat.get("href")
        if not link:
            continue
        categories.append({
            "name": name,
            "link": "https://www.konvy.com" + link if link.startswith("/") else link
        })

    return categories


def fetch_konvy_products_by_category(url):
    driver = get_driver()
    driver.get(url)

    try:
        close_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div.dialog_guide .close"))
        )
        close_btn.click()
    except:
        pass
    
    try:
        close_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div.v-modal .login_close_btn"))
        )
        close_btn.click()
    except:
        pass

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.product-item, ul.product-module li"))
        )
    except Exception as e:
        print(f"❌ Error waiting for products: {e}")
        driver.quit()
        return []

    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    products = []
    for item in soup.select("div.product-item, ul.product-module li"):
        name_tag = item.select_one("p.product-name")
        price_tag = item.select_one("span.ky-v-baseline") or item.select_one("div.price strong")
        image_tag = item.select_one("img")
        link_tag = item.select_one("a")

        if not (name_tag and price_tag and image_tag and link_tag):
            continue

        name = name_tag.get_text(strip=True)
        link = "https://www.konvy.com" + link_tag.get("href") if link_tag.get("href") else "N/A"
        price = price_tag.get_text(strip=True)
        image = image_tag.get("original") or image_tag.get("src")
        
        products.append({
            "name": name,
            "link": link,
            "price": price,
            "image": image
        })

    return products


def fetch_skincare_subcategories():
    return [
        {"name": "Mask", "link": "https://www.konvy.com/list/mask/", "image": "https://s3.konvy.com/static/mall/2021/1219/16398912827601.jpg"},
        {"name": "Skincare Set", "link": "https://www.konvy.com/list/sets-and-travel-kits/", "image": "https://s3.konvy.com/static/mall/2017/0517/14950106604061.jpg"},
        {"name": "Cleanser & Exfoliator", "link": "https://www.konvy.com/list/cleansing/", "image": "https://s3.konvy.com/static/mall/2021/1217/16397343692254.jpg"},
        {"name": "Moisturizer", "link": "https://www.konvy.com/list/moisturizer/", "image": "https://s3.konvy.com/static/mall/2021/1217/16397311389732.jpg"},
        {"name": "Lip Care", "link": "https://www.konvy.com/list/lip-care/", "image": "https://s3.konvy.com/static/mall/2017/0517/14950100372550.jpg"}
    ]

def fetch_makeup_subcategories():
    return [
        {"name": "Lips", "link": "https://www.konvy.com/list/lip-makeup/", "image": "https://s3.konvy.com/static/mall/2018/0718/15318964499369.jpg"},
        {"name": "Special Set", "link": "https://www.konvy.com/list/makeup-palette-and-sets/", "image": "https://s3.konvy.com/static/mall/2017/0524/14956128326666.jpg"},
        {"name": "Face", "link": "https://www.konvy.com/list/face-makeup/", "image": "https://s3.konvy.com/static/mall/2022/1123/16691884192574.jpg"}
    ]

def fetch_lips_subcategories():
    return [
        {"name": "Lip Gloss & Plumpers", "link": "https://www.konvy.com/list/lip-gloss/", "image": "https://s3.konvy.com/static/team/2024/0705/17201444121400_280x280.jpg.webp"},
        {"name": "Lip Liner", "link": "https://www.konvy.com/list/lip-liner/", "image": "https://s3.konvy.com/static/team/2023/0904/16938262789520_280x280.jpg.webp"},
        {"name": "Lip Oil & Color Balm", "link": "https://www.konvy.com/list/lip-oil-and-color-balm/", "image": "https://s3.konvy.com/static/team/2025/0227/17406238276845_280x280.jpg.webp"},
        {"name": "Lip Primer & Concealer", "link": "https://www.konvy.com/list/lip-primer-and-concealer/", "image": "https://s3.konvy.com/static/team/2025/0723/17532421332259_280x280.jpg.webp"},
        {"name": "Lip Stain & Tint", "link": "https://www.konvy.com/list/lip-stain-and-tint/", "image": "https://s3.konvy.com/static/team/2025/0708/17519685273883_280x280.jpg.webp"},
        {"name": "Lipstick", "link": "https://www.konvy.com/list/lipstick/", "image": "https://s3.konvy.com/static/team/2025/0724/17533415129343_280x280.jpg.webp"},
        {"name": "Liquid Lipsticks", "link": "https://www.konvy.com/list/liquid-lipsticks/", "image": "https://s3.konvy.com/static/team/2023/0912/16944917104339_280x280.jpg.webp"}
    ]
def Lip_Gloss_Plumpers():
    return [
        {"name": "Jabs x Bellygom Lip Gloss Plumper SPF50+ PA++++ 3g", "link": "https://www.konvy.com/jabs/jabs-x-bellygom-lip-gloss-plumper-spf50%2b-pa%2b%2b%2b%2b-3g-115476.html", "image": "https://s3.konvy.com/static/team/2025/0610/17495492268538_280x280.jpg.webp"},
        {"name": "ROM&amp;ND Glasting Color Gloss 4g #06 Deepen Moor", "link": "https://www.konvy.com/rom%26nd/rom%26nd-glasting-color-gloss-4g-06-deepen-moor-101249.html", "image": "https://s3.konvy.com/static/team/2024/0821/17242365811963_280x280.jpg.webp"},
        {"name": "Time Phoria Lunara Frost 3D Lip Gloss 4ml #011 Odyssey", "link": "https://www.konvy.com/time-phoria/time-phoria-lunara-frost-3d-lip-gloss-4ml-011-odyssey-117442.html", "image": "https://s3.konvy.com/static/team/2025/0725/17534429985389_280x280.jpg.webp"},
       
    ]

# konvy_scraper.py
def fetch_raw_html(url):
    """ดึง HTML ของหน้าเว็บด้วย Selenium"""
    driver = get_driver()
    driver.get(url)

    # ปิด popup ถ้ามี
    try:
        close_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div.dialog_guide .close"))
        )
        close_btn.click()
    except:
        pass
    
    try:
        close_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div.v-modal .login_close_btn"))
        )
        close_btn.click()
    except:
        pass

    time.sleep(3)  # รอให้โหลด content
    html = driver.page_source
    driver.quit()
    return html
