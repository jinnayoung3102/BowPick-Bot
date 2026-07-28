import os
import time
import traceback
import requests
from openai import OpenAI
from flask import Flask, request

try:
    from api.sheets import (
        test_sheet_connection,
        save_wednesday_selection,
        get_wednesday_selections,
        get_active_staff_members,
        get_enabled_rules,
        get_assignment_history,
        get_applications,
    )

    from api.ai import (
        generate_staff_assignment,
        format_assignment_message,
    )

    from api.telegram import (
        send_wednesday_recruitment,
        update_wednesday_recruitment,
        answer_callback_query,
    )

except ImportError:
    from sheets import (
        test_sheet_connection,
        save_wednesday_selection,
        get_wednesday_selections,
        get_active_staff_members,
        get_enabled_rules,
        get_assignment_history,
        get_applications,
    )

    from ai import (
        generate_staff_assignment,
        format_assignment_message,
    )

    from telegram import (
        send_wednesday_recruitment,
        update_wednesday_recruitment,
        answer_callback_query,
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


# 수요예배 테스트 기본 인원
DEFAULT_WEDNESDAY_NOON_NAMES = [
    "김지은",
    "김민창",
    "김영식",
    "정은혜",
    "박주영",
    "진나영",
]

DEFAULT_WEDNESDAY_EVENING_NAMES = [
    "강예린",
    "김소연",
    "한예준",
    "서태희",
    "김유진",
    "노유림",
    "이경환",
]


def send_telegram_message(chat_id, text):
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        return

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": chat_id,
        "text": text,
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=10,
        )
        response.raise_for_status()

    except Exception as error:
        print(f"Telegram Send Error: {error}")


def call_chatgpt(prompt):
    if not OPENAI_API_KEY:
        return "⚠️ OPENAI_API_KEY가 설정되지 않았습니다."

    try:
        response = client.responses.create(
            model="gpt-5-mini",
            input=prompt,
        )

        return response.output_text.strip()

    except Exception as error:
        return f"❌ ChatGPT API 오류: {str(error)}"


def unique_names(names):
    """
    이름 중복을 제거하면서 기존 순서를 유지한다.
    """
    result = []
    seen = set()

    for name in names:
        clean_name = str(name).strip()

        if not clean_name:
            continue

        if clean_name in seen:
            continue

        seen.add(clean_name)
        result.append(clean_name)

    return result


def build_wednesday_live_names(recruitment_id):
    """
    기본 명단에 신청현황의 최신 선택을 반영한다.

    정오 선택:
    정오 명단에만 포함

    저녁 선택:
    저녁 명단에만 포함

    불참 선택:
    두 명단에서 모두 제외
    """
    noon_names = list(DEFAULT_WEDNESDAY_NOON_NAMES)
    evening_names = list(DEFAULT_WEDNESDAY_EVENING_NAMES)

    selections = get_wednesday_selections(
        recruitment_id
    )

    for application in selections:
        name = str(
            application.get("name", "")
        ).strip()

        selection = str(
            application.get("selection", "")
        ).strip()

        if not name:
            continue

        # 기존 위치에서 먼저 제거
        noon_names = [
            saved_name
            for saved_name in noon_names
            if saved_name != name
        ]

        evening_names = [
            saved_name
            for saved_name in evening_names
            if saved_name != name
        ]

        # 마지막 선택 상태에 따라 다시 추가
        if selection == "정오":
            noon_names.append(name)

        elif selection == "저녁":
            evening_names.append(name)

        elif selection == "불참":
            pass

    return (
        unique_names(noon_names),
        unique_names(evening_names),
    )


