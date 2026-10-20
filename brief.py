"""매크로 아침 브리핑(GitHub Actions에서 평일 아침 실행) — 미국 마감 숫자와 교차확인 뉴스만 디스코드로 보내요.

필요한 설정: GitHub 저장소 Settings → Secrets and variables → Actions 에 DISCORD_WEBHOOK_URL
테스트: python brief.py  (웹훅이 없으면 화면에만 출력)
"""
from __future__ import annotations

import os

import requests

import config as C
import macro


def fmt(snap: dict) -> str:
    sm, ver = snap["sm"], snap["ver"]
    lines = [f"🌍 **매크로 브리핑** {snap['at']:%m/%d %H:%M}", "· " + "\n· ".join(macro.facts(snap)), ""]
    for i in C.INDICES[:8]:
        s = sm.get(i["yf"])
        if s and s["d1"] is not None:
            lines.append(f"{i['name']} {s['last']:,.2f} ({s['d1']:+.2f}%) [{ver.get(i['yf'], ('없음',))[0]}] {s['date']:%m/%d}")
    for m in C.MACRO:
        s = sm.get(macro.key_of(m))
        if s and m["kind"] == "rate" and s.get("a1") is not None:
            lines.append(f"{m['name']} {s['last']:.3f}% ({s['a1']:+.3f}%p)")
        elif s and m["name"] in ("원/달러", "WTI", "금") and s["d1"] is not None:
            lines.append(f"{m['name']} {s['last']:,.2f} ({s['d1']:+.2f}%)")
    news = [n for n in snap["news"] if n["status"] == "교차확인"][:8]
    if news:
        lines += ["", "📰 교차확인 뉴스 (언론사 2곳 이상)"]
        lines += [f"· {n['title']} — {', '.join(n['sources'][:3])}" for n in news]
    return "\n".join(lines)


def send(text: str) -> None:
    print(text)
    hook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not hook:
        print("(DISCORD_WEBHOOK_URL 이 없어서 보내지 않았어요)")
        return
    for i in range(0, len(text), 1900):          # 디스코드 한 메시지 2,000자 제한
        r = requests.post(hook, json={"content": text[i:i + 1900]}, timeout=10)
        print("discord", r.status_code)


if __name__ == "__main__":
    send(fmt(macro.snapshot()))
