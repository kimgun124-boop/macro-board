from datetime import datetime, timezone

import pandas as pd

import macro
import sources


def test_verify():
    p = {"last": 100.0, "date": pd.Timestamp("2026-10-19")}
    assert macro.verify(p, {"close": 100.1, "date": pd.Timestamp("2026-10-19")})[0] == "교차확인"
    assert macro.verify(p, {"close": 101.0, "date": pd.Timestamp("2026-10-19")})[0] == "상충"
    assert macro.verify(p, {"close": 100.0, "date": pd.Timestamp("2026-10-18")})[0] == "단일출처"
    assert macro.verify(p, None)[0] == "단일출처"
    assert macro.verify(None, None)[0] == "없음"


def test_classify():
    assert macro.classify("S&P 500 rises 0.4% as chip stocks rebound") == "사실"
    assert macro.classify("Oil could hit $120, analysts say") == "의견"
    assert macro.classify("Houthis claim attack on tanker") == "주장"
    assert macro.classify("코스피 하락 전망") == "의견"


def test_cluster_cross_check():
    now = datetime.now(timezone.utc)
    items = [
        {"title": "S&P 500 rises 0.4% as chip stocks rebound", "source": "Reuters", "url": "a", "when": now},
        {"title": "S&P 500 gains 0.4% as chipmakers rebound", "source": "AP News", "url": "b", "when": now},
        {"title": "Fed holds rates steady at 4.25%", "source": "CNBC", "url": "c", "when": now},
    ]
    out = macro.cluster(items)
    assert out[0]["status"] == "교차확인" and out[0]["n"] == 2
    assert out[1]["status"] == "단일출처"


def test_parsers():
    assert sources.parse_stooq("Symbol,Date,Time,Open,High,Low,Close\n^SPX,2026-10-19,22:00:00,1,2,0.5,6700.5\n")["close"] == 6700.5
    fred = sources.parse_fred_csv("observation_date,DGS10\n2026-10-16,4.01\n2026-10-17,.\n")
    assert len(fred) == 1 and fred["value"].iloc[0] == 4.01
    df = sources.parse_fchart('<chartdata name="삼성전자"><item data="20261017|1|2|0.5|98000|10" /><item data="20261020|1|2|0.5|99000|10" /></chartdata>')
    assert df["close"].tolist() == [98000, 99000]
    rss = '<rss><channel><item><title>Oil rises - Reuters</title><link>u</link><source>Reuters</source><pubDate>Mon, 20 Oct 2026 01:00:00 GMT</pubDate></item></channel></rss>'
    assert macro.parse_rss(rss)[0]["title"] == "Oil rises"


def test_snapshot_mock():
    snap = macro.snapshot()
    assert snap["sm"]["^GSPC"]["last"] > 0
    assert "fred:DGS2" in snap["sm"]
    assert snap["ver"]["^KS11"][0] in ("교차확인", "상충", "단일출처")
    assert macro.facts(snap)


def test_app_runs():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    assert not at.exception
    assert len(at.tabs) == 3
