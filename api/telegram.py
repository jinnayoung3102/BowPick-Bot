import os
import requests


TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

if TELEGRAM_BOT_TOKEN:
    TELEGRAM_API_URL = (
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    )
else:
    TELEGRAM_API_URL = ""


def telegram_api_request(method, payload=None, timeout=15):
    """
    Telegram Bot API에 요청을 전송한다.
    성공하면 result 값을 반환한다.
    """
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN 환경변수가 설정되지 않았습니다."
        )

    url = f"{TELEGRAM_API_URL}/{method}"

    try:
        response = requests.post(
            url,
            json=payload or {},
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()

    except requests.RequestException as error:
        raise RuntimeError(
            f"Telegram API 요청 실패: {error}"
        ) from error

    except ValueError as error:
        raise RuntimeError(
            "Telegram API 응답을 읽을 수 없습니다."
        ) from error

    if not data.get("ok"):
        description = data.get(
            "description",
            "알 수 없는 Telegram 오류",
        )
        raise RuntimeError(description)

    return data.get("result")


def send_telegram_message(
    chat_id,
    text,
    reply_markup=None,
):
    """
    일반 텔레그램 메시지를 전송한다.
    reply_markup을 넣으면 인라인 버튼도 함께 전송한다.
    """
    payload = {
        "chat_id": chat_id,
        "text": text,
    }

    if reply_markup:
        payload["reply_markup"] = reply_markup

    return telegram_api_request(
        "sendMessage",
        payload,
    )


def edit_telegram_message(
    chat_id,
    message_id,
    text,
    reply_markup=None,
):
    """
    기존 모집 메시지의 내용과 버튼을 수정한다.
    참석자 명단 실시간 갱신에 사용한다.
    """
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
    }

    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    return telegram_api_request(
        "editMessageText",
        payload,
    )


def answer_callback_query(
    callback_query_id,
    text=None,
    show_alert=False,
):
    """
    버튼을 누른 사람에게 확인 메시지를 표시한다.

    show_alert=False:
    화면 아래에 잠깐 표시

    show_alert=True:
    팝업창으로 표시
    """
    payload = {
        "callback_query_id": callback_query_id,
        "show_alert": show_alert,
    }

    if text:
        payload["text"] = text

    return telegram_api_request(
        "answerCallbackQuery",
        payload,
    )


def remove_inline_keyboard(
    chat_id,
    message_id,
):
    """
    모집이 마감되면 기존 메시지에서 버튼만 제거한다.
    """
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "reply_markup": {
            "inline_keyboard": []
        },
    }

    return telegram_api_request(
        "editMessageReplyMarkup",
        payload,
    )


def make_wednesday_keyboard(recruitment_id):
    """
    수요예배용 선택 버튼을 만든다.

    정오 참석:
    정오 O / 저녁 X

    저녁 참석:
    정오 X / 저녁 O

    둘 다 불참:
    정오 X / 저녁 X
    """
    return {
        "inline_keyboard": [
            [
                {
                    "text": "☀️ 정오 참석",
                    "callback_data": (
                        f"apply|{recruitment_id}|noon"
                    ),
                },
                {
                    "text": "🌙 저녁 참석",
                    "callback_data": (
                        f"apply|{recruitment_id}|evening"
                    ),
                },
            ],
            [
                {
                    "text": "❌ 둘 다 불참",
                    "callback_data": (
                        f"apply|{recruitment_id}|absent"
                    ),
                }
            ],
        ]
    }


def make_sunday_keyboard(recruitment_id):
    """
    주일 정오예배용 참석/불참 버튼을 만든다.
    """
    return {
        "inline_keyboard": [
            [
                {
                    "text": "⭕ 참석",
                    "callback_data": (
                        f"apply|{recruitment_id}|attend"
                    ),
                },
                {
                    "text": "❌ 불참",
                    "callback_data": (
                        f"apply|{recruitment_id}|absent"
                    ),
                },
            ]
        ]
    }


def format_names(names):
    """
    이름 목록을 단체방 표시용 문자열로 변환한다.
    """
    cleaned_names = [
        str(name).strip()
        for name in names
        if str(name).strip()
    ]

    if not cleaned_names:
        return "아직 참석자가 없습니다."

    return " ".join(cleaned_names)


def make_wednesday_recruitment_text(
    service_date,
    noon_names,
    evening_names,
    deadline_text="오늘 자정",
):
    """
    수요 정오·저녁 모집글을 만든다.
    불참자 명단은 표시하지 않는다.
    """
    noon_text = format_names(noon_names)
    evening_text = format_names(evening_names)

    return (
        f"✅ {service_date} 스탭가능자 파악\n\n"
        f"🔸 정오예배 · {len(noon_names)}명\n"
        f"- {noon_text}\n\n"
        f"🔸 저녁예배 · {len(evening_names)}명\n"
        f"- {evening_text}\n\n"
        f"정오와 저녁 중 한 예배만 선택할 수 있습니다.\n"
        f"선택을 변경하려면 다른 버튼을 다시 눌러주세요.\n\n"
        f"⏰ 마감: {deadline_text}"
    )


def make_sunday_recruitment_text(
    service_date,
    attendee_names,
    deadline_text="오늘 자정",
):
    """
    주일 정오예배 모집글을 만든다.
    불참자 명단은 표시하지 않는다.
    """
    attendee_text = format_names(attendee_names)

    return (
        f"✅ {service_date} 스탭가능자 파악\n\n"
        f"🔸 주일 정오예배 · {len(attendee_names)}명\n"
        f"- {attendee_text}\n\n"
        f"선택을 변경하려면 버튼을 다시 눌러주세요.\n\n"
        f"⏰ 마감: {deadline_text}"
    )


def send_wednesday_recruitment(
    chat_id,
    recruitment_id,
    service_date,
    noon_names,
    evening_names,
    deadline_text="오늘 자정",
):
    """
    수요예배 모집 메시지와 버튼을 전송한다.

    반환값에 포함된 message_id를
    모집일정 시트에 저장해야 한다.
    """
    text = make_wednesday_recruitment_text(
        service_date=service_date,
        noon_names=noon_names,
        evening_names=evening_names,
        deadline_text=deadline_text,
    )

    keyboard = make_wednesday_keyboard(
        recruitment_id
    )

    return send_telegram_message(
        chat_id=chat_id,
        text=text,
        reply_markup=keyboard,
    )


def send_sunday_recruitment(
    chat_id,
    recruitment_id,
    service_date,
    attendee_names,
    deadline_text="오늘 자정",
):
    """
    주일 정오예배 모집 메시지와 버튼을 전송한다.
    """
    text = make_sunday_recruitment_text(
        service_date=service_date,
        attendee_names=attendee_names,
        deadline_text=deadline_text,
    )

    keyboard = make_sunday_keyboard(
        recruitment_id
    )

    return send_telegram_message(
        chat_id=chat_id,
        text=text,
        reply_markup=keyboard,
    )


def update_wednesday_recruitment(
    chat_id,
    message_id,
    recruitment_id,
    service_date,
    noon_names,
    evening_names,
    deadline_text="오늘 자정",
):
    """
    버튼이 눌릴 때마다 수요예배 모집글을 실시간 갱신한다.
    """
    text = make_wednesday_recruitment_text(
        service_date=service_date,
        noon_names=noon_names,
        evening_names=evening_names,
        deadline_text=deadline_text,
    )

    keyboard = make_wednesday_keyboard(
        recruitment_id
    )

    return edit_telegram_message(
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup=keyboard,
    )


def update_sunday_recruitment(
    chat_id,
    message_id,
    recruitment_id,
    service_date,
    attendee_names,
    deadline_text="오늘 자정",
):
    """
    버튼이 눌릴 때마다 주일 모집글을 실시간 갱신한다.
    """
    text = make_sunday_recruitment_text(
        service_date=service_date,
        attendee_names=attendee_names,
        deadline_text=deadline_text,
    )

    keyboard = make_sunday_keyboard(
        recruitment_id
    )

    return edit_telegram_message(
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup=keyboard,
    )


def close_wednesday_recruitment(
    chat_id,
    message_id,
    service_date,
    noon_names,
    evening_names,
):
    """
    수요예배 모집을 마감하고 버튼을 제거한다.
    """
    noon_text = format_names(noon_names)
    evening_text = format_names(evening_names)

    text = (
        f"🔒 {service_date} 스탭 신청이 마감되었습니다.\n\n"
        f"🔸 정오예배 · {len(noon_names)}명\n"
        f"- {noon_text}\n\n"
        f"🔸 저녁예배 · {len(evening_names)}명\n"
        f"- {evening_text}\n\n"
        f"스탭 배치를 진행합니다."
    )

    return edit_telegram_message(
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup={
            "inline_keyboard": []
        },
    )


def close_sunday_recruitment(
    chat_id,
    message_id,
    service_date,
    attendee_names,
):
    """
    주일 모집을 마감하고 버튼을 제거한다.
    """
    attendee_text = format_names(
        attendee_names
    )

    text = (
        f"🔒 {service_date} 스탭 신청이 마감되었습니다.\n\n"
        f"🔸 주일 정오예배 · {len(attendee_names)}명\n"
        f"- {attendee_text}\n\n"
        f"스탭 배치를 진행합니다."
    )

    return edit_telegram_message(
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup={
            "inline_keyboard": []
        },
    )
