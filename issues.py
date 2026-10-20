"""이슈 ↔ 섹터 반응. 뉴스 제목으로 이슈를 찾고, 그 이슈의 지표가 움직인 방향과
관련 섹터가 실제로 같은 쪽으로 움직였는지(가설이 맞았는지) 5거래일 기준으로 맞춰 봐요."""
from __future__ import annotations

import re

import config as C

RATE_LIKE = {"^TNX", "^FVX", "^TYX", "^VIX", "^MOVE", "^OVX"}   # 등락률 대신 절대 변화로 보는 것


def move(snap: dict, sym: str) -> tuple[float | None, str]:
    """5거래일 변화와 표시 문자열."""
    if sym.startswith("fred:"):
        s = snap["fred"].get(sym[5:]) or snap["sm"].get(sym)
        v = s and s.get("a5")
        return v, "—" if v is None else f"{v:+.2f}%p"
    s = snap["sm"].get(sym)
    if not s:
        return None, "—"
    if sym in RATE_LIKE:
        v = s.get("a5")
        return v, "—" if v is None else (f"{v:+.2f}%p" if sym in ("^TNX", "^FVX", "^TYX") else f"{v:+.2f}")
    v = s.get("d5")
    return v, "—" if v is None else f"{v:+.2f}%"


def name_of(sym: str) -> str:
    table = {i["yf"]: i["name"] for i in C.INDICES} | {m["yf"]: m["name"] for m in C.MACRO if m["yf"]}
    table |= {v["yf"]: v["name"].split(" (")[0] for v in C.VOL} | dict(C.SECTORS) | dict(C.THEMES)
    table |= {"fred:" + f["id"]: f["name"] for f in C.FRED} | {"fred:DGS2": "미국 2년물"}
    return table.get(sym, sym)


def build(snap: dict) -> list[dict]:
    news = snap.get("news") or []
    out = []
    for iss in C.ISSUES:
        rx = re.compile(iss["words"], re.I)
        hits = [n for n in news if any(rx.search(t) for t in n.get("titles", [n["title"]]))]
        facts = [n for n in hits if n["status"] in ("교차확인", "단일출처")]
        major = sorted({m for n in hits for m in n.get("major", [])})
        dv, dtxt = move(snap, iss["driver"][0])
        drivers = [(name_of(d), move(snap, d)[1]) for d in iss["driver"]]
        links, agree, total = [], 0, 0
        for sym, how, why in iss["links"]:
            v, txt = move(snap, sym)
            ok = None
            if v is not None and dv is not None and abs(dv) > 1e-9 and abs(v) > 1e-9:
                ok = (v > 0) == (dv > 0) if how == "same" else (v > 0) != (dv > 0)
                total += 1
                agree += ok
            links.append({"sym": sym, "name": name_of(sym), "how": how, "why": why, "move": txt, "v": v, "ok": ok})
        out.append({**{k: iss[k] for k in ("key", "name")}, "news": hits, "n_fact": len(facts),
                    "n_cross": sum(1 for n in hits if n["status"] == "교차확인"), "major": major,
                    "drivers": drivers, "dv": dv, "links": links, "agree": agree, "total": total,
                    "comment": _comment(iss, drivers, dv, links, agree, total, len(hits))})
    # 뉴스가 많고 지표가 크게 움직인 이슈부터
    out.sort(key=lambda x: (-(x["n_cross"] * 2 + len(x["news"])), -abs(x["dv"] or 0)))
    return out


def _comment(iss, drivers, dv, links, agree, total, n_news) -> str:
    if dv is None:
        return "지표를 불러오지 못했어요."
    head = f"{drivers[0][0]} 5일 {drivers[0][1]}"
    if not total:
        return head + "."
    if agree == total:
        tail = "관련 섹터가 모두 가설대로 움직였어요 → 시장이 이 이슈를 가격에 반영하는 중"
    elif agree == 0:
        tail = "관련 섹터가 가설과 반대로 움직였어요 → 이 이슈보다 다른 힘(실적·수급·다른 매크로)이 더 큰 상태"
    else:
        tail = f"가설과 같은 방향 {agree}/{total} → 반응이 섞여 있어요(이슈 영향이 부분적)"
    news = f" 관련 뉴스 {n_news}건." if n_news else " 지난 24시간 관련 뉴스는 없어요(지표만 움직임)."
    return f"{head}. {tail}.{news}"
