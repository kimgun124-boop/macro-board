"""시황 해석 글. 매일 오전 8시·밤 8시에 Claude가 사실(지수·수급·외신)을 모아 쓴 글을
reports/YYYY-MM-DD-HHMM.md 로 저장소에 올리면, 보드가 가장 최근 글을 보여 줘요(추가 요금 없음).

글 첫 줄은 '# 제목', 그 아래 '> 요약 한 줄'을 쓰는 걸 약속으로 해요.
"""
from __future__ import annotations

import re
from pathlib import Path

DIR = Path(__file__).parent / "reports"
NAME = re.compile(r"(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})\.md$")


def all_reports() -> list[dict]:
    out = []
    for p in DIR.glob("*.md") if DIR.exists() else []:
        m = NAME.search(p.name)
        if not m:
            continue
        text = p.read_text(encoding="utf-8")
        title = next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")), p.stem)
        lead = next((l[1:].strip() for l in text.splitlines() if l.startswith(">")), "")
        y, mo, d, h, mi = m.groups()
        out.append({"file": p.name, "when": f"{y}-{mo}-{d} {h}:{mi}", "title": title, "lead": lead, "text": text})
    return sorted(out, key=lambda x: x["file"], reverse=True)


def body(text: str) -> str:
    """제목 줄은 빼고(화면이 따로 그려요) 나머지."""
    return "\n".join(l for l in text.splitlines() if not l.startswith("# ")).strip()


def section(text: str, heading: str) -> str:
    """'## heading' 아래부터 다음 '## '까지(없으면 빈 문자열)."""
    out, on = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            if on:
                break
            on = line[3:].strip().startswith(heading)
            continue
        if on:
            out.append(line)
    return "\n".join(out).strip()
