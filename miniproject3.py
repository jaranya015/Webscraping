# bot_app.py
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
    RETURN p.product_name AS name, p.price AS price, p.product_link AS link, p.image_link AS image,
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
                "image": record.get("image")
            })
    print(f"Loaded {len(products)} products from Neo4j.")
    return products

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
    """พยายามจับ category/material/theme/budget จากข้อความเดียว"""
    profile = {
        "material": None,
        "category": None,
        "theme": None,
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
    elif re.search(r"\b(engrave|สลัก|engraveable|engravable)\b", text):
        profile["theme"] = "Engravable"

    # budget — รองรับทั้ง "5000-10000", "up to 10000", "under 10000", "10000"
    range_match = re.search(r"(\d{1,3}(?:,\d{3})*)\s*-\s*(\d{1,3}(?:,\d{3})*)", text)
    if range_match:
        low = int(range_match.group(1).replace(',', ''))
        high = int(range_match.group(2).replace(',', ''))
        profile["budget_low"], profile["budget_high"] = low, high
    else:
        # up to / under / less than
        mo = re.search(r"(?:up to|under|less than)\s*(\d{1,3}(?:,\d{3})*)", text)
        if mo:
            high = int(mo.group(1).replace(',', ''))
            profile["budget_low"], profile["budget_high"] = 0, high
        else:
            # single number -> treat as max
            single = re.search(r"\b(\d{1,3}(?:,\d{3})*)\b", text)
            if single:
                val = int(single.group(1).replace(',', ''))
                # ถ้มีคำว่า 'budget' หรือ '฿' รอบๆ ให้ใช้เป็น high
                if 'budget' in text or '฿' in user_message:
                    profile["budget_low"], profile["budget_high"] = 0, val

    # clean freetext (ลบคำที่จับได้)
    keywords_to_remove = [v.lower() for k, v in profile.items() if k not in ["budget_low","budget_high","freetext"] and v]
    cleaned_text = text
    for keyword in keywords_to_remove:
        cleaned_text = cleaned_text.replace(keyword.lower(), "")
    profile["freetext"] = cleaned_text.strip()

    return profile

# ---------------- Neo4j question fetcher ----------------
def get_question(filter_name):
    with driver.session() as session:
        result = session.run("MATCH (q:Question {filter: $filter_name}) RETURN q.text AS text", filter_name=filter_name)
        record = result.single()
        return record["text"] if record else None

def generate_alternative_questions(original_question):
    if not original_question:
        original_question = "your preference"
    paraphrase_candidates = [
        f"Could you please tell me {original_question.lower()}?",
        f"May I know {original_question.lower()}?",
        f"What about {original_question.lower()}?",
        f"Can you specify {original_question.lower()}?"
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
                filtered_results.append(r)
        return filtered_results if filtered_results else results
    return results

# ---------------- User state storage ----------------
# โครงสร้าง: user_profiles[user_id] = {"profile": {...}, "last_question": None|"category"|"material"|"budget", "retry_count": int}
user_profiles = {}

# mapping last_question -> profile key(s) that answer it
LAST_Q_KEY = {
    "category": "category",
    "material": "material",
    "budget": ("budget_low", "budget_high")
}

def next_missing_field(profile):
    if not profile.get("category"):
        return "category"
    if not profile.get("material"):
        return "material"
    if profile.get("budget_low") is None or profile.get("budget_high") is None:
        return "budget"
    return None

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

    # ensure user state exists
    if user_id not in user_profiles:
        user_profiles[user_id] = {"profile": {"material": None, "category": None, "theme": None, "budget_low": None, "budget_high": None, "freetext": ""}, "last_question": None, "retry_count": 0}

    state = user_profiles[user_id]
    profile = state["profile"]

    # parse newly-provided info from message
    new_info = extract_user_profile(user_message)
    print("new_info:", new_info)

    # if we previously asked a specific question, prioritize trying to resolve it
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
            if new_info.get(key):
                profile[key] = new_info[key]
                answered = True

        if answered:
            # clear last_question and retry_count
            state["last_question"] = None
            state["retry_count"] = 0
            # also merge other new_info fields if present
            for k, v in new_info.items():
                if v and k not in ["freetext"]:
                    profile[k] = v
        else:
            # user didn't answer the question we asked
            state["retry_count"] += 1
            if state["retry_count"] < 2:
                # ask again with paraphrase
                base_q = get_question(asked) or f"Could you specify {asked}?"
                reply = generate_alternative_questions(base_q)
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
                return
            else:
                # give up asking this one after retries -> reset last_question and continue
                state["last_question"] = None
                state["retry_count"] = 0
                # continue to merge any new_info (even if doesn't answer asked Q)
                for k, v in new_info.items():
                    if v:
                        profile[k] = v

    else:
        # no pending question -> merge new info into profile
        for k, v in new_info.items():
            if v:
                profile[k] = v

    print("Merged profile:", profile)

    # decide next missing field
    next_field = next_missing_field(profile)
    if next_field:
        qtext = get_question(next_field) or f"Could you specify {next_field}?"
        paraphrase = generate_alternative_questions(qtext)
        # save asked question
        state["last_question"] = next_field
        state["retry_count"] = 0
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=paraphrase))
        return

    # all required info gathered -> recommend products
    try:
        recommendations = query_products(profile, products, index, embeddings)
    except Exception as e:
        print("Query products error:", e)
        recommendations = []

    if recommendations:
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
        line_bot_api.reply_message(event.reply_token, reply_message)
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text="Sorry, I couldn't find any matching jewelry. Try adjusting your preferences."
        ))

    # reset last_question / retry_count after recommendation (so next conversation is fresh)
    state["last_question"] = None
    state["retry_count"] = 0

@handler.add(FollowEvent)
def handle_follow(event):
    try:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text="สวัสดี! ฉันช่วยคุณหาเครื่องประดับที่ถูกใจได้นะ 😊\nลองพิมพ์ เช่น 'Looking for a gift set' หรือ 'สร้อยคอ เงิน'"))
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
