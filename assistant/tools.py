"""세션 3 실습: 일정 도구"""

from datetime import datetime
from zoneinfo import ZoneInfo

from langchain.tools import tool

import storage

TZ = "Asia/Seoul"  # IANA 시간대 이름. Codespaces 기본값은 UTC라 직접 정함


@tool
def get_now() -> str:
    """현재 날짜와 시각을 사용자의 시간대 기준으로 반환한다.
    "오늘", "내일", "다음 주 화요일"처럼 상대적인 날짜를 해석하기 전에 먼저 호출한다."""
    now = datetime.now(ZoneInfo(TZ))
    return now.strftime("%Y-%m-%dT%H:%M (%A)")


@tool
def add_event(title: str, start: str, end: str) -> str:
    """시작과 끝 시각이 있는 일정을 등록한다. start, end는 YYYY-MM-DDTHH:MM 형식."""
    overlap = storage.find_overlap(start, end)  # 4단계: 겹치면 오류를 반환
    if overlap:
        return (f"등록하지 않음. 해당 시간에 이미 일정이 있습니다: "
                f"{overlap['title']} {overlap['start']} ~ {overlap['end']}")
    e = storage.add_event(title, start, end)
    return f"등록함: [{e['id']}] {title} {start} ~ {end}"


@tool
def list_events(date: str = "") -> str:
    """일정을 id와 함께 반환한다. date(YYYY-MM-DD)를 주면 그날 일정만, 비우면 전체 일정을 반환한다.
    일정을 지우기 전에 id를 확인할 때도 쓴다."""
    events = storage.list_events(date)
    lines = [f"[{e['id']}] {e['title']} {e['start']} ~ {e['end']}"
             for e in events]
    return "\n".join(lines) or "일정이 없습니다."


@tool
def delete_event(event_id: str) -> str:
    """id로 일정을 삭제한다. id를 모르면 먼저 list_events로 확인한다."""
    if storage.delete_event(event_id):
        return "삭제함"
    return (f"삭제하지 않음. id {event_id}인 일정이 없습니다. "
            "list_events로 id를 확인하세요.")


TOOLS = [get_now, add_event, list_events, delete_event]

if __name__ == "__main__":
    for t in TOOLS:
        schema = t.tool_call_schema.model_json_schema()["properties"]
        print(t.name, "|", t.description.splitlines()[0], "|", schema)
