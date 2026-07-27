import os
import traceback
import requests
from openai import OpenAI
from flask import Flask, request
from api.sheets import (
    test_sheet_connection,
    save_wednesday_selection,
)

try:
    from api.sheets import (
        test_sheet_connection,
        save_wednesday_selection,
    )
    from api.telegram import (
        send_wednesday_recruitment,
        answer_callback_query,
    )
except ImportError:
    from sheets import (
        test_sheet_connection,
        save_wednesday_selection,
    )
    from telegram import (
        send_wednesday_recruitment,
        answer_callback_query,
    )
    from sheets import (
    test_sheet_connection,
    save_wednesday_selection,
    )

app = Flask(__name__)

# 환경 변수 로드
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# ChatGPT 유료 기능을 사용할 수 있는 관리자 텔레그램 ID
ADMIN_TELEGRAM_ID = "1514822797"

client = OpenAI(api_key=OPENAI_API_KEY)

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


def call_chatgpt(prompt):
    if not OPENAI_API_KEY:
        return "⚠️ OPENAI_API_KEY가 설정되지 않았습니다."

    try:
        response = client.responses.create(
            model="gpt-5-mini",
            input=prompt
        )

        return response.output_text.strip()

    except Exception as e:
        return f"❌ ChatGPT API 오류: {str(e)}"


