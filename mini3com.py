import os
import re
import random
import faiss
import numpy as np
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FollowEvent,
    TemplateSendMessage, CarouselTemplate, CarouselColumn, URITemplateAction
)
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer

# ---------------- Configuration ----------------
# แทนที่ค่าเหล่านี้ด้วยของจริง หรือตั้งเป็น environment variables
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "cJMkFOjDwKWlJ0saZXXkhOGvdElQVClznOqYWVAYVveQflKbvRiXcbQYl0IWjwSQuYx9jvX+fy8cqtjDC2vY/NA/3wkCIYXWScTlDmNmhnA7hNEZourNou1ZeboRZtX3IGHBiJA/iGXx0Rr/tsoM4AdB04t89/1O/w1cDnyilFU=")
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "8674ab6dc94c264cbd939631c07940c7")

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password123")

# ---------------- Initialization ----------------
app = Flask(__name__)
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# ไลท์เวอร์ชันโมเดล (ประหยัดหน่วยความจำ)
model = SentenceTransformer("all-MiniLM-L6-v2")

# ---------------- Helpers: Load products from Neo4j ----------------
def load_product_nodes():
    query = """
    MATCH (p:Product)
    OPTIONAL MATCH (p)-[:HAS_MATERIAL]->(m:Material)
    OPTIONAL MATCH (p)-[:IS_A_CATEGORY]->(c:Category)
    OPTIONAL MATCH (p)-[:HAS_THEME]->(t:Theme)
    OPTIONAL MATCH (p)-[:HAS_PROPERTY]->(pr:Property)
    WITH p, 
          collect(DISTINCT m.name) AS materials, 
          collect(DISTINCT c.name) AS categories, 
          collect(DISTINCT t.name) AS themes,
          collect(DISTINCT pr.name) AS properties
    // ดึง URL รูปภาพจาก p.image_url และ alias เป็น 'image'
    RETURN p.product_name AS name, p.price AS price, p.product_link AS link, p.image_url AS image,
            materials, categories, themes, properties
    """
    with driver.session() as session:
        results = session.run(query)
        products = []
        for record in results:
            specs_combined = (
                f"Material: {', '.join(record['materials'])}. "
                f"Category: {', '.join(record['categories'])}. "
                f"Theme: {', '.join(record['themes'])}. "
                f"Property: {', '.join(record['properties'])}."
            )
            products.append({
                "name": record["name"],
                "specs": specs_combined.strip(),
                "price": record["price"],
                "link": record["link"],
                "image": record["image"]  
            })
    print(f"Loaded {len(products)} products from Neo4j.")
    return products

# ---------------- Logging Function (NEW) ----------------
def log_search_event(user_id, profile, recommendations):
    """Logs the user's search profile and the top 5 recommended products to Neo4j."""
    query_text = profile_to_query(profile)
    # เก็บชื่อสินค้า 5 อันดับแรกที่ถูกแนะนำ
    recommended_products = [r['name'] for r in recommendations[:5]]
    
    # Log the Search Event (S:Search)
    search_query = """
    CREATE (s:Search {
        userId: $userId, 
        timestamp: datetime(), 
        queryText: $queryText, 
        material: $material,
        category: $category,
        theme: $theme,
        property: $property,
        isGift: $isGift,
        budgetLow: $budgetLow,
        budgetHigh: $budgetHigh
    })
    WITH s
    // สร้างความสัมพันธ์ไปยังสินค้าที่ถูกแนะนำ
    UNWIND $recommendedNames AS productName
    MATCH (p:Product {product_name: productName})
    CREATE (s)-[:RECOMMENDED_PRODUCT]->(p)
    """
    
    params = {
        "userId": user_id,
        "queryText": query_text,
        "material": profile.get('material'),
        "category": profile.get('category'),
        "theme": profile.get('theme'),
        "property": profile.get('property'),
        "isGift": profile.get('is_gift'),
        "budgetLow": profile.get('budget_low'),
        "budgetHigh": profile.get('budget_high'),
        "recommendedNames": recommended_products
    }
    
    try:
        with driver.session() as session:
            session.run(search_query, params)
        print(f"Logged search event for user {user_id}")
    except Exception as e:
        print(f"Error logging search event to Neo4j: {e}")

