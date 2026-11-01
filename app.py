import os
from flask import Flask, request, jsonify
import requests
from dotenv import load_dotenv

# Tải các biến môi trường từ file .env
load_dotenv()

app = Flask(__name__)

# Đọc API Keys từ file .env
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_ID = "nvidia/nemotron-3-ultra-550b-a55b:free"

@app.route('/slack-notify', methods=['POST'])
def handle_notification():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "no data"}), 400

        timestamp = data.get("timestamp", "N/A")
        raw_title = data.get("title", "")
        raw_text = data.get("text", "")

        if not raw_text:
            return jsonify({"status": "empty text"}), 200

        sender = raw_title
        channel = "Direct Message"
        
        if " in #" in raw_title:
            parts = raw_title.split(" in #")
            sender = parts[0]
            channel = parts[1]
        elif " in " in raw_title:
            parts = raw_title.split(" in ")
            sender = parts[0]
            channel = parts[1]

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com",
            "X-Title": "Slack Summarizer Bot"
        }

        prompt = (
            "Bạn là trợ lý tóm tắt tin nhắn làm việc. Hãy tóm tắt ngắn gọn, rõ ràng nội dung "
            "tin nhắn Slack sau đây trong 1-2 câu tiếng Việt (giữ nguyên deadline, con số hoặc link quan trọng nếu có):\n\n"
            f"{raw_text}"
        )

        payload = {
            "model": MODEL_ID,
            "messages": [
                {"role": "system", "content": "Bạn là một trợ lý tóm tắt văn bản chính xác và súc tích."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }

        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            res_data = response.json()
            summarized_text = res_data['choices'][0]['message']['content'].strip()
        else:
            print(f"OpenRouter API Error: {response.status_code} - {response.text}")
            summarized_text = raw_text

        discord_payload = {
            "embeds": [
                {
                    "title": f"💬 Thông báo từ #{channel}",
                    "color": 3447003,
                    "fields": [
                        {"name": "⏰ Thời gian", "value": timestamp, "inline": True},
                        {"name": "👤 Người gửi", "value": sender, "inline": True},
                        {"name": "📌 Channel", "value": f"#{channel}", "inline": True},
                        {"name": "📝 Nội dung (Tóm tắt)", "value": summarized_text, "inline": False}
                    ],
                    "footer": {
                        "text": "Powered by Nvidia Nemotron 3 Ultra (OpenRouter)"
                    }
                }
            ]
        }

        if DISCORD_WEBHOOK_URL:
            requests.post(DISCORD_WEBHOOK_URL, json=discord_payload)
        else:
            print("Cảnh báo: DISCORD_WEBHOOK_URL chưa được cấu hình!")

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"System Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
@app.route('/', methods=['GET'])
def home():
    return "Server Bot đang hoạt động bình thường!", 200
    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)