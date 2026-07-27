import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# 환경 변수 로드
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

DEFAULT_RULES = [
    "PC 자리는 최대 2명 배치하고, 2번째 PC 담당자는 (이름) 형태 괄호로 표기한다.",
    "일요일 보고일 경우 '※ 예배 후 장비 정리 필수' 문구를 맨 아래에 작성한다."
]

def send_telegram_message(chat_id, text):
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        res.raise_for_status()
    except Exception as e:
        print(f"Telegram Send Error: {e}")

def call_gemini_api(prompt):
    if not GEMINI_API_KEY:
        return "⚠️ GEMINI_API_KEY가 설정되지 않았습니다."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        res_data = response.json()

        if response.status_code == 200:
            candidates = res_data.get("candidates", [])
            if candidates:
                text = candidates[0].get("content", {}).get("parts", [])[0].get("text", "")
                return text
            return "⚠️ 응답을 가져올 수 없습니다."
        else:
            error_msg = res_data.get("error", {}).get("message", "알 수 없는 오류")
            return f"❌ Gemini API 오류 ({response.status_code}): {error_msg}"
    except Exception as e:
        return f"❌ Gemini 호출 실패: {str(e)}"

# Vercel 포워딩 및 루트 접속 모두 지원하도록 멀티 라우트 설정
@app.route('/', methods=['GET', 'POST'])
@app.route('/api/index', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        return "BowPick Bot is running!", 200

    data = request.get_json(silent=True) or {}
    message = data.get('message', {})
    text = message.get('text', '')
    chat_id = message.get('chat', {}).get('id')

    if not chat_id or not text:
        return 'OK', 200

    try:
        # 규칙 직접 조회 시
        if "바우픽 규칙 보여줘" in text:
            rules_str = "\n".join([f"- {r}" for r in DEFAULT_RULES])
            reply = f"🤖 [현재 적용 중인 바우픽 기본 규칙]\n{rules_str}"
            send_telegram_message(chat_id, reply)

        # '바우픽'이라는 단어가 포함되어 있으면 Gemini가 유연하고 친절하게 대답
        elif "바우픽" in text:
            prompt = f"""
너는 참불 관리 및 스태프 안내를 돕는 AI 조교 '바우픽'이야.
사용자가 한 말에 맞춰 친절하고 센스 있게 대답해줘.

만약 사용자가 업무/스태프/명단 정리나 보고와 관련된 요청을 하면 아래 [기본 규칙]을 참고해서 작성해줘.
[기본 규칙]:
{DEFAULT_RULES}

사용자 메시지: {text}
"""
            reply_text = call_gemini_api(prompt)
            send_telegram_message(chat_id, reply_text)

    except Exception as e:
        print(f"Error processing webhook: {e}")
        send_telegram_message(chat_id, f"❌ 처리 중 오류 발생: {str(e)}")

    return 'OK', 200