# ---------------- Embedding & FAISS ----------------
def embed_texts(texts):
    embeddings = model.encode(texts, normalize_embeddings=True)
    return np.array(embeddings).astype("float32")

def embed_products(products):
    texts = [f"{p['name']} {p['specs']} {p['price']}" for p in products]
    return embed_texts(texts)

def build_faiss_index(embeddings):
    if embeddings.size == 0:
        raise ValueError("Embeddings array is empty.")
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)
    print("FAISS index built.")
    return index

# ---------------- User profile extraction (improved) ----------------
def extract_user_profile(user_message):
    """พยายามจับ category/material/theme/property/budget/gift จากข้อความเดียว"""
    profile = {
        "material": None,
        "category": None,
        "theme": None,
        "property": None,   # ******* ADDED: Property field *******
        "is_gift": None,    # ******* ADDED: Gift purpose field (Boolean) *******
        "budget_low": None,
        "budget_high": None,
        "freetext": user_message
    }
    text = user_message.lower()

    # material (เพิ่ม synonyms)
    if re.search(r"\b(gold plated|14k gold|gold)\b", text) or "ทอง" in text:
        profile["material"] = "Gold Plated"
    elif re.search(r"\b(sterling silver|silver|เงิน)\b", text):
        profile["material"] = "Sterling Silver"
    elif re.search(r"\b(pearl|freshwater|มุก)\b", text):
        profile["material"] = "Pearl"

    # category (synonyms)
    if re.search(r"\b(necklace|สร้อยคอ|collier)\b", text):
        profile["category"] = "Necklace"
    elif re.search(r"\b(pendant|จี้|charm)\b", text):
        profile["category"] = "Pendant"
    elif re.search(r"\b(gift set|ชุดของขวัญ|giftset|set)\b", text):
        profile["category"] = "Gift Set"

    # theme
    if re.search(r"\b(heart|หัวใจ)\b", text):
        profile["theme"] = "Heart"
    elif re.search(r"\b(dragon|มังกร)\b", text):
        profile["theme"] = "Dragon"
    elif "disney" in text:
        profile["theme"] = "Disney"
    
    # ******* ADDED: Property extraction *******
    if re.search(r"\b(adjustable|ปรับได้)\b", text):
        profile["property"] = "Adjustable"
    elif re.search(r"\b(engraveable|สลัก|engravable)\b", text):
        profile["property"] = "Engravable"

    # ******* ADDED: Gift purpose extraction *******
    if re.search(r"\b(gift|ของขวัญ|for him|for her|fan|แฟน|birthday|วันเกิด)\b", text) and "not gift" not in text:
        profile["is_gift"] = True
    elif re.search(r"\b(self-treat|for myself|ซื้อให้ตัวเอง|ใช้เอง|not a gift|ไม่เป็นของขวัญ)\b", text) or re.search(r"\b(no)\b", text) and "gift" in text:
        profile["is_gift"] = False


    # budget — รองรับทั้ง "5000-10000", "up to 10000", "under 10000", "10000"
    range_match = re.search(r"(\d{1,3}(?:,\d{3})*)\s*[-\s]+\s*(\d{1,3}(?:,\d{3})*)", text)
    if range_match:
        low = int(range_match.group(1).replace(',', ''))
        high = int(range_match.group(2).replace(',', ''))
        profile["budget_low"], profile["budget_high"] = low, high
    else:
        # up to / under / less than / ไม่เกิน / ต่ำกว่า
        mo = re.search(r"(?:up to|under|less than|ไม่เกิน|ต่ำกว่า)\s*(\d{1,3}(?:,\d{3})*)", text)
        if mo:
            high = int(mo.group(1).replace(',', ''))
            profile["budget_low"], profile["budget_high"] = 0, high
        else:
            # single number -> treat as max
            single = re.search(r"\b(\d{1,3}(?:,\d{3})*)\b", text)
            if single:
                val = int(single.group(1).replace(',', ''))
                # ถ้มีคำว่า 'budget' หรือ '฿' รอบๆ ให้ใช้เป็น high
                if 'budget' in text or '฿' in user_message or 'บาท' in text:
                    profile["budget_low"], profile["budget_high"] = 0, val

    # clean freetext (ลบคำที่จับได้)
    # ******* UPDATED: Exclude 'is_gift' from keywords_to_remove *******
    keywords_to_remove = [v.lower() for k, v in profile.items() if k not in ["budget_low","budget_high","freetext", "is_gift"] and v]
    cleaned_text = text
    for keyword in keywords_to_remove:
        # ใช้ word boundary เพื่อป้องกันการลบคำย่อย เช่น 'gold' ใน 'gold plated'
        cleaned_text = re.sub(r'\b' + re.escape(keyword) + r'\b', '', cleaned_text).strip()
    
    # ลบคำที่เกี่ยวข้องกับ Budget และ Gift Purpose เพื่อให้ Freetext สะอาดขึ้น
    cleaned_text = re.sub(r"(?:up to|under|less than|ไม่เกิน|ต่ำกว่า|\d{1,3}(?:,\d{3})*|\b(budget|฿|บาท)\b|\b(gift|ของขวัญ|for him|for her|fan|แฟน|birthday|วันเกิด|self-treat|for myself|ซื้อให้ตัวเอง|ใช้เอง)\b)", "", cleaned_text)
    
    profile["freetext"] = re.sub(r'\s+', ' ', cleaned_text).strip() # clean multiple spaces

    return profile

