import json
import os
from typing import Any

from openai import OpenAI


OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get(
    "OPENAI_MODEL",
    "gpt-5-mini",
)

client = OpenAI(api_key=OPENAI_API_KEY)


ASSIGNMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "success": {
            "type": "boolean",
        },
        "service_date": {
            "type": "string",
        },
        "service_type": {
            "type": "string",
        },
        "assignments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "part": {
                        "type": "string",
                    },
                    "names": {
                        "type": "array",
                        "items": {
                            "type": "string",
                        },
                    },
                    "reason": {
                        "type": "string",
                    },
                },
                "required": [
                    "part",
                    "names",
                    "reason",
                ],
                "additionalProperties": False,
            },
        },
        "unassigned_parts": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "warnings": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "summary": {
            "type": "string",
        },
    },
    "required": [
        "success",
        "service_date",
        "service_type",
        "assignments",
        "unassigned_parts",
        "warnings",
        "summary",
    ],
    "additionalProperties": False,
}


def normalize_name(value: Any) -> str:
    """
    이름 앞뒤 공백을 제거한다.
    """
    return str(value or "").strip()


def unique_names(names: list[Any]) -> list[str]:
    """
    이름 중복을 제거하면서 기존 순서를 유지한다.
    """
    result = []
    seen = set()

    for name in names:
        clean_name = normalize_name(name)

        if not clean_name:
            continue

        if clean_name in seen:
            continue

        seen.add(clean_name)
        result.append(clean_name)

    return result


def normalize_attendees(
    attendees: list[Any],
) -> list[str]:
    """
    참석자 입력을 이름 목록으로 정리한다.

    허용 형식:
    [
        "진나영",
        "김지은"
    ]

    또는:

    [
        {"이름": "진나영"},
        {"name": "김지은"}
    ]
    """
    names = []

    for attendee in attendees or []:
        if isinstance(attendee, dict):
            name = (
                attendee.get("이름")
                or attendee.get("name")
                or attendee.get("성명")
                or ""
            )
        else:
            name = attendee

        clean_name = normalize_name(name)

        if clean_name:
            names.append(clean_name)

    return unique_names(names)


def normalize_staff_members(
    staff_members: list[dict],
) -> list[dict]:
    """
    스탭명단 데이터를 AI가 읽기 쉬운 형태로 정리한다.
    """
    normalized = []

    for member in staff_members or []:
        if not isinstance(member, dict):
            continue

        name = normalize_name(
            member.get("이름")
            or member.get("name")
        )

        if not name:
            continue

        available_parts = (
            member.get("가능파트")
            or member.get("배치가능파트")
            or member.get("파트")
            or member.get("available_parts")
            or ""
        )

        if isinstance(available_parts, list):
            part_list = [
                normalize_name(part)
                for part in available_parts
                if normalize_name(part)
            ]
        else:
            part_text = str(
                available_parts or ""
            )

            part_text = (
                part_text
                .replace("/", ",")
                .replace("·", ",")
            )

            part_list = [
                part.strip()
                for part in part_text.split(",")
                if part.strip()
            ]

        normalized.append(
            {
                "name": name,
                "available_parts": part_list,
                "active": normalize_name(
                    member.get("활성", "O")
                ),
            }
        )

    return normalized


def normalize_rules(
    rules: list[Any],
) -> list[str]:
    """
    규칙 시트 데이터를 텍스트 목록으로 정리한다.
    """
    normalized = []

    for rule in rules or []:
        if isinstance(rule, dict):
            enabled = normalize_name(
                rule.get("사용", "O")
            ).upper()

            if enabled and enabled != "O":
                continue

            category = normalize_name(
                rule.get("분류")
                or rule.get("category")
            )

            description = normalize_name(
                rule.get("규칙")
                or rule.get("내용")
                or rule.get("description")
            )

            if category and description:
                normalized.append(
                    f"[{category}] {description}"
                )
            elif description:
                normalized.append(description)

        else:
            description = normalize_name(rule)

            if description:
                normalized.append(description)

    return normalized


def normalize_history(
    history: list[dict],
    limit: int = 100,
) -> list[dict]:
    """
    최근 배치이력을 AI가 읽기 쉬운 형태로 정리한다.
    """
    normalized = []

    for record in (history or [])[-limit:]:
        if not isinstance(record, dict):
            continue

        normalized.append(
            {
                "service_date": normalize_name(
                    record.get("예배일")
                    or record.get("service_date")
                ),
                "service_type": normalize_name(
                    record.get("예배구분")
                    or record.get("service_type")
                ),
                "name": normalize_name(
                    record.get("이름")
                    or record.get("name")
                ),
                "part": normalize_name(
                    record.get("파트")
                    or record.get("part")
                ),
                "reason": normalize_name(
                    record.get("배치사유")
                    or record.get("reason")
                ),
            }
        )

    return normalized


