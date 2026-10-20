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

CENSUS = "programCode=MARTS&startYear=2024&endYear=2026&dataType=SM&geoLevel=US&adjusted=1&notAdjusted=0&errorData=0"
PROBE = {
    "Census dbsearch": f"https://www.census.gov/econ/currentdata/dbsearch?{CENSUS}&categories[]=44X72",
    "Census export2": f"https://www.census.gov/econ/currentdata/export/csv?{CENSUS}&timeSlotType=12&categories=44X72",
    "Census export3": f"https://www.census.gov/econ/currentdata/export/csv?{CENSUS}&timeSlotType=12&categories%5B%5D=44X72",
    "Census api": "https://api.census.gov/data/timeseries/eits/marts?get=cell_value,time_slot_id,category_code,data_type_code"
                  "&time=2026&category_code=44X72&data_type_code=SM&seasonally_adj=yes",
    "Census retail": "https://www.census.gov/retail/index.html",
}


def probe() -> None:
    import re
    for name, url in PROBE.items():
        try:
            r = S.session.get(url, timeout=30)
            text = r.text
            if name == "Census retail":
                print(f"{name}: {r.status_code}", sorted(set(re.findall(r'href="([^"]+\.(?:xlsx?|csv|txt))"', text)))[:40])
                continue
            if name == "Census dbsearch":
                i = text.find("<table")
                print(f"{name}: {r.status_code} forms={re.findall(r'<a[^>]+export[^>]*>', text)[:5]} table={text[i:i+900]!r}")
                continue
            print(f"{name:20s} {r.status_code}  {text[:500]!r}")
        except Exception as e:
            print(f"{name:20s} 실패  {e.__class__.__name__}: {str(e)[:100]}")
    for ft in ("xml", "xls"):
        try:
            r = S.session.post("https://oui.doleta.gov/unemploy/wkclaims/report.asp", timeout=60,
                               data={"level": "us", "final_yr": "2027", "strtdate": "2025", "enddate": "2026",
                                     "filetype": ft, "submit": "Submit"})
            print(f"노동부 {ft}: {r.status_code} {r.headers.get('content-type')} {r.text[:900]!r} … {r.text[-600:]!r}")
        except Exception as e:
            print(f"노동부 {ft} 실패 {e}")


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
