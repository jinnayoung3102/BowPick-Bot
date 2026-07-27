import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import gspread
from google.oauth2.service_account import Credentials


GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get(
    "GOOGLE_SERVICE_ACCOUNT_JSON"
)
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_spreadsheet():
    """
    Vercel 환경변수에 저장된 서비스 계정 정보로
    바우픽 구글 스프레드시트에 연결한다.
    """
    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON 환경변수가 없습니다."
        )

    if not GOOGLE_SHEET_ID:
        raise RuntimeError(
            "GOOGLE_SHEET_ID 환경변수가 없습니다."
        )

    try:
        service_account_info = json.loads(
            GOOGLE_SERVICE_ACCOUNT_JSON
        )
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON 형식이 올바르지 않습니다."
        ) from error

    credentials = Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES,
    )

    client = gspread.authorize(credentials)

    return client.open_by_key(GOOGLE_SHEET_ID)


def get_worksheet(sheet_name):
    """
    시트 탭 이름으로 워크시트를 가져온다.
    """
    spreadsheet = get_spreadsheet()

    try:
        return spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound as error:
        raise RuntimeError(
            f"'{sheet_name}' 시트를 찾을 수 없습니다."
        ) from error


def get_staff_members():
    """
    '스탭명단' 시트의 모든 데이터를 불러온다.
    반환 예시:
    [
        {
            "이름": "진나영",
            "텔레그램ID": "",
            "활성": "O",
            ...
        }
    ]
    """
    worksheet = get_worksheet("스탭명단")
    return worksheet.get_all_records()


def get_active_staff_members():
    """
    스탭명단에서 활성 값이 O인 인원만 불러온다.
    """
    staff_members = get_staff_members()

    return [
        member
        for member in staff_members
        if str(member.get("활성", "")).strip().upper() == "O"
    ]


def get_enabled_rules():
    """
    '규칙' 시트에서 사용 값이 O인 규칙만 불러온다.
    """
    worksheet = get_worksheet("규칙")
    records = worksheet.get_all_records()

    return [
        record
        for record in records
        if str(record.get("사용", "")).strip().upper() == "O"
    ]


def get_rules_as_text():
    """
    활성화된 규칙을 AI가 읽기 쉬운 텍스트로 변환한다.
    """
    rules = get_enabled_rules()

    if not rules:
        return "현재 활성화된 규칙이 없습니다."

    lines = []

    for rule in rules:
        category = str(rule.get("분류", "")).strip()
        description = str(rule.get("규칙", "")).strip()

        if category and description:
            lines.append(f"- [{category}] {description}")

    return "\n".join(lines)


def get_environment_settings():
    """
    '환경설정' 시트의 항목과 값을 딕셔너리로 불러온다.

    반환 예시:
    {
        "모집채팅방": "-100123456789",
        "결과채팅방": "-100123456789",
        "관리자": "진나영"
    }
    """
    worksheet = get_worksheet("환경설정")
    rows = worksheet.get_all_values()

    settings = {}

    for row in rows[1:]:
        if len(row) < 2:
            continue

        item = row[0].strip()
        value = row[1].strip()

        if item:
            settings[item] = value

    return settings


def get_applications():
    """
    '신청현황' 시트의 모든 신청 데이터를 불러온다.
    """
    worksheet = get_worksheet("신청현황")
    return worksheet.get_all_records()


def get_assignment_history():
    """
    '배치이력' 시트의 모든 배치 데이터를 불러온다.
    """
    worksheet = get_worksheet("배치이력")
    return worksheet.get_all_records()


def append_assignment_history(
    service_date,
    service_type,
    name,
    part,
    reason,
):
    """
    배치 결과를 '배치이력' 시트에 한 줄 추가한다.
    """
    worksheet = get_worksheet("배치이력")

    created_at = datetime.now(
        ZoneInfo("Asia/Seoul")
    ).strftime("%Y-%m-%d %H:%M:%S")

    worksheet.append_row(
        [
            service_date,
            service_type,
            name,
            part,
            reason,
            created_at,
        ],
        value_input_option="USER_ENTERED",
    )


def test_sheet_connection():
    """
    구글 스프레드시트 연결 상태를 확인한다.
    """
    spreadsheet = get_spreadsheet()

    worksheet_titles = [
        worksheet.title
        for worksheet in spreadsheet.worksheets()
    ]

    required_sheets = [
        "스탭명단",
        "신청현황",
        "배치이력",
        "규칙",
        "모집일정",
        "환경설정",
    ]

    missing_sheets = [
        sheet_name
        for sheet_name in required_sheets
        if sheet_name not in worksheet_titles
    ]

    if missing_sheets:
        return {
            "success": False,
            "message": (
                "일부 시트가 없습니다: "
                + ", ".join(missing_sheets)
            ),
            "sheets": worksheet_titles,
        }

    return {
        "success": True,
        "message": "구글 스프레드시트 연결에 성공했습니다.",
        "sheets": worksheet_titles,
    }

def get_staff_name_by_telegram_id(telegram_id, fallback_name=""):
    """
    텔레그램 ID와 연결된 실제 스탭 이름을 찾는다.
    아직 ID가 등록되지 않았다면 텔레그램 표시 이름을 사용한다.
    """
    telegram_id = str(telegram_id).strip()

    for member in get_active_staff_members():
        saved_id = str(member.get("텔레그램ID", "")).strip()

        if saved_id and saved_id == telegram_id:
            return str(member.get("이름", "")).strip()

    return str(fallback_name).strip() or f"사용자-{telegram_id}"


def upsert_application(
    recruitment_id,
    service_date,
    service_type,
    telegram_id,
    name,
    selection,
    final_status,
):
    """
    같은 모집ID + 예배구분 + 텔레그램ID가 있으면 수정하고,
    없으면 새 행을 추가한다.
    """
    worksheet = get_worksheet("신청현황")
    rows = worksheet.get_all_values()

    telegram_id = str(telegram_id).strip()

    responded_at = datetime.now(
        ZoneInfo("Asia/Seoul")
    ).strftime("%Y-%m-%d %H:%M:%S")

    row_values = [
        recruitment_id,
        service_date,
        service_type,
        telegram_id,
        name,
        selection,
        responded_at,
        final_status,
    ]

    # 1행은 제목이므로 2행부터 검색
    for row_number, row in enumerate(rows[1:], start=2):
        saved_recruitment_id = (
            row[0].strip() if len(row) > 0 else ""
        )
        saved_service_type = (
            row[2].strip() if len(row) > 2 else ""
        )
        saved_telegram_id = (
            row[3].strip() if len(row) > 3 else ""
        )

        if (
            saved_recruitment_id == recruitment_id
            and saved_service_type == service_type
            and saved_telegram_id == telegram_id
        ):
            worksheet.update(
                values=[row_values],
                range_name=f"A{row_number}:H{row_number}",
                value_input_option="USER_ENTERED",
            )

            return {
                "created": False,
                "row": row_number,
            }

    worksheet.append_row(
        row_values,
        value_input_option="USER_ENTERED",
    )

    return {
        "created": True,
        "row": None,
    }


def save_wednesday_selection(
    recruitment_id,
    service_date,
    telegram_id,
    fallback_name,
    selection,
):
    """
    수요예배 선택을 저장한다.

    noon:
    수요정오 O / 수요저녁 X

    evening:
    수요정오 X / 수요저녁 O

    absent:
    수요정오 X / 수요저녁 X
    """
    if selection not in {"noon", "evening", "absent"}:
        raise ValueError(
            f"지원하지 않는 수요예배 선택입니다: {selection}"
        )

    name = get_staff_name_by_telegram_id(
        telegram_id=telegram_id,
        fallback_name=fallback_name,
    )

    if selection == "noon":
        selection_text = "정오"

        noon_status = "O"
        evening_status = "X"

    elif selection == "evening":
        selection_text = "저녁"

        noon_status = "X"
        evening_status = "O"

    else:
        selection_text = "불참"

        noon_status = "X"
        evening_status = "X"

    noon_result = upsert_application(
        recruitment_id=recruitment_id,
        service_date=service_date,
        service_type="수요정오",
        telegram_id=telegram_id,
        name=name,
        selection=selection_text,
        final_status=noon_status,
    )

    evening_result = upsert_application(
        recruitment_id=recruitment_id,
        service_date=service_date,
        service_type="수요저녁",
        telegram_id=telegram_id,
        name=name,
        selection=selection_text,
        final_status=evening_status,
    )

    return {
        "name": name,
        "selection": selection,
        "noon_status": noon_status,
        "evening_status": evening_status,
        "noon_result": noon_result,
        "evening_result": evening_result,
    }

def get_wednesday_selections(recruitment_id):
    """
    특정 수요예배 모집의 최신 선택 결과를 불러온다.

    반환 예시:
    [
        {
            "telegram_id": "1514822797",
            "name": "진나영",
            "selection": "저녁"
        }
    ]
    """
    worksheet = get_worksheet("신청현황")
    records = worksheet.get_all_records()

    selections = {}

    for record in records:
        saved_recruitment_id = str(
            record.get("모집ID", "")
        ).strip()

        service_type = str(
            record.get("예배구분", "")
        ).strip()

        telegram_id = str(
            record.get("텔레그램ID", "")
        ).strip()

        name = str(
            record.get("이름", "")
        ).strip()

        selection = str(
            record.get("선택", "")
        ).strip()

        if saved_recruitment_id != recruitment_id:
            continue

        if service_type not in {"수요정오", "수요저녁"}:
            continue

        if not telegram_id and not name:
            continue

        person_key = telegram_id or name

        selections[person_key] = {
            "telegram_id": telegram_id,
            "name": name,
            "selection": selection,
        }

    return list(selections.values())