# ---------------- Neo4j question fetcher ----------------
def get_question(filter_name):
    # This fetches the English question text from Neo4j
    with driver.session() as session:
        result = session.run("MATCH (q:Question {filter: $filter_name}) RETURN q.text AS text", filter_name=filter_name)
        record = result.single()
        return record["text"] if record else None

def generate_alternative_questions(original_question):
    """Generates a slightly different phrasing based on the original question (in English)."""
    if not original_question:
        original_question = "your preference"
    
    # Remove leading/trailing quotes and question marks for cleaner concatenation
    q_text = original_question.strip().strip('"').strip('?').lower() 
    
    paraphrase_candidates = [
        f"Just to clarify, {q_text}?",
        f"Could you please elaborate on {q_text}?",
        f"To help me narrow down the options, {q_text}?",
        f"May I know {q_text}?"
    ]
    return random.choice(paraphrase_candidates)

# ---------------- Query products via FAISS (keeps your current approach) ----------------
def profile_to_query(profile):
    query_text = ""
    if profile.get("material"):
        query_text += f" Material: {profile['material']}"
    if profile.get("category"):
        query_text += f" Category: {profile['category']}"
    if profile.get("theme"):
        query_text += f" Theme: {profile['theme']}"
    # ******* ADDED: Property query part *******
    if profile.get("property"):
        query_text += f" Property: {profile['property']}"
    # ******* ADDED: Gift context *******
    if profile.get("is_gift") == True:
        query_text += f" Perfect gift idea"
        
    if profile.get("budget_low") is not None and profile.get("budget_high") is not None:
        query_text += f" Price range: {profile['budget_low']}-{profile['budget_high']}"
    if profile.get("freetext"):
        query_text += f" Keywords: {profile['freetext']}"
    return query_text.strip()

def embed_query(profile):
    return embed_texts([profile_to_query(profile)])