# Vercel 포워딩 및 루트 접속 모두 지원하도록 멀티 라우트 설정
@app.route('/', methods=['GET', 'POST'])
@app.route('/api/index', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        return "BowPick Bot is running!", 200

    data = request.get_json(silent=True) or {}

    try:
        # ==================================================
        # 인라인 버튼 클릭 처리
        # 단체방에 새 메시지는 남기지 않고,
        # 버튼을 누른 사람 화면에만 잠깐 안내를 표시한다.
        # ==================================================
        callback_query = data.get("callback_query")

        if callback_query:
            callback_query_id = callback_query.get("id")
            callback_data = callback_query.get("data", "")

            # callback_data 형식:
            # apply|WED-TEST-001|noon
            # apply|WED-TEST-001|evening
            # apply|WED-TEST-001|absent
            parts = callback_data.split("|")

            if len(parts) != 3 or parts[0] != "apply":
                answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="⚠️ 올바르지 않은 버튼입니다.",
                    show_alert=False,
                )
                return 'OK', 200

                        recruitment_id = parts[1]
            selection = parts[2]

            callback_user = callback_query.get("from", {})

            callback_user_id = str(
                callback_user.get("id", "")
            )

            first_name = str(
                callback_user.get("first_name", "")
            ).strip()

            last_name = str(
                callback_user.get("last_name", "")
            ).strip()

            fallback_name = (
                f"{last_name}{first_name}".strip()
                or first_name
                or f"사용자-{callback_user_id}"
            )

            save_result = save_wednesday_selection(
                recruitment_id=recruitment_id,
                service_date="테스트",
                telegram_id=callback_user_id,
                fallback_name=fallback_name,
                selection=selection,
            )

            saved_name = save_result.get(
                "name",
                fallback_name,
            )

            if selection == "noon":
                notice_text = (
                    f"☀️ {saved_name}님, "
                    "정오예배 참석으로 저장되었습니다."
                )

            elif selection == "evening":
                notice_text = (
                    f"🌙 {saved_name}님, "
                    "저녁예배 참석으로 저장되었습니다."
                )

            elif selection == "absent":
                notice_text = (
                    f"❌ {saved_name}님, "
                    "둘 다 불참으로 저장되었습니다."
                )

            elif selection == "attend":
                notice_text = (
                    f"⭕ {saved_name}님, "
                    "참석으로 저장되었습니다."
                )

            else:
                notice_text = "⚠️ 알 수 없는 선택입니다."

            print(
                "Callback received:",
                {
                    "recruitment_id": recruitment_id,
                    "selection": selection,
                    "user_id": callback_query.get(
                        "from", {}
                    ).get("id"),
                }
            )

            answer_callback_query(
                callback_query_id=callback_query_id,
                text=notice_text,
                show_alert=False,
            )

            return 'OK', 200

        # ==================================================
        # 일반 텔레그램 메시지 처리
        # ==================================================
        message = data.get('message', {})

        text = message.get('text', '')
        chat_id = message.get('chat', {}).get('id')

        # 메시지를 보낸 사람의 고유 텔레그램 ID
        user_id = str(
            message.get('from', {}).get('id', '')
        )

        if not chat_id or not text:
            return 'OK', 200

        # 구글 스프레드시트 연결 테스트
        # OpenAI를 호출하지 않으므로 비용이 발생하지 않음
        if text.strip() == "바우픽 테스트":
            result = test_sheet_connection()

            if result.get("success"):
                sheet_names = "\n".join(
                    [
                        f"- {name}"
                        for name in result.get("sheets", [])
                    ]
                )

                reply = (
                    "✅ 구글 시트 연결 성공!\n\n"
                    f"{sheet_names}"
                )
            else:
                reply = (
                    "❌ 구글 시트 연결 실패\n\n"
                    f"{result.get('message', '알 수 없는 오류')}"
                )

            send_telegram_message(chat_id, reply)

        # 수요예배 모집글 및 인라인 버튼 출력 테스트
        # OpenAI를 호출하지 않으므로 비용이 발생하지 않음
        elif text.strip() == "바우픽 수요 모집 테스트":
            if user_id != ADMIN_TELEGRAM_ID:
                send_telegram_message(
                    chat_id,
                    "⛔ 관리자 전용 테스트입니다."
                )
                return 'OK', 200

            noon_names = [
                "김지은",
                "김민창",
                "김영식",
                "정은혜",
                "박주영",
                "진나영"
            ]

            evening_names = [
                "강예린",
                "김소연",
                "한예준",
                "서태희",
                "김유진",
                "노유림",
                "이경환"
            ]

            send_wednesday_recruitment(
                chat_id=chat_id,
                recruitment_id="WED-TEST-001",
                service_date="수요예배 테스트",
                noon_names=noon_names,
                evening_names=evening_names,
                deadline_text="테스트 종료 전까지"
            )

        # 규칙 조회
        # OpenAI를 호출하지 않으므로 비용이 발생하지 않음
        elif "바우픽 규칙 보여줘" in text:
            rules_str = "\n".join(
                [f"- {rule}" for rule in DEFAULT_RULES]
            )

            reply = (
                "🤖 [현재 적용 중인 바우픽 기본 규칙]\n"
                f"{rules_str}"
            )

            send_telegram_message(chat_id, reply)

        # '바우픽'이 포함된 일반 요청은 관리자만 ChatGPT 사용 가능
        elif "바우픽" in text:
            if user_id != ADMIN_TELEGRAM_ID:
                send_telegram_message(
                    chat_id,
                    "⛔ 관리자 전용 기능입니다.\n"
                    "OpenAI 기능은 관리자만 사용할 수 있습니다."
                )
                return 'OK', 200

            prompt = f"""
너는 참불 관리 및 스태프 안내를 돕는 AI 조교 '바우픽'이야.
사용자가 한 말에 맞춰 친절하고 센스 있게 대답해줘.

만약 사용자가 업무/스태프/명단 정리나 보고, 규칙 수정 등에 대한 대화를 시도하면 아래 [기본 규칙]을 참고해.

[기본 규칙]
{chr(10).join(DEFAULT_RULES)}

사용자 메시지:
{text}
"""

            reply_text = call_chatgpt(prompt)
            send_telegram_message(chat_id, reply_text)

    except Exception as e:
        traceback.print_exc()

        error_name = type(e).__name__
        error_message = (
            str(e).strip()
            or "오류 상세 내용이 없습니다."
        )

        # callback 처리 중 오류라면 단체방에 오류 메시지를 쌓지 않음
        callback_query = data.get("callback_query")

        if callback_query:
            callback_query_id = callback_query.get("id")

            try:
                answer_callback_query(
                    callback_query_id=callback_query_id,
                    text=f"❌ 처리 실패: {error_name}",
                    show_alert=True,
                )
            except Exception:
                traceback.print_exc()

            return 'OK', 200

        message = data.get("message", {})
        chat_id = message.get("chat", {}).get("id")

        if chat_id:
            send_telegram_message(
                chat_id,
                f"❌ {error_name}\n\n{error_message}"
            )

    return 'OK', 200