def build_assignment_prompt(
    service_date: str,
    service_type: str,
    attendees: list[str],
    staff_members: list[dict],
    rules: list[str],
    history: list[dict],
) -> str:
    """
    GPT에 전달할 자동배치 프롬프트를 만든다.
    """
    input_data = {
        "service_date": service_date,
        "service_type": service_type,
        "attendees": attendees,
        "staff_members": staff_members,
        "rules": rules,
        "recent_assignment_history": history,
    }

    return f"""
너는 교회 예배 영상·방송 스태프를 배치하는 AI 조교
'바우픽'이다.

아래 데이터와 규칙을 사용하여 예배 스태프를 배치하라.

[절대 원칙]

1. 참석자 목록에 없는 사람은 절대 배치하지 않는다.

2. 각 사람은 스탭명단에 기록된 가능 파트에만 배치한다.

3. 규칙 목록은 위에서 아래로 읽되,
   필수파트·예외규칙·우선순위를 모두 지킨다.

4. PD, 자막, PC는 인원이 부족하더라도 우선 배치한다.

5. 수요예배 인원이 부족하면
   CAM 1번, CAM 2번, CAM 3번은 미배치할 수 있다.

6. 규칙에서 허용한 경우에만 겸직과 중복배치를 한다.

7. PD와 TD 겸직 규칙이 활성화되어 있으면
   같은 사람을 PD와 TD에 동시에 배치할 수 있다.

8. 기술 파트 중복 규칙은
   해당 규칙에 적힌 제외 파트를 반드시 지킨다.

9. TD, 자막, 팬틸트는 최근 배치이력을 기준으로
   순환 배치한다.

10. 총괄, PD, PC, 기술, 음향, CAM은
    배치이력보다 고정 우선순위와 규칙을 우선한다.

11. 기도자는 참석자 전체 중 한 명을 선정한다.
    별도의 가능파트 제한을 적용하지 않는다.

12. PC는 최대 2명까지 배치한다.

13. 같은 파트에 여러 명이 필요한 경우
    names 배열에 모두 넣는다.

14. 주일예배 제외 규칙과
    주일 음향 전원배치 규칙을 정확히 적용한다.

15. 인원이 부족해 배치하지 못한 파트는
    임의의 사람을 억지로 넣지 말고
    unassigned_parts에 기록한다.

16. 존재하지 않는 사람, 파트, 규칙을 만들어내지 않는다.

17. 배치 이유에는 적용된 우선순위,
    순환 기준 또는 예외규칙을 간단히 적는다.

[입력 데이터]

{json.dumps(
    input_data,
    ensure_ascii=False,
    indent=2,
)}

위 입력만 사용하여 최선의 배치를 생성하라.
"""


def validate_assignment_result(
    result: dict,
    attendees: list[str],
) -> dict:
    """
    AI 결과에 참석자가 아닌 사람이 들어갔는지 검사한다.
    """
    attendee_set = set(attendees)

    invalid_names = []

    for assignment in result.get(
        "assignments",
        [],
    ):
        names = assignment.get("names", [])

        cleaned_names = unique_names(names)
        assignment["names"] = cleaned_names

        for name in cleaned_names:
            if name not in attendee_set:
                invalid_names.append(name)

    if invalid_names:
        invalid_names = unique_names(
            invalid_names
        )

        raise ValueError(
            "AI가 참석자 목록에 없는 사람을 "
            "배치했습니다: "
            + ", ".join(invalid_names)
        )

    return result


def generate_staff_assignment(
    service_date,
    service_type,
    attendees,
    staff_members,
    rules,
    history,
):
    """
    OpenAI를 사용하여 자동 스태프 배치를 생성한다.

    반환 예시:

    {
        "success": True,
        "service_date": "2026-07-29",
        "service_type": "수요정오",
        "assignments": [
            {
                "part": "총괄",
                "names": ["정봉주"],
                "reason": "총괄 우선순위 1순위"
            }
        ],
        "unassigned_parts": [],
        "warnings": [],
        "summary": "배치가 완료되었습니다."
    }
    """
    if not OPENAI_API_KEY:
        return {
            "success": False,
            "service_date": str(
                service_date or ""
            ),
            "service_type": str(
                service_type or ""
            ),
            "assignments": [],
            "unassigned_parts": [],
            "warnings": [
                "OPENAI_API_KEY가 설정되지 않았습니다."
            ],
            "summary": (
                "OpenAI API 키가 없어 "
                "자동배치를 실행할 수 없습니다."
            ),
        }

    clean_service_date = normalize_name(
        service_date
    )

    clean_service_type = normalize_name(
        service_type
    )

    clean_attendees = normalize_attendees(
        attendees
    )

    clean_staff_members = (
        normalize_staff_members(
            staff_members
        )
    )

    clean_rules = normalize_rules(rules)

    clean_history = normalize_history(
        history
    )

    if not clean_attendees:
        return {
            "success": False,
            "service_date": clean_service_date,
            "service_type": clean_service_type,
            "assignments": [],
            "unassigned_parts": [],
            "warnings": [
                "참석자가 없습니다."
            ],
            "summary": (
                "참석자가 없어 자동배치를 "
                "진행하지 않았습니다."
            ),
        }

    prompt = build_assignment_prompt(
        service_date=clean_service_date,
        service_type=clean_service_type,
        attendees=clean_attendees,
        staff_members=clean_staff_members,
        rules=clean_rules,
        history=clean_history,
    )

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            input=[
                {
                    "role": "developer",
                    "content": (
                        "반드시 제공된 JSON Schema를 "
                        "따라 결과를 반환한다."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "staff_assignment",
                    "description": (
                        "예배 스태프 자동배치 결과"
                    ),
                    "schema": ASSIGNMENT_SCHEMA,
                    "strict": True,
                }
            },
        )

        output_text = (
            response.output_text or ""
        ).strip()

        if not output_text:
            raise RuntimeError(
                "OpenAI 응답 내용이 비어 있습니다."
            )

        result = json.loads(output_text)

        result = validate_assignment_result(
            result=result,
            attendees=clean_attendees,
        )

        return result

    except json.JSONDecodeError as error:
        return {
            "success": False,
            "service_date": clean_service_date,
            "service_type": clean_service_type,
            "assignments": [],
            "unassigned_parts": [],
            "warnings": [
                f"AI 응답 JSON 변환 실패: {error}"
            ],
            "summary": (
                "자동배치 응답을 읽지 못했습니다."
            ),
        }

    except Exception as error:
        return {
            "success": False,
            "service_date": clean_service_date,
            "service_type": clean_service_type,
            "assignments": [],
            "unassigned_parts": [],
            "warnings": [
                f"{type(error).__name__}: {str(error)}"
            ],
            "summary": (
                "자동배치 중 오류가 발생했습니다."
            ),
        }


def format_assignment_message(
    assignment_result,
):
    """
    자동배치 결과를 텔레그램 공지문으로 변환한다.
    """
    if not assignment_result.get(
        "success"
    ):
        warnings = assignment_result.get(
            "warnings",
            [],
        )

        warning_text = "\n".join(
            [
                f"- {warning}"
                for warning in warnings
            ]
        )

        return (
            "❌ 자동배치 실패\n\n"
            f"{assignment_result.get('summary', '')}"
            + (
                f"\n\n{warning_text}"
                if warning_text
                else ""
            )
        )

    service_date = assignment_result.get(
        "service_date",
        "",
    )

    service_type = assignment_result.get(
        "service_type",
        "",
    )

    lines = [
        "✅ 스탭 자동배치 완료",
        "",
        f"✔️ {service_date} {service_type}",
        "",
    ]

    for assignment in assignment_result.get(
        "assignments",
        [],
    ):
        part = assignment.get("part", "")
        names = assignment.get("names", [])

        if not part or not names:
            continue

        # PC는 두 번째 담당자를 괄호로 표시
        if part == "PC" and len(names) >= 2:
            names_text = (
                f"{names[0]} ({names[1]})"
            )
        else:
            names_text = " ".join(names)

        lines.append(
            f"🔸 {part}: {names_text}"
        )

    unassigned_parts = assignment_result.get(
        "unassigned_parts",
        [],
    )

    if unassigned_parts:
        lines.extend(
            [
                "",
                "⚠️ 미배치 파트",
                "- " + " ".join(
                    unassigned_parts
                ),
            ]
        )

    warnings = assignment_result.get(
        "warnings",
        [],
    )

    if warnings:
        lines.extend(
            [
                "",
                "📌 참고",
            ]
        )

        for warning in warnings:
            lines.append(
                f"- {warning}"
            )

    if "주일" in service_type:
        lines.extend(
            [
                "",
                "※ 예배 후 장비 정리 필수",
            ]
        )

    return "\n".join(lines)