def query_products(profile, products, index, embeddings, top_k=5):
    if not products or embeddings is None or embeddings.size == 0:
        return []
    query_vec = embed_query(profile)
    distances, indices = index.search(query_vec, top_k)
    results = [products[i] for i in indices[0]]
    
    # budget filtering (numerical)
    filtered_results = []
    if profile.get("budget_low") is not None and profile.get("budget_high") is not None:
        for r in results:
            price_str = (r.get('price') or '').replace('฿','').replace(',','').strip()
            try:
                price = float(price_str)
                if profile["budget_low"] <= price <= profile["budget_high"]:
                    filtered_results.append(r)
            except:
                filtered_results.append(r) # Keep if price parsing fails
        # Return filtered list if it has items, otherwise return the original embedding results
        return filtered_results if filtered_results else results
    return results

# ---------------- User state storage ----------------
# โครงสร้าง: user_profiles[user_id] = {"profile": {...}, "last_question": None|"category"|"material"|"budget"|..., "retry_count": int}
user_profiles = {}

# mapping last_question -> profile key(s) that answer it
LAST_Q_KEY = {
    "category": "category",
    "material": "material",
    "theme": "theme",         # ******* ADDED: Theme key *******
    "property": "property",   # ******* ADDED: Property key *******
    "gift_purpose": "is_gift", # ******* ADDED: Gift purpose key (Boolean) *******
    "budget": ("budget_low", "budget_high")
}

def next_missing_field(profile):
    """Determines the next preference field to ask the user about."""
    if not profile.get("category"):
        return "category"
    if not profile.get("material"):
        return "material"
    if not profile.get("theme"):
        return "theme"
    if not profile.get("property"):
        return "property"
    if profile.get("budget_low") is None or profile.get("budget_high") is None:
        return "budget"
    if profile.get("is_gift") is None:
        return "gift_purpose"
    return None

def reset_user_state(user_id):
    """Initializes or resets the user's state/profile."""
    user_profiles[user_id] = {
        "profile": {
            "material": None, "category": None, "theme": None, 
            "property": None, "is_gift": None, "budget_low": None, 
            "budget_high": None, "freetext": ""
        }, 
        "last_question": None, 
        "retry_count": 0
    }

