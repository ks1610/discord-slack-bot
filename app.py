import os
from flask import Flask, request, jsonify
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_ID = "nvidia/nemotron-3-ultra-550b-a55b:free"

@app.route('/', methods=['GET'])
def home():
    return "Notification Summarizer Bot is Running!", 200

@app.route('/slack-notify', methods=['POST'])
def handle_notification():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "no data"}), 400

        timestamp = data.get("timestamp", "N/A")
        raw_title = data.get("title", "Thông báo")
        raw_text = data.get("text", "")

        # Chỉ ngắt nếu hoàn toàn không có nội dung text
        if not raw_text:
            print("Nhận request nhưng raw_text bị rỗng")
            return jsonify({"status": "empty text"}), 200

        print(f"Đã nhận tin nhắn thành công: Title='{raw_title}' - Text='{raw_text}'")

        # Phân tích Title (Hỗ trợ Slack, Messenger)
        sender = raw_title
        channel = "Messenger Chat"
        
        if " in #" in raw_title:
            parts = raw_title.split(" in #")
            sender = parts[0]
            channel = parts[1]
        elif " in " in raw_title:
            parts = raw_title.split(" in ")
            sender = parts[0]
            channel = parts[1]

        # 1. Gọi OpenRouter API tóm tắt
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com",
            "X-Title": "Notification Summarizer Bot"
        }

        prompt = (
            "Bạn là trợ lý tóm tắt tin nhắn. Hãy tóm tắt ngắn gọn, rõ ràng nội dung "
            "tin nhắn sau đây trong 1-2 câu tiếng Việt (giữ nguyên deadline, con số hoặc thông tin quan trọng nếu có):\n\n"
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
            print(f"Lỗi OpenRouter API: {response.status_code} - {response.text}")
            summarized_text = raw_text

        # 2. Định dạng Embed và gửi sang Discord Webhook
        discord_payload = {
            "username": "Message Summarizer",
            "embeds": [
                {
                    "title": f"💬 Thông báo mới ({channel})",
                    "color": 3447003,
                    "fields": [
                        {"name": "⏰ Thời gian", "value": timestamp, "inline": True},
                        {"name": "👤 Người gửi / Nhóm", "value": sender, "inline": True},
                        {"name": "📝 Nội dung (Tóm tắt)", "value": summarized_text, "inline": False}
                    ],
                    "footer": {
                        "text": "Powered by Nvidia Nemotron 3 Ultra (OpenRouter)"
                    }
                }
            ]
        }

        if DISCORD_WEBHOOK_URL:
            res_discord = requests.post(DISCORD_WEBHOOK_URL, json=discord_payload)
            print(f"Kết quả gửi Discord: {res_discord.status_code}")
        else:
            print("Lỗi: Chưa cấu hình DISCORD_WEBHOOK_URL")

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"System Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)