import requests

url = "https://www.konvy.com/list/lip-gloss/"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/114.0.0.0 Safari/537.36"
}

response = requests.get(url, headers=headers)

# ✅ บันทึกเป็นไฟล์ HTML
with open("lip_gloss.html", "w", encoding="utf-8") as f:
    f.write(response.text)

print("บันทึกไฟล์ lip_gloss.html เรียบร้อย")