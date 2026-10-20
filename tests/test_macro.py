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


def test_mixed_date_units():
    """야후(ns)·네이버(us)처럼 날짜 단위가 달라도 날짜 맞춰 붙이기(merge_asof)가 멈추지 않아야 해요(배포에서 난 MergeError)."""
    import corr
    import portfolio
    d = pd.bdate_range("2025-01-01", periods=300)
    kr = pd.DataFrame({"date": d.as_unit("us"), "close": [100 + (i % 7) for i in range(300)]})
    us = pd.DataFrame({"date": d.as_unit("ns"), "close": [4 + (i % 5) / 100 for i in range(300)]})
    assert portfolio._series(kr).index.dtype == "datetime64[ns]"
    ret = kr.set_index(pd.DatetimeIndex(kr["date"]))["close"].pct_change() * 100
    beta, n = portfolio._beta(ret, us.set_index("date")["close"].diff() * 100, kr=True)
    assert n > 60
    assert not corr.align(us, kr, lag=True).empty
    assert sources.parse_fchart('<item data="20260102|1|2|1|1.5|10" />')["date"].dtype == "datetime64[ns]"


def test_tab_error_stays_in_tab(monkeypatch):
    """탭 하나가 실패해도 앱 전체는 그려져야 해요."""
    import view
    from streamlit.testing.v1 import AppTest

    def boom(snap):
        raise ValueError("test")
    monkeypatch.setattr(view, "tab_account", boom)
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    assert len(at.tabs) == 11
    assert any("내 계좌" in e.value for e in at.error)


def test_repo_fred_file(tmp_path, monkeypatch):
    """깃허브가 받아 둔 data/fred.csv를 먼저 읽고, 오래됐으면 실시간 출처 → 그래도 없으면 오래된 파일."""
    import json as _json
    monkeypatch.setattr(sources, "MOCK", False)
    monkeypatch.setattr(sources, "DATA_DIR", tmp_path)
    for fn in ("_fredgraph", "_fred_api", "_dbnomics", "_treasury", "_origin", "_yahoo_rate"):
        monkeypatch.setattr(sources, fn, lambda s, start: sources.EMPTY_FRED)
    today = pd.Timestamp.today().normalize()
    pd.DataFrame({"id": ["UNRATE"] * 3, "date": [f"{d:%Y-%m-%d}" for d in pd.date_range(end=today, periods=3, freq="MS")],
                  "value": [4.1, 4.2, 4.3]}).to_csv(tmp_path / "fred.csv", index=False)
    now = pd.Timestamp.now(tz="UTC")
    (tmp_path / "fred_meta.json").write_text(_json.dumps({"at": f"{now:%Y-%m-%dT%H:%M:%SZ}", "src": {"UNRATE": "FRED"}}))
    df = sources.fred("UNRATE", 400)
    assert list(df["value"]) == [4.1, 4.2, 4.3] and df["date"].dtype == "datetime64[ns]"
    assert sources.FRED_SRC["UNRATE"].startswith("저장소 파일") and "FRED" in sources.FRED_SRC["UNRATE"]
    old = now - pd.Timedelta(days=10)
    (tmp_path / "fred_meta.json").write_text(_json.dumps({"at": f"{old:%Y-%m-%dT%H:%M:%SZ}", "src": {}}))
    assert len(sources.fred("UNRATE", 400)) == 3 and "오래된" in sources.FRED_SRC["UNRATE"]
    assert sources.fred("CPIAUCSL", 400).empty


def test_origin_parsers():
    """FRED가 막힐 때 쓰는 원래 발표 기관 파일들(BLS·BEA·연준 G.17)을 읽는지, 오래된 출처는 거르는지."""
    js = {"status": "REQUEST_SUCCEEDED", "Results": {"series": [{"seriesID": "LNS14000000", "data": [
        {"year": "2026", "period": "M09", "value": "4.4"}, {"year": "2026", "period": "M08", "value": "4.3"},
        {"year": "2025", "period": "M13", "value": "4.1"}, {"year": "2025", "period": "M10", "value": "-"}]}]}}
    b = sources.parse_bls(js)
    assert list(b["value"]) == [4.3, 4.4] and b["date"].iloc[-1] == pd.Timestamp("2026-09-01")
    text = '%SeriesCode,Period,Value\nDPCCRG,2026M07,"127.512"\nDPCCRG,2026M08,"127.861"\nDPCCRGX,2026M08,"1"\nA191RL,2026Q2,"2.1"\n'
    m = sources.parse_bea(text, "DPCCRG")
    assert list(m["value"]) == [127.512, 127.861] and m["date"].iloc[-1] == pd.Timestamp("2026-08-01")
    q = sources.parse_bea(text, "A191RL")
    assert q["date"].iloc[0] == pd.Timestamp("2026-04-01") and q["value"].iloc[0] == 2.1
    g = sources.parse_g17('"B50001: Total index"\n"B50001"   2026   103.1  103.4  103.0\n"B50002"   2026   1 2 3\n')
    assert list(g["value"]) == [103.1, 103.4, 103.0] and g["date"].iloc[-1] == pd.Timestamp("2026-03-01")
    assert not sources.fresh(pd.DataFrame({"date": [pd.Timestamp("2025-01-01")], "value": [1.0]}))
    assert sources.fresh(pd.DataFrame({"date": [pd.Timestamp.today().normalize()], "value": [1.0]}))


def test_dol_claims_xml():
    xml = ('<r539cyNational rundate="10/20/2026"><week><weekEnded>10/04/2026</weekEnded><InitialClaims><NSA>206,295</NSA>'
           '<SA>226,000</SA></InitialClaims></week><week><weekEnded>10/11/2026</weekEnded><InitialClaims><NSA>&#160;</NSA>'
           '<SA>&#160;</SA></InitialClaims></week></r539cyNational>')
    d = sources.parse_dol(xml)
    assert list(d["value"]) == [226000] and d["date"].iloc[0] == pd.Timestamp("2026-10-04")
