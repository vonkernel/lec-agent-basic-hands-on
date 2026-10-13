"""세션 3 실습: 이 컴퓨터의 시간대"""

import os
from datetime import datetime
from pathlib import Path


def local_tz_name() -> str:
    """이 컴퓨터의 시간대 이름(예: Asia/Seoul)을 돌려준다."""
    tz = os.environ.get("TZ")  # TZ 환경 변수가 있으면 그 값
    if tz:
        return tz
    path = str(Path("/etc/localtime").resolve())  # 예: .../zoneinfo/Asia/Seoul
    if "zoneinfo/" in path:
        return path.split("zoneinfo/")[-1]
    return datetime.now().astimezone().tzname()  # 찾지 못하면 약어(예: KST)