# ---------------- LINE Webhook & Handlers ----------------
@app.route("/", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    print("\n--- NEW WEBHOOK REQUEST ---")
    print(f"Signature: {signature}")
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature - check channel secret")
        return "Invalid signature", 400
    except Exception as e:
        print("Webhook handler error:", e)
        return "Internal Server Error", 500
    return "OK", 200

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text or ""
    print(f"[{user_id}] message: {user_message}")

    # ensure user state exists and initialize new fields
    if user_id not in user_profiles:
        reset_user_state(user_id)

    state = user_profiles[user_id]
    profile = state["profile"]
    
    # ******* NEW: Reset Command Logic *******
    if user_message.strip().lower() in ["reset", "start over", "เริ่มใหม่", "เริ่มต้นใหม่"]:
        reset_user_state(user_id)
        # Force the bot to ask the first question immediately
        next_field = next_missing_field(user_profiles[user_id]["profile"])
        if next_field:
            qtext = get_question(next_field) or f"Could you specify {next_field}?"
            paraphrase = generate_alternative_questions(qtext)
            user_profiles[user_id]["last_question"] = next_field
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"I've reset our conversation. Let's start fresh!\n{paraphrase}"))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="Conversation reset. Please tell me what you're looking for."))
        return

    # parse newly-provided info from message
    new_info = extract_user_profile(user_message)
    print("new_info:", new_info)

    # State machine logic: Check for pending question first
    if state["last_question"]:
        asked = state["last_question"]
        key = LAST_Q_KEY.get(asked)
        answered = False

        # budget is special: check budget_low/high in new_info
        if asked == "budget":
            if new_info.get("budget_low") is not None and new_info.get("budget_high") is not None:
                profile["budget_low"] = new_info["budget_low"]
                profile["budget_high"] = new_info["budget_high"]
                answered = True
            else:
                # check if freetext can be parsed as budget (single number)
                mo = re.search(r"\b(\d{1,3}(?:,\d{3})*)\b", user_message)
                if mo:
                    val = int(mo.group(1).replace(',', ''))
                    # only set budget if the number seems intentional
                    if val > 100: 
                        profile["budget_low"], profile["budget_high"] = 0, val
                        answered = True
                        
        # ******* ADDED: gift_purpose is special: check boolean value *******
        elif asked == "gift_purpose":
             if new_info.get("is_gift") is not None:
                profile["is_gift"] = new_info["is_gift"]
                answered = True
                
        else:
            # check for category, material, theme, property
            if new_info.get(key):
                profile[key] = new_info[key]
                answered = True

        if answered:
            # clear last_question and retry_count
            state["last_question"] = None
            state["retry_count"] = 0
            # also merge other new_info fields if present
            for k, v in new_info.items():
                # Avoid overriding budget/gift just set, and skip freetext
                if v and k not in ["freetext", "budget_low", "budget_high", "is_gift"]: 
                    profile[k] = v
        else:
            # User didn't answer the specific question we asked
            state["retry_count"] += 1
            if state["retry_count"] < 2:
                # ask again with paraphrase
                base_q = get_question(asked) or f"Could you specify {asked}?"
                reply = generate_alternative_questions(base_q)
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
                return
            else:
                # Give up after retries, reset state, and continue to product search
                state["last_question"] = None
                state["retry_count"] = 0
                for k, v in new_info.items():
                    if v:
                        profile[k] = v

    else:
        # No pending question -> merge all new info into profile
        for k, v in new_info.items():
            if v:
                profile[k] = v

    print("Merged profile:", profile)

    # Decide next missing field
    next_field = next_missing_field(profile)
    if next_field:
        # Get the English question text from Neo4j
        qtext = get_question(next_field) or f"Could you specify {next_field}?"
        paraphrase = generate_alternative_questions(qtext)
        
        # save asked question
        state["last_question"] = next_field
        state["retry_count"] = 0
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=paraphrase))
        return

    # All required info gathered -> recommend products
    try:
        recommendations = query_products(profile, products, index, embeddings)
    except Exception as e:
        print("Query products error:", e)
        recommendations = []
        
    # ******* NEW: Log the search event (บันทึกสถิติการค้นหา) *******
    if recommendations:
        log_search_event(user_id, profile, recommendations) # <- บันทึกสถิติการค้นหา

        columns = []
        for r in recommendations[:5]:
            title = (r.get("name") or "Item")[:40]
            text = f"Price: {r.get('price') or '-'}"
            columns.append(
                CarouselColumn(
                    thumbnail_image_url=r.get("image") or "https://example.com/default.jpg", 
                    title=title,
                    text=text[:60],
                    actions=[URITemplateAction(label="View Product", uri=r.get('link') or "#")]
                )
            )

        reply_message = TemplateSendMessage(
            alt_text="Here are some jewelry recommendations",
            template=CarouselTemplate(columns=columns)
        )
        # Add a friendly intro message before the carousel
        line_bot_api.reply_message(event.reply_token, [
            TextSendMessage(text="Thank you! Based on your preferences, here are the best recommendations:"),
            reply_message
        ])
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text="Sorry, I couldn't find any matching jewelry. Try adjusting your preferences."
        ))

    # reset state after recommendation
    state["last_question"] = None
    state["retry_count"] = 0

@handler.add(FollowEvent)
def handle_follow(event):
    try:
        # ******* UPDATED: Follow message to be more consistent with English Q&A flow *******
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text="Hello! I can help you find the perfect jewelry. 😊\nTry typing, for example: 'Looking for a gold plated heart necklace under 5000.' or 'อยากได้ชุดของขวัญเป็นมุก'. You can type 'Start over' anytime to reset the conversation."
        ))
    except Exception as e:
        print("LINE API ERROR (follow):", e)

# ---------------- System init: load products + build FAISS ----------------
print("Loading product data and building FAISS index...")
products = load_product_nodes()
embeddings = embed_products(products) if products else np.array([])
index = build_faiss_index(embeddings) if embeddings.size else None
print("Bot ready to receive messages.")

if __name__ == "__main__":
    app.run(port=5000, debug=True)
