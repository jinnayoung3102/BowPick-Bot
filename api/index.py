import os
import requests
import google.generativeai as genai
from flask import Flask, request, jsonify

app = Flask(__name__)

# 환경 변수 로드
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# Gemini API 설정 및 이용 가능한 모델 자동 탐색
model = None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # 지원되는 모델 목록 중 generateContent가 가능한 첫 번째 모델을 자동으로 선점
    try:
        available_models = [
            m.name for m in genai.list_models() 
            if 'generateContent' in m.supported_generation_methods
        ]
        if available_models:
            # 1.5-flash 계열 우선, 없으면 첫 번째 호환 모델 사용
            target_model = next((m for m in available_models if '1.5-flash' in m), available_models[0])
            model = genai.GenerativeModel(target_model)
            print(f"Loaded Gemini Model: {target_model}")
        else:
            model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        print(f"Model Init Error: {e}")
        model = genai.GenerativeModel('gemini-1.5-flash')

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
        if "바우픽 규칙 보여줘" in text:
            rules_str = "\n".join([f"- {r}" for r in DEFAULT_RULES])
            reply = f"🤖 [현재 적용 중인 바우픽 기본 규칙]\n{rules_str}"
            send_telegram_message(chat_id, reply)

        elif "바우픽" in text:
            if not model:
                send_telegram_message(chat_id, "⚠️ GEMINI_API_KEY가 설정되지 않았습니다.")
                return 'OK', 200

            prompt = f"""
너는 참불 관리 AI 조교야. 
아래 규칙을 지켜서 메시지를 정리해줘.
[규칙]: {DEFAULT_RULES}
[입력 데이터]: {text}
"""
            response = model.generate_content(prompt)
            if response and response.text:
                send_telegram_message(chat_id, response.text)
            else:
                send_telegram_message(chat_id, "⚠️ 응답 생성에 실패했습니다.")

    except Exception as e:
        print(f"Error processing webhook: {e}")
        send_telegram_message(chat_id, f"❌ 처리 중 오류 발생: {str(e)}")

    return 'OK', 200
