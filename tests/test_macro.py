from datetime import datetime, timezone

import pandas as pd

import ai
import econ
import issues
import macro
import sources
import trend


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
    assert len(at.tabs) == 11


def test_trend_stages():
    up = pd.DataFrame({"date": pd.bdate_range("2025-01-01", periods=260), "close": [100 + i for i in range(260)]})
    t = trend.metrics(up)
    assert t["stage"] == "상승 추세" and t["above"][200]
    down = up.assign(close=up["close"][::-1].values)
    assert trend.metrics(down)["stage"] == "하락 추세"
    snap = macro.snapshot()
    v = trend.market_view(snap)
    assert v["verdict"] and v["lines"]


def test_issues_mock():
    snap = macro.snapshot()
    out = issues.build(snap)
    oil = next(x for x in out if x["key"] == "oil")
    assert oil["news"] and oil["links"]
    assert any(n.get("major") for n in oil["news"])


def test_econ():
    df = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=30, freq="MS"), "value": [100 * 1.01 ** i for i in range(30)]})
    y = econ.transform(df, "yoy")
    assert abs(y["value"].iloc[-1] - (1.01 ** 12 - 1) * 100) < 1e-6
    assert econ._rule_date(pd.Timestamp("2026-09-01"), "jobs") == pd.Timestamp("2026-10-02")
    snap = macro.snapshot()
    e = next(x for x in __import__("config").ECON if x["id"] == "CPIAUCSL")
    rel = econ.releases(e, econ.fetch_series()["CPIAUCSL"], snap["px"])
    assert rel["rows"] and "^GSPC" in rel["rows"][0]["react"]
    assert econ.reaction_stats(rel["rows"])


def test_ai_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    snap = macro.snapshot()
    ctx = ai.market_context(snap, trend.market_view(snap), issues.build(snap), trend.rate_regime(snap["sm"]))
    assert "S&P 500" in ctx
    assert ai.ask(ctx, "test")["error"]


def test_reports(tmp_path, monkeypatch):
    import report
    monkeypatch.setattr(report, "DIR", tmp_path)
    (tmp_path / "2026-10-20-0752.md").write_text("# 제목\n> 요약\n\n본문", encoding="utf-8")
    (tmp_path / "2026-10-20-1952.md").write_text("# 밤\n> 밤 요약\n\n본문", encoding="utf-8")
    r = report.all_reports()
    assert r[0]["title"] == "밤" and r[0]["lead"] == "밤 요약" and r[0]["when"] == "2026-10-20 19:52"
    assert report.body(r[0]["text"]).startswith(">")


def test_corr_and_flows():
    import corr, flows
    px = corr.fetch_long()
    t = corr.table(px)
    assert t and t[0]["cells"]["1년"]["corr"] is not None
    assert t[0]["cells"]["10년"] is not None
    assert not corr.recent_days(px).empty
    ov = flows.fetch_market_overview()
    fl = flows.fetch_investor_flows(ov)
    assert ov["코스피"]["deal"] and not fl["코스닥"].empty


def test_fallback_parsers():
    df = sources.parse_dbnomics({"series": {"docs": [{"period": ["2026-08", "2026-09"], "value": [320.1, 321.0]}]}})
    assert df["value"].tolist() == [320.1, 321.0]
    csv = "Date,1 Mo,2 Yr,10 Yr\n10/17/2026,4.1,3.5,4.0\n10/16/2026,4.1,3.6,4.1\n"
    assert sources.parse_treasury_csv(csv, "10 Yr")["value"].tolist() == [4.0, 4.1]


def test_alloc():
    import alloc
    import flows
    assert alloc.p_rate(5.15) == 0 and alloc.p_rate(4.2) == 15
    assert alloc.band(88)["name"] == "공격" and alloc.band(40)["name"] == "축소" and alloc.band(10)["name"] == "방어"
    snap = macro.snapshot()
    fl = flows.fetch_investor_flows(flows.fetch_market_overview())
    a = alloc.build(snap, fl)
    assert 0 <= a["score"] <= 100 and len(a["signals"]) == 12
    assert a["split"]["kr"] + a["split"]["us"] == 100
    # 10년물 5% 이상이면 '축소' 위로 못 가요
    hot = {**snap, "fred": {**snap["fred"], "DGS10": {**snap["fred"]["DGS10"], "last": 5.15}}}
    assert alloc.build(hot, fl)["score"] <= 49
    h = alloc.history(snap)
    assert not h.empty and h["score"].between(0, 100).all()
    assert alloc.band_stats(h)


def test_digest_and_treasury():
    import digest
    assert digest.topic_of("Oil wavers near five-month high as Iran's Hormuz threats vie with flows") == "iran"
    assert digest.gist("Canada's inflation ticks up to 3.1% due to high oil prices") == ["캐나다", "물가", "유가", "상승"]
    assert "5개월 고점" in digest.gist("Brent crude holds near five-month high")
    assert digest.gist("코스피 5700선 탈환") == []
    d = digest.build(macro.snapshot())
    assert d["top"] and d["topics"]
    g = digest.build(macro.snapshot(), only=digest.GEO_KEYS)
    assert all(n["topic"] in digest.GEO_KEYS for n in g["news"]) and g["lines"]
    real = sources.parse_treasury_csv("Date,5 YR,7 YR,10 YR,20 YR,30 YR\n10/16/2026,1.50,1.70,1.92,2.10,2.20\n", "10 Yr")
    assert real["value"].iloc[0] == 1.92
    import report
    assert report.section("# t\n## 뉴스 해석\n| a |\n## 다음\nx", "뉴스 해석") == "| a |"


def test_portfolio_events_analog():
    import alloc
    import analog
    import corr
    import events
    import flows
    import portfolio
    rows, cash, bad = portfolio.parse("삼성전자 30\n000660 20\nNVDA 10\n현금 40\n???")
    assert [r["code"] for r in rows] == ["005930", "000660", "NVDA"] and cash == 40 and bad == ["???"]
    assert portfolio.decode(portfolio.encode("삼성전자 30\n현금 70")) == "삼성전자 30\n현금 70"
    snap = macro.snapshot()
    px = {r["code"]: (sources.naver(r["code"]) if r["kr"] else sources.yahoo([r["code"]]).get(r["code"])) for r in rows}
    a = alloc.build(snap, flows.fetch_investor_flows(flows.fetch_market_overview()))
    c = portfolio.check(rows, cash, px, snap, a)
    assert c["equity"] == 60 and all(i["ok"] for i in c["items"]) and portfolio.notes(c)
    ev = events.calendar(pd.Timestamp("2026-10-20"), 35)
    assert ev[0]["name"] == "FOMC 금리 결정" and ev[0]["dday"] == 9
    assert any(e["kind"] == "kr_opt" and e["date"] == pd.Timestamp("2026-11-12") for e in ev)
    res = analog.all_for(corr.fetch_long())
    assert res["코스피"] and res["코스피"]["n"] >= 0
    ch = alloc.changes(alloc.history(snap))
    assert ch and "d5" in ch