@app.route("/", methods=["GET", "POST"])
@app.route("/api/index", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        return "BowPick Bot is running!", 200

    data = request.get_json(silent=True) or {}

    try:
        # ==================================================
        # 인라인 버튼 클릭 처리
        # ==================================================
        callback_query = data.get("callback_query")

        if callback_query:
            callback_query_id = callback_query.get("id")
            callback_data = callback_query.get("data", "")

            parts = callback_data.split("|")

            if len(parts) != 3 or parts[0] != "apply":
                answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="⚠️ 올바르지 않은 버튼입니다.",
                    show_alert=False,
                )
                return "OK", 200

            recruitment_id = parts[1]
            selection = parts[2]

            # 콜백 만료를 막기 위해 먼저 즉시 응답
            if selection == "noon":
                immediate_notice = (
                    "☀️ 정오예배 선택을 반영합니다."
                )

            elif selection == "evening":
                immediate_notice = (
                    "🌙 저녁예배 선택을 반영합니다."
                )

            elif selection == "absent":
                immediate_notice = (
                    "❌ 불참 선택을 반영합니다."
                )

            elif selection == "attend":
                immediate_notice = (
                    "⭕ 참석 선택을 반영합니다."
                )

            else:
                immediate_notice = (
                    "⚠️ 선택 내용을 확인할 수 없습니다."
                )

            answer_callback_query(
                callback_query_id=callback_query_id,
                text=immediate_notice,
                show_alert=False,
            )

            # 버튼을 누른 사용자 정보
            callback_user = callback_query.get(
                "from",
                {},
            )

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

            # 수요예배 버튼 처리
            if selection in {
                "noon",
                "evening",
                "absent",
            }:
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

                print(
                    "Application saved:",
                    {
                        "recruitment_id": recruitment_id,
                        "selection": selection,
                        "user_id": callback_user_id,
                        "name": saved_name,
                    }
                )

                # 여러 사람이 거의 동시에 누를 경우를 고려해
                # 잠시 기다린 뒤 최신 시트 내용을 다시 읽는다.
                time.sleep(0.2)

                noon_names, evening_names = (
                    build_wednesday_live_names(
                        recruitment_id
                    )
                )

                callback_message = callback_query.get(
                    "message",
                    {},
                )

                callback_chat_id = callback_message.get(
                    "chat",
                    {},
                ).get("id")

                callback_message_id = (
                    callback_message.get("message_id")
                )

                if (
                    callback_chat_id
                    and callback_message_id
                ):
                    try:
                        update_wednesday_recruitment(
                            chat_id=callback_chat_id,
                            message_id=callback_message_id,
                            recruitment_id=recruitment_id,
                            service_date="수요예배 테스트",
                            noon_names=noon_names,
                            evening_names=evening_names,
                            deadline_text=(
                                "테스트 종료 전까지"
                            ),
                        )

                    except RuntimeError as update_error:
                        error_text = str(
                            update_error
                        ).strip()

                        error_text_lower = (
                            error_text.lower()
                        )

                        print(
                            "Telegram message update error:",
                            error_text,
                        )

                        # 같은 선택을 다시 눌러서
                        # 모집글 내용이 변하지 않은 경우는 정상 처리
                        if (
                            "message is not modified"
                            in error_text_lower
                            or "message_not_modified"
                            in error_text_lower
                        ):
                            pass

                        else:
                            raise

            elif selection == "attend":
                print(
                    "Sunday attendance callback received:",
                    {
                        "recruitment_id": recruitment_id,
                        "user_id": callback_user_id,
                    }
                )

            else:
                print(
                    "Unknown callback selection:",
                    selection,
                )

            return "OK", 200

        # ==================================================
        # 일반 텔레그램 메시지 처리
        # ==================================================
        message = data.get("message", {})

        text = message.get("text", "")
        chat_id = message.get(
            "chat",
            {},
        ).get("id")

        user_id = str(
            message.get(
                "from",
                {},
            ).get("id", "")
        )

        if not chat_id or not text:
            return "OK", 200

        # 구글 스프레드시트 연결 테스트
        if text.strip() == "바우픽 테스트":
            result = test_sheet_connection()

            if result.get("success"):
                sheet_names = "\n".join(
                    [
                        f"- {name}"
                        for name in result.get(
                            "sheets",
                            [],
                        )
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

            send_telegram_message(
                chat_id,
                reply,
            )

        # 수요예배 모집글 및 버튼 출력 테스트
                # 자동배치 테스트
        elif text.strip() == "바우픽 수요 배치 테스트":

            if user_id != ADMIN_TELEGRAM_ID:
                send_telegram_message(
                    chat_id,
                    "⛔ 관리자 전용 기능입니다.",
                )
                return "OK", 200

            applications = get_applications()

            attendees = []

            for row in applications:

                if (
                    str(row.get("모집ID", "")).strip() == "WED-TEST-001"
                    and str(row.get("예배구분", "")).strip() == "수요정오"
                    and str(row.get("최종상태", "")).strip().upper() == "O"
                ):
                    attendees.append(
                        row.get("이름")
                    )

            staff_members = get_active_staff_members()

            rules = get_enabled_rules()

            history = get_assignment_history()

            result = generate_staff_assignment(
                service_date="수요예배 테스트",
                service_type="수요정오",
                attendees=attendees,
                staff_members=staff_members,
                rules=rules,
                history=history,
            )

            message = format_assignment_message(result)

            send_telegram_message(
                chat_id,
                message,
            ):
            if user_id != ADMIN_TELEGRAM_ID:
                send_telegram_message(
                    chat_id,
                    "⛔ 관리자 전용 테스트입니다.",
                )
                return "OK", 200

            recruitment_id = "WED-TEST-001"

            noon_names, evening_names = (
                build_wednesday_live_names(
                    recruitment_id
                )
            )

            send_wednesday_recruitment(
                chat_id=chat_id,
                recruitment_id=recruitment_id,
                service_date="수요예배 테스트",
                noon_names=noon_names,
                evening_names=evening_names,
                deadline_text=(
                    "테스트 종료 전까지"
                ),
            )

        # 규칙 조회
        elif "바우픽 규칙 보여줘" in text:
            rules_str = "\n".join(
                [
                    f"- {rule}"
                    for rule in DEFAULT_RULES
                ]
            )

            reply = (
                "🤖 [현재 적용 중인 바우픽 기본 규칙]\n"
                f"{rules_str}"
            )

            send_telegram_message(
                chat_id,
                reply,
            )

        # 일반 바우픽 호출은 관리자만 ChatGPT 사용 가능
        elif "바우픽" in text:
            if user_id != ADMIN_TELEGRAM_ID:
                send_telegram_message(
                    chat_id,
                    "⛔ 관리자 전용 기능입니다.\n"
                    "OpenAI 기능은 관리자만 사용할 수 있습니다.",
                )
                return "OK", 200

            prompt = f"""
너는 참불 관리 및 스태프 안내를 돕는 AI 조교 '바우픽'이야.
사용자가 한 말에 맞춰 친절하고 센스 있게 대답해줘.

업무, 스태프, 명단 정리, 보고,
규칙 수정 등에 대한 요청에는
아래 기본 규칙을 참고해.

[기본 규칙]
{chr(10).join(DEFAULT_RULES)}

사용자 메시지:
{text}
"""

            reply_text = call_chatgpt(prompt)

            send_telegram_message(
                chat_id,
                reply_text,
            )

    except Exception as error:
        traceback.print_exc()

        error_name = type(error).__name__
        error_message = (
            str(error).strip()
            or "오류 상세 내용이 없습니다."
        )

        callback_query = data.get(
            "callback_query"
        )

        if callback_query:
            # 콜백은 이미 즉시 응답했으므로
            # 다시 팝업을 전송하지 않고 로그만 남긴다.
            print(
                "Callback processing error:",
                error_name,
                error_message,
            )

            return "OK", 200

        message = data.get("message", {})

        chat_id = message.get(
            "chat",
            {},
        ).get("id")

        if chat_id:
            send_telegram_message(
                chat_id,
                f"❌ {error_name}\n\n{error_message}",
            )

    return "OK", 200
