from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import time
import pandas as pd  # ใช้ pandas สำหรับการสร้าง CSV

# หากคุณใช้ ChromeDriver ที่ติดตั้งไว้ใน PATH แล้ว ไม่ต้องระบุ path
service = Service()  # หรือใส่ path ของ ChromeDriver ตรงนี้เช่น Service('C:/path/to/chromedriver.exe')

# ตั้งค่า browser
options = webdriver.ChromeOptions()
# options.add_argument("--headless")  # รันแบบไม่เปิดหน้าต่าง browser

# เริ่มต้น browser
driver = webdriver.Chrome(service=service, options=options)

# เปิดเว็บเพจ
driver.get("https://www.pandora.co.th/necklaces.html")

# รอให้เว็บโหลดเสร็จ (ปรับตามความเร็วเน็ต)
time.sleep(5)

# ดึง source หลังโหลด
soup = BeautifulSoup(driver.page_source, 'html.parser')

# หาทุกสินค้าที่อยู่ใน <a> tag ตาม class ที่คุณเจอ
product_links = soup.find_all('a', class_='product do-not-prerender photo product-item-photo block mx-auto')

# สร้างรายการเก็บข้อมูล
data = []

# แสดงผลและเก็บข้อมูล
for link in product_links:
    href = link.get('href')
    title = link.get('title')
    
    # ดึงราคา
    price_tag = link.find_parent('li').find('span', class_='price')  # หาราคาโดยใช้ parent <li> ของ <a> tag
    price = price_tag.text.strip() if price_tag else "ไม่พบราคา"

    # ดึง URL ของภาพสินค้า
    img_tag = link.find_parent('li').find('img', class_='object-contain product-image-photo')  # หาภาพสินค้า
    img_url = img_tag['src'] if img_tag else "ไม่พบภาพ"

    # เก็บข้อมูลใน list
    data.append({"ชื่อสินค้า": title, "ลิงก์": href, "ราคา": price, "URL ของภาพ": img_url})

# สร้าง DataFrame จากข้อมูลที่เก็บ
df = pd.DataFrame(data)

# บันทึกข้อมูลลงในไฟล์ CSV
df.to_csv("pandora_necklaces.csv", index=False, encoding="utf-8-sig")

# ปิด browser
driver.quit()

print("✅ ข้อมูลถูกบันทึกลงใน pandora_necklaces.csv แล้ว")
