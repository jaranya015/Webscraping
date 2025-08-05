import time
from bs4 import BeautifulSoup
import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def search_advice_branch(location_name: str) -> list:
    result = []
    # Auto-install compatible ChromeDriver
    chromedriver_autoinstaller.install()

    # Setup Chrome options (uncomment headless if you want no browser UI)
    chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument('--headless')
    # chrome_options.add_argument('--no-sandbox')
    # chrome_options.add_argument('--disable-dev-shm-usage')

    # Initialize the WebDriver
    driver = webdriver.Chrome(options=chrome_options)

    try:
        # Step 1: Go to Advice website
        driver.get("https://www.advice.co.th/wheretobuy?srsltid=AfmBOoqgONhKTiIr9J-wCinaW_d9OJhKh3rVBiPWNJO087cjuv_nsp9t")

        # Step 2: Wait for page to load
        time.sleep(5)  # Adjust or replace with WebDriverWait if needed

        # Optional: save the page HTML to a local file
        with open("advice_page01.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        # Step 3: Click on "สาขาใกล้ฉัน"
        # Locate the input box by ID and type text
        search_input = driver.find_element(By.ID, "shop_find")
        search_input.clear()
        search_input.send_keys(location_name)  # Type the location name in Thai

        # Optional: press Enter (if needed)
        search_input.submit()

        time.sleep(3)

        # Optional: save the page HTML to a local file
        with open("advice_page02.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)

        
        # Step 4: Scrape store names
        # Get HTML directly from Selenium (no need to read file)
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        # Extract branch names and links
        branches = soup.select(".list-items-branch h3 > a")

        for idx, branch in enumerate(branches, 1):
            name = branch.text.strip()
            link = branch["href"]
            print(f"{idx}. {name} --> {link}") 
            result.append(f"{idx}. {name} --> {link}")

    finally:
        driver.quit()
    
    return result