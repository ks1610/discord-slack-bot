import os
import re
import requests
import time
from collections import OrderedDict
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Cache lưu 20 request gần nhất để chống trùng lặp (Deduplication)
PROCESSED_REQUESTS = OrderedDict()
DEDUP_WINDOW_SECONDS = 10

# Danh sách Model ID Free CHUẨN XÁC trên OpenRouter
FREE_MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "google/gemma-2-9b-it:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "qwen/qwen-2.5-coder-32b-instruct:free",
    "mistralai/mistral-7b-instruct:free"
]

SYSTEM_PROMPT = """
You are an intelligent workplace notification analyst for a PageFly Customer Support team member.
Your responsibility is to analyze internal Slack messages and produce concise, structured English summaries.

CORE OBJECTIVES:
1. Identify the main announcement or update.
2. Extract important information, including dates, deadlines, numbers, pricing, promotional codes, policies, names, and URLs.
3. Explain the impact on Frontline Support.
4. Identify required actions and responsible persons.
5. Highlight restrictions, exceptions, and warnings.

PRIORITIES:
- HIGH: Urgent actions, approaching deadlines, important policy changes, or critical CS instructions.
- MEDIUM: Relevant team updates, new features, operational changes, or upcoming campaigns.
- LOW: General announcements and informational updates.

IMPORTANT RULES:
- Write entirely in clear, professional English.
- Preserve exact dates, numbers, names, URLs, promotional codes, and policy details.
- Remove greetings, repetitive explanations, and unnecessary formalities.

OUTPUT FORMAT:
Priority: HIGH / MEDIUM / LOW

📌 MAIN UPDATE
Briefly explain what is happening.

🔑 KEY INFORMATION
- Important dates, numbers, policies, codes, links, etc.

💬 CS IMPACT
- What Frontline Support should know.

⚡ ACTION REQUIRED
- Required tasks, responsible persons, and deadlines.

⚠️ IMPORTANT NOTES
- Restrictions, exceptions, and things to avoid.

Return only the summary.
"""

def build_user_prompt(raw_text):
    return f"Analyze the following internal notification:\n\n{raw_text}"

def parse_notification_title(raw_title):
    sender = raw_title
    channel = "Messenger Chat"
    if " in #" in raw_title:
        parts = raw_title.split(" in #", 1)
        sender, channel = parts[0].strip(), parts[1].strip()
    elif " in " in raw_title:
        parts = raw_title.split(" in ", 1)
        sender, channel = parts[0].strip(), parts[1].strip()
    return sender, channel

def summarize_notification(raw_text):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com",
        "X-Title": "PageFly Notification Summarizer Bot"
    }

    last_error = None

    for model_name in FREE_MODELS:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(raw_text)}
            ],
            "temperature": 0.2,
            "max_tokens": 1200
        }

        try:
            print(f"Attempting summarization with model: {model_name}")
            response = requests.post(
                OPENROUTER_URL,
                headers=headers,
                json=payload,
                timeout=25
            )

            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()
                if content:
                    return content

            print(f"Model {model_name} failed with status {response.status_code}: {response.text}")
            time.sleep(1)

        except Exception as err:
            last_error = err
            print(f"Error calling {model_name}: {err}")
            continue

    raise last_error or RuntimeError("All fallback models failed")

def get_priority(summary):
    match = re.search(r"Priority:\s*(HIGH|MEDIUM|LOW)", summary, re.IGNORECASE)
    return match.group(1).upper() if match else "MEDIUM"

def get_priority_color(priority):
    colors = {"HIGH": 0xE74C3C, "MEDIUM": 0xF39C12, "LOW": 0x2ECC71}
    return colors.get(priority, 0x3498DB)

def split_summary(summary):
    pattern = r"(📌 MAIN UPDATE|🔑 KEY INFORMATION|💬 CS IMPACT|⚡ ACTION REQUIRED|⚠️ IMPORTANT NOTES)"
    parts = re.split(pattern, summary)
    sections = {}
    for i in range(1, len(parts), 2):
        sections[parts[i].strip()] = parts[i + 1].strip()
    return sections

def truncate_text(text, limit=1024):
    return text if len(text) <= limit else text[:limit - 3] + "..."

def build_discord_embed(timestamp, sender, channel, summary):
    priority = get_priority(summary)
    sections = split_summary(summary)
    priority_icons = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}

    fields = [
        {"name": "👤 Sender", "value": truncate_text(sender), "inline": True},
        {"name": "📂 Channel", "value": truncate_text(channel), "inline": True},
        {"name": "⏰ Time", "value": truncate_text(timestamp), "inline": True}
    ]

    section_names = ["📌 MAIN UPDATE", "🔑 KEY INFORMATION", "💬 CS IMPACT", "⚡ ACTION REQUIRED", "⚠️ IMPORTANT NOTES"]
    for name in section_names:
        content = sections.get(name)
        if content:
            fields.append({"name": name, "value": truncate_text(content), "inline": False})

    return {
        "title": "📬 PAGEFLY NOTIFICATION SUMMARY",
        "description": f"{priority_icons[priority]} **{priority} PRIORITY**",
        "color": get_priority_color(priority),
        "fields": fields,
        "footer": {"text": "PageFly Notification Summarizer | Powered by OpenRouter"}
    }

def send_to_discord(embed):
    if not DISCORD_WEBHOOK_URL:
        raise ValueError("DISCORD_WEBHOOK_URL is not configured")

    payload = {"username": "PageFly Notification Bot", "embeds": [embed]}
    response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
    response.raise_for_status()
    return response.status_code

@app.route("/", methods=["GET"])
def home():
    return "PageFly Notification Summarizer is Running!", 200

@app.route("/slack-notify", methods=["POST"])
def handle_notification():
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"status": "no data"}), 400

        timestamp = data.get("timestamp", "N/A")
        raw_title = data.get("title", "Notification")
        raw_text = data.get("text", "")

        # 1. Chống trùng lặp (Deduplication Check)
        request_key = f"{raw_title}_{raw_text}"
        now = time.time()
        
        # Dọn dẹp cache cũ
        while PROCESSED_REQUESTS and next(iter(PROCESSED_REQUESTS.values())) < now - DEDUP_WINDOW_SECONDS:
            PROCESSED_REQUESTS.popitem(last=False)

        if request_key in PROCESSED_REQUESTS:
            print("Duplicate request detected within 10s. Ignored.")
            return jsonify({"status": "ignored duplicate"}), 200

        PROCESSED_REQUESTS[request_key] = now

        # 2. Lọc bỏ thông báo rác
        ignored_titles = ["chat heads active", "messenger", "system"]
        ignored_texts = ["start a conversation", "active now", "bong bóng chat đang hoạt động"]

        if raw_title.lower().strip() in ignored_titles or raw_text.lower().strip() in ignored_texts:
            return jsonify({"status": "ignored system notification"}), 200

        if not raw_text.strip() or len(raw_text.strip()) < 5:
            return jsonify({"status": "text too short"}), 200

        sender, channel = parse_notification_title(raw_title)

        try:
            summarized_text = summarize_notification(raw_text)
        except Exception as ai_error:
            print(f"OpenRouter Error: {ai_error}")
            summarized_text = f"Priority: MEDIUM\n\n📌 MAIN UPDATE\nAI Summarization failed.\n\n🔑 KEY INFORMATION\n{raw_text}"

        embed = build_discord_embed(timestamp, sender, channel, summarized_text)
        discord_status = send_to_discord(embed)

        return jsonify({"status": "success", "priority": get_priority(summarized_text)}), 200

    except Exception as e:
        print(f"System Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)