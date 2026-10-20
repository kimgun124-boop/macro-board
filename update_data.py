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

PROBE = {
    "FRED csv": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=UNRATE",
    "BLS API v1": "https://api.bls.gov/publicAPI/v1/timeseries/data/LNS14000000",
    "Fed G.17(산업생산)": "https://www.federalreserve.gov/releases/g17/ipdisk/ip_sa.txt",
    "Census(소매판매)": "https://api.census.gov/data/timeseries/eits/marts?get=cell_value,time_slot_id&category_code=44X72"
                       "&data_type_code=SM&seasonally_adj=yes&time=from+2025",
    "BEA NIPA(월)": "https://apps.bea.gov/national/Release/TXT/NipaDataM.txt",
    "노동부(실업수당)": "https://oui.doleta.gov/unemploy/csv/ar539.csv",
    "DBnomics": "https://api.db.nomics.world/v22/series/BLS/ln/LNS14000000?observations=1",
    "뉴욕연은": "https://markets.newyorkfed.org/api/rates/unsecured/effr/last/5.json",
    "프레디맥": "https://www.freddiemac.com/pmms/docs/PMMS_history.csv",
    "미시간대": "https://www.sca.isr.umich.edu/files/tbmics.csv",
}


def probe() -> None:
    for name, url in PROBE.items():
        try:
            r = S.session.get(url, timeout=20, stream=True)
            head = next(r.iter_content(160), b"").decode("utf-8", "replace").replace("\n", " ")[:120]
            print(f"{name:20s} {r.status_code}  {head}")
            r.close()
        except Exception as e:
            print(f"{name:20s} 실패  {e.__class__.__name__}: {str(e)[:100]}")


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
    if not old.empty:                      # 이번에 못 받은 시리즈는 지난 파일 값을 남겨 둬요
        new = pd.concat([new, old[old["id"].isin(missing)]])
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
