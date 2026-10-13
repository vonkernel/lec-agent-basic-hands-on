"""세션 3 실습: 일정·할 일 도구"""

from datetime import datetime
from zoneinfo import ZoneInfo

from langchain.tools import tool

import storage
from clock import local_tz_name


@tool
def get_now() -> str:
    """현재 날짜와 시각을 이 컴퓨터의 시간대 기준으로 돌려준다.
    "오늘", "내일", "다음 주 화요일"처럼 상대적인 날짜를 해석하기 전에 먼저 호출한다."""
    now = datetime.now(ZoneInfo(local_tz_name()))
    return now.strftime("%Y-%m-%dT%H:%M (%A)")


@tool
def add_event(title: str, start: str, end: str) -> str:
    """시작과 끝 시각이 있는 일정을 등록한다. start, end는 YYYY-MM-DDTHH:MM 형식.
    기한만 있는 할 일은 이 도구가 아니라 add_task로 등록한다."""
    e = storage.add_event(title, start, end)
    return f"등록함: [{e['id']}] {title} {start} ~ {end}"


@tool
def list_events(date: str = "") -> str:
    """일정을 id와 함께 돌려준다. date(YYYY-MM-DD)를 주면 그날 일정만, 비우면 전체 일정을 돌려준다.
    일정을 지우기 전에 id를 확인할 때도 쓴다."""
    events = storage.list_events(date)
    lines = [f"[{e['id']}] {e['title']} {e['start']} ~ {e['end']}"
             for e in events]
    return "\n".join(lines) or "일정이 없습니다."


@tool
def delete_event(event_id: str) -> str:
    """id로 일정을 삭제한다. id를 모르면 먼저 list_events로 확인한다. 실행 전에 사용자 승인을 받는다."""
    return "삭제함" if storage.delete_event(event_id) else "실패"


@tool
def add_task(todo: str, due: str) -> str:
    """기한(YYYY-MM-DD)까지 해야 할 일을 등록한다. 시작과 끝 시각이 있는 약속은 add_event로 등록한다."""
    t = storage.add_task(todo, due)
    return f"등록함: [{t['id']}] {todo} (기한 {due})"


@tool
def list_tasks() -> str:
    """등록된 할 일을 id, 기한, 완료 여부와 함께 돌려준다."""
    tasks = storage.list_tasks()
    lines = []
    for t in tasks:
        state = "완료" if t["complete"] else "미완료"
        lines.append(f"[{t['id']}] {t['todo']} (기한 {t['due']}, {state})")
    return "\n".join(lines) or "등록된 할 일이 없습니다."


@tool
def complete_task(task_id: str) -> str:
    """id로 할 일을 완료로 표시한다. id를 모르면 먼저 list_tasks로 확인한다."""
    return "완료로 표시함" if storage.complete_task(task_id) else "실패"


@tool
def delete_task(task_id: str) -> str:
    """id로 할 일을 삭제한다. id를 모르면 먼저 list_tasks로 확인한다. 실행 전에 사용자 승인을 받는다."""
    return "삭제함" if storage.delete_task(task_id) else "실패"


TOOLS = [get_now, add_event, list_events, delete_event,
         add_task, list_tasks, complete_task, delete_task]

if __name__ == "__main__":
    for t in TOOLS:
        schema = t.tool_call_schema.model_json_schema()["properties"]
        print(t.name, "|", t.description.splitlines()[0], "|", schema)
