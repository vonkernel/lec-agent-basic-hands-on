"""세션 3 실습: 일정·할 일 JSON 저장소"""

import json
import uuid
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def load(name):
    path = DATA / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def dump(name, items):
    DATA.mkdir(exist_ok=True)
    text = json.dumps(items, ensure_ascii=False, indent=2)
    (DATA / f"{name}.json").write_text(text, encoding="utf-8")


# 일정
def add_event(title, start, end):
    event = {"id": uuid.uuid4().hex[:6], "title": title,
             "start": start, "end": end}
    dump("events", load("events") + [event])
    return event


def list_events(date=""):
    return [e for e in load("events") if e["start"].startswith(date)]


def find_overlap(start, end):
    for e in load("events"):
        if e["start"] < end and start < e["end"]:
            return e
    return None


def delete_event(event_id):
    events = load("events")
    dump("events", [e for e in events if e["id"] != event_id])
    return any(e["id"] == event_id for e in events)


# 할 일
def add_task(todo, due):
    task = {"id": uuid.uuid4().hex[:6], "todo": todo,
            "due": due, "complete": False}
    dump("tasks", load("tasks") + [task])
    return task


def list_tasks():
    return load("tasks")


def complete_task(task_id):
    tasks = load("tasks")
    found = False
    for t in tasks:
        if t["id"] == task_id:
            t["complete"] = True
            found = True
    dump("tasks", tasks)
    return found


def delete_task(task_id):
    tasks = load("tasks")
    dump("tasks", [t for t in tasks if t["id"] != task_id])
    return any(t["id"] == task_id for t in tasks)


if __name__ == "__main__":
    e = add_event("팀 회의", "2026-10-15T15:00", "2026-10-15T16:00")
    print(e)
    print(list_events("2026-10-15"))
    print(find_overlap("2026-10-15T15:30", "2026-10-15T16:30"))
    t = add_task("보고서 제출", "2026-10-16")
    print(complete_task(t["id"]), list_tasks())
