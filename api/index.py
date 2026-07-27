import json
import os
import google.generativeai as genai
from flask import Flask, request

app = Flask(__name__)

# Gemini 설정 (Vercel Environment Variables에 GEMINI_API_KEY 등록 필요)
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

# 임시/기본 상시 규칙 (코드 내 보관)
DEFAULT_RULES = [
    "PC 자리는 최대 2명 배치하고, 2번째 PC 담당자는 (이름) 형태 괄호로 표기한다.",
    "일요일 보고일 경우 '※ 예배 후 장비 정리 필수' 문구를 맨 아래에 작성한다."
]

@app.route('/api/index', methods=['POST'])
def webhook():
    data = request.get_json()
    
    # 텔레그램 메시지 텍스트 추출
    message = data.get('message', {})
    text = message.get('text', '')
    chat_id = message.get('chat', {}).get('id')
    
    if "바우픽 규칙 보여줘" in text:
        # 규칙 목록 출력
        rules_str = "\n".join([f"- {r}" for r in DEFAULT_RULES])
        reply = f"🤖 **[현재 적용 중인 바우픽 기본 규칙]**\n{rules_str}"
        send_telegram_message(chat_id, reply)
        
    elif "바우픽" in text:
        # 참불 보고서 생성 요청 등 처리
        prompt = f"""
        너는 참불 관리 AI 조교야. 
        아래 규칙을 지켜서 메시지를 정리해줘.
        [규칙]: {DEFAULT_RULES}
        [입력 데이터]: {text}
        """
        response = model.generate_content(prompt)
        send_telegram_message(chat_id, response.text)
        
    return 'OK', 200

def send_telegram_message(chat_id, text):
    # 텔레그램 sendMessage API 호출 로직
    pass
