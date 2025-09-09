import os
import time
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from pythainlp.tokenize import word_tokenize as thai_word_tokenize

from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.chat_models import ChatOllama
from nltk.translate.bleu_score import sentence_bleu
from nltk.tokenize import word_tokenize
from pythainlp.tokenize import word_tokenize as thai_word_tokenize
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction


# -------------------------
# Configuration
# -------------------------
PDF_PATH = os.environ.get("RAG_PDF_PATH", "solarcell-basic-knowledge-SolarHub.pdf")
#CHROMA_DIR = os.environ.get("CHROMA_DIR", "./chroma_db")
CHROMA_DIR = os.environ.get("CHROMA_DIR", "faiss_index")
EMBED_MODEL_NAME = os.environ.get("EMBED_MODEL_NAME", "paraphrase-multilingual-MiniLM-L12-v2")
RETRIEVAL_K = int(os.environ.get("RETRIEVAL_K", "3"))

CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "8674ab6dc94c264cbd939631c07940c7")
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "cJMkFOjDwKWlJ0saZXXkhOGvdElQVClznOqYWVAYVveQflKbvRiXcbQYl0IWjwSQuYx9jvX+fy8cqtjDC2vY/NA/3wkCIYXWScTlDmNmhnA7hNEZourNou1ZeboRZtX3IGHBiJA/iGXx0Rr/tsoM4AdB04t89/1O/w1cDnyilFU=")

# -------------------------
# Global Chat History
# -------------------------
chat_history = []

# -------------------------
# Helper Functions
# -------------------------
def calculate_bleu(reference: str, candidate: str) -> float:
    # tokenize ด้วย pythainlp
    reference_tokens = [thai_word_tokenize(reference)]
    candidate_tokens = thai_word_tokenize(candidate)
    
    # ใช้ smoothing function method4
    smoothie = SmoothingFunction().method4
    
    score = sentence_bleu(reference_tokens, candidate_tokens, smoothing_function=smoothie)
    return score

def build_chat_llm():
    model_name = os.environ.get("OLLAMA_MODEL", "gemma3:4b")
    chat_llm = ChatOllama(model=model_name)
    print(f"[LLM] Using Ollama model: {model_name}")
    return chat_llm

def build_prompt(context: str, user_input: str) -> str:
    return f"""
Context (use only this information, do not add external knowledge):
{context}

Instructions:
- Answer strictly in Thai language
- Ensure correct spelling
- Keep the explanation short, clear, and easy to understand
- Do not provide any information outside of the Context

User question:
{user_input}

Answer:
""".strip()

# -------------------------
# Flask + LINE Bot
# -------------------------
app = Flask(__name__)
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

@app.route("/", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event: MessageEvent):
    start_time = time.time()  # ⏱️ start timer

    query = event.message.text
    
    # Retrieve docs with similarity scores
    results = app.config["VECTORSTORE"].similarity_search_with_score(query, k=RETRIEVAL_K)
    
    # Filter by threshold
    filtered_docs = [doc for doc, score in results if score >= 0.8]
    
    if not filtered_docs:
        context = "[No document found above similarity threshold 0.8]"
    else:
        context = "\n\n".join(d.page_content for d in filtered_docs)
    
    # Build prompt
    prompt = build_prompt(context, query)
    
    # Call LLM
    response = app.config["CHAT_LLM"].invoke(prompt)
    answer = getattr(response, "content", str(response)) or "[ERROR] Empty response"

    # Save to history
    chat_history.append(("User", query))
    chat_history.append(("Bot", answer))

    # Calculate elapsed time
    elapsed_time = time.time() - start_time
    print(f"[TIME] Response generated in {elapsed_time:.2f} seconds")

    ground_truth_answer = "แผงโซลาร์เซลล์ใช้พลังงานแสงอาทิตย์เพื่อผลิตไฟฟ้า"

    bleu_score = calculate_bleu(ground_truth_answer, answer)
    print(f"[BLEU] Score: {bleu_score:.4f}")
    # Optionally append time to user message
    answer_with_time = f"{answer}\n\n⏱️ Response time: {elapsed_time:.2f} seconds"
    answer_with_time += f"\n📏 BLEU score: {bleu_score:.4f}"
    # Truncate for LINE reply
    if len(answer_with_time) > 1900:
        answer_with_time = answer_with_time[:1900] + "\n… (truncated)"
    
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=answer_with_time))


# -------------------------
# Main Entry
# -------------------------
if __name__ == "__main__":
    import nltk
    nltk.download('punkt', quiet=True) 
    print("[BOOT] Loading Chroma index…")
    embedding = SentenceTransformerEmbeddings(model_name=EMBED_MODEL_NAME)
    
    vectorstore = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embedding
    )

    print("[BOOT] Initializing chat LLM…")
    chat_llm = build_chat_llm()

    app.config["VECTORSTORE"] = vectorstore
    app.config["CHAT_LLM"] = chat_llm

    port = int(os.environ.get("PORT", "5000"))
    print(f"[RUN] Flask listening on 0.0.0.0:{port}")
    app.run(port=port)
