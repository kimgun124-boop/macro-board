"""경제지표·신용 스프레드 자료를 받아 data/fred.csv로 저장해요(GitHub Actions에서 하루 두 번 실행).

스트림릿 서버에서는 FRED(세인트루이스 연준)가 막혀 경제지표가 비어 보여요. 깃허브 서버에서 미리 받아
저장소에 넣어 두면, 앱은 이 파일을 먼저 읽어요. 숫자는 원래 출처(FRED·BLS·연준 등) 값 그대로예요.

실행: python update_data.py          (data/fred.csv, data/fred_meta.json 생성)
     python update_data.py --probe  (대체 출처가 열리는지만 확인)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import pandas as pd

import config as C
import sources as S

# (시리즈, 받을 기간 일수) · 경제지표는 12년, 금리·신용은 3년
SERIES = ([(e["id"], 365 * 12) for e in C.ECON] + [(f["id"], 1100) for f in C.FRED]
          + [(m["fred"], 1100) for m in C.MACRO if m.get("fred")])

PROBE = ["https://www.census.gov/retail/sales.html", "https://www.census.gov/retail/marts/www/timeseries.html",
         "https://www.census.gov/retail/index.html"]


def probe() -> None:
    import re
    for url in PROBE:
        try:
            r = S.session.get(url, timeout=30)
            links = sorted(set(re.findall(r'href="([^"]*(?:marts|xls|csv|timeseries)[^"]*)"', r.text, re.I)))
            print(f"{url}: {r.status_code} {links[:60]}")
        except Exception as e:
            print(f"{url} 실패 {e}")
    try:
        r = S.session.get("https://api.stlouisfed.org/fred/series/observations",
                          params={"series_id": "RSAFS", "api_key": "0" * 32, "file_type": "json"}, timeout=30)
        print(f"FRED API(가짜 키): {r.status_code} {r.text[:200]!r}")
    except Exception as e:
        print(f"FRED API 실패 {e.__class__.__name__}: {str(e)[:100]}")


def main() -> int:
    frames, src, missing = [], {}, []
    for sid, days in SERIES:
        if sid in src or sid in missing:
            continue
        df = S.fred(sid, days=days, use_repo=False)
        if df.empty:
            missing.append(sid)
            print(f"✗ {sid}: 모든 출처 실패")
            continue
        src[sid] = S.FRED_SRC.get(sid, "")
        frames.append(df.assign(id=sid)[["id", "date", "value"]])
        print(f"✓ {sid}: {len(df)}개, 마지막 {df['date'].iloc[-1]:%Y-%m-%d} = {df['value'].iloc[-1]} ({src[sid]})")
    if not frames:
        print("하나도 못 받았어요. 기존 파일을 그대로 둬요.")
        return 1
    new = pd.concat(frames)
    old = S.repo_fred()
    for sid in list(missing):              # 이번에 못 받은 시리즈는 지난 파일 값이 아직 새것이면 남겨 둬요
        keep = old[old["id"] == sid]
        if S.fresh(keep):
            new = pd.concat([new, keep])
            src[sid] = S.repo_meta().get("src", {}).get(sid, "").replace(" (지난 실행 값)", "") + " (지난 실행 값)"
            print(f"… {sid}: 지난 실행 값 유지(마지막 {keep['date'].max():%Y-%m-%d})")
    new["date"] = new["date"].dt.strftime("%Y-%m-%d")
    S.DATA_DIR.mkdir(exist_ok=True)
    new.to_csv(S.DATA_DIR / "fred.csv", index=False)
    meta = {"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "src": src, "missing": missing}
    (S.DATA_DIR / "fred_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(f"저장: {len(src)}개 시리즈, 실패 {missing or '없음'}")
    return 0


if __name__ == "__main__":
    if "--probe" in sys.argv:
        probe()
        sys.exit(0)
    sys.exit(main())
