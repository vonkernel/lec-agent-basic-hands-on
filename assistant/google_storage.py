"""세션 4 실습 마지막 단계: Google Calendar·Tasks 저장소

storage.py와 같은 이름의 함수를 Google API로 구현한다. tools.py는 import 한 줄만 바꾼다."""

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from clock import local_tz_name

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SCOPES = [
    # 이 애플리케이션이 만든 캘린더와 그 일정만
    "https://www.googleapis.com/auth/calendar.app.created",
    # 할 일 목록과 할 일
    "https://www.googleapis.com/auth/tasks",
]
NAME = "AI Agent 실습"  # 실습 전용 캘린더와 할 일 목록의 이름
TZ = local_tz_name()


def login():
    """token.json이 있으면 쓰고, 없거나 만료됐으면 브라우저에서 다시 로그인한다."""
    token = ROOT / "token.json"
    creds = None
    if token.exists():
        creds = Credentials.from_authorized_user_file(token, SCOPES)
    # 테스트 상태 앱의 토큰은 7일 뒤 만료된다. 갱신이 실패하면 token.json을 지운다
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        secrets = ROOT / "credentials.json"
        flow = InstalledAppFlow.from_client_secrets_file(secrets, SCOPES)
        flow.redirect_uri = "http://localhost:8080/"
        url, _ = flow.authorization_url(prompt="consent")
        print(f"아래 주소를 브라우저에서 열고 로그인하세요.\n{url}")
        # Codespaces에서는 로그인 뒤 localhost 페이지가 열리지 않는다.
        # 주소창의 주소에 code가 들어 있다
        answer = input("로그인 뒤 이동한 페이지의 주소 전체를 붙여 넣으세요: ").strip()
        flow.fetch_token(code=parse_qs(urlparse(answer).query)["code"][0])
        creds = flow.credentials
    token.write_text(creds.to_json())
    return creds


creds = login()
calendar = build("calendar", "v3", credentials=creds)
tasks = build("tasks", "v1", credentials=creds)


def setup():
    """처음 실행할 때 실습 전용 캘린더와 할 일 목록을 만들고, id를 data/google.json에 둔다."""
    path = DATA / "google.json"
    if path.exists():
        return json.loads(path.read_text())
    cal = calendar.calendars().insert(body={"summary": NAME, "timeZone": TZ})
    tl = tasks.tasklists().insert(body={"title": NAME})
    ids = {"calendar": cal.execute()["id"], "tasklist": tl.execute()["id"]}
    DATA.mkdir(exist_ok=True)
    path.write_text(json.dumps(ids))
    return ids


IDS = setup()
CAL, TL = IDS["calendar"], IDS["tasklist"]


# 일정: Google Calendar
def to_event(e):
    return {
        "id": e["id"],
        "title": e.get("summary", ""),
        "start": e["start"]["dateTime"][:16],
        "end": e["end"]["dateTime"][:16],
    }


def add_event(title, start, end):
    body = {
        "summary": title,
        "start": {"dateTime": f"{start}:00", "timeZone": TZ},
        "end": {"dateTime": f"{end}:00", "timeZone": TZ},
    }
    event = calendar.events().insert(calendarId=CAL, body=body).execute()
    return to_event(event)


def list_events(date=""):
    request = calendar.events().list(calendarId=CAL, singleEvents=True,
                                     orderBy="startTime", timeZone=TZ)
    events = [to_event(e) for e in request.execute().get("items", [])]
    return [e for e in events if e["start"].startswith(date)]


def find_overlap(start, end):
    for e in list_events():
        if e["start"] < end and start < e["end"]:
            return e
    return None


def delete_event(event_id):
    try:
        calendar.events().delete(calendarId=CAL, eventId=event_id).execute()
        return True
    except HttpError:  # 없는 id
        return False


# 할 일: Google Tasks
def to_task(t):
    return {
        "id": t["id"],
        "todo": t["title"],
        "due": t.get("due", "")[:10],
        "complete": t["status"] == "completed",
    }


def add_task(todo, due):
    body = {"title": todo, "due": f"{due}T00:00:00.000Z"}
    return to_task(tasks.tasks().insert(tasklist=TL, body=body).execute())


def list_tasks():
    request = tasks.tasks().list(tasklist=TL, showCompleted=True,
                                 showHidden=True)
    return [to_task(t) for t in request.execute().get("items", [])]


def complete_task(task_id):
    try:
        body = {"status": "completed"}
        tasks.tasks().patch(tasklist=TL, task=task_id, body=body).execute()
        return True
    except HttpError:
        return False


def delete_task(task_id):
    try:
        tasks.tasks().delete(tasklist=TL, task=task_id).execute()
        return True
    except HttpError:
        return False


if __name__ == "__main__":
    e = add_event("팀 회의", "2026-10-15T15:00", "2026-10-15T16:00")
    print(e)
    print(list_events("2026-10-15"))
    print(find_overlap("2026-10-15T15:30", "2026-10-15T16:30"))
    t = add_task("보고서 제출", "2026-10-16")
    print(complete_task(t["id"]), list_tasks())
    print(delete_event(e["id"]), delete_task(t["id"]))  # 확인용으로 만든 것은 지운다
