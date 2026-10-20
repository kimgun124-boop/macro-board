"""차트(plotly). 캔들 + 이동평균(10·20·50·200일) + 거래량. 한국식 색: 상승 빨강, 하락 파랑."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import theme

UP, DOWN = "#D6333B", "#1F66C9"
MA_SET = ((10, "10일"), (20, "20일"), (50, "50일"), (200, "200일"))
MA_COLORS = ("#E0672B", "#2E9D5B", "#7A4FD1", "#8A96A0")
PERIODS = {"3개월": 63, "6개월": 126, "1년": 250, "2년": 500}
FONT = dict(family=theme.CHART_FONT, size=12)


def _prep(df: pd.DataFrame, n: int) -> pd.DataFrame:
    b = df.copy().reset_index(drop=True)
    for k, _ in MA_SET:
        b[f"ma{k}"] = b["close"].rolling(k).mean()
    b = b.tail(n)
    b["x"] = pd.to_datetime(b["date"]).dt.strftime("%Y-%m-%d")
    return b


def candle(df: pd.DataFrame, n: int = 126, show_vol: bool = True, height: int = 560, fmt: str = ",.2f") -> go.Figure:
    b = _prep(df, n)
    has_vol = show_vol and "volume" in b and b["volume"].fillna(0).sum() > 0
    fig = make_subplots(rows=2 if has_vol else 1, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                        row_heights=[0.78, 0.22] if has_vol else [1.0])
    fig.add_trace(go.Candlestick(
        x=b["x"], open=b["open"], high=b["high"], low=b["low"], close=b["close"], name="봉", showlegend=False,
        increasing=dict(line=dict(color=UP, width=1), fillcolor=UP),
        decreasing=dict(line=dict(color=DOWN, width=1), fillcolor=DOWN)), row=1, col=1)
    for (k, lab), c in zip(MA_SET, MA_COLORS):
        fig.add_trace(go.Scatter(x=b["x"], y=b[f"ma{k}"], name=lab, mode="lines", line=dict(color=c, width=1.3),
                                 hovertemplate=f"{lab} %{{y:{fmt}}}<extra></extra>"), row=1, col=1)
    hi = float(df["close"].tail(250).max())
    fig.add_hline(y=hi, line=dict(color="#F2B134", width=1.2, dash="dash"), row=1, col=1,
                  annotation_text=f"52주 최고(종가) {hi:{fmt}}", annotation_position="top left",
                  annotation_font=dict(size=11, color="#B7861D"))
    if has_vol:
        colors = [UP if c >= o else DOWN for o, c in zip(b["open"], b["close"])]
        fig.add_trace(go.Bar(x=b["x"], y=b["volume"], marker_color=colors, opacity=0.55, name="거래량", showlegend=False,
                             hovertemplate="거래량 %{y:,.0f}<extra></extra>"), row=2, col=1)
        fig.update_yaxes(tickformat="~s", row=2, col=1)
    fig.update_yaxes(side="right", gridcolor="#EEF1F3", zeroline=False)
    fig.update_yaxes(tickformat=fmt, row=1, col=1)
    fig.update_xaxes(type="category", nticks=8, showgrid=False, rangeslider_visible=False, tickangle=0)
    fig.update_layout(height=height, margin=dict(l=4, r=4, t=30, b=6), hovermode="x unified", dragmode="pan",
                      plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF", font=FONT,
                      legend=dict(orientation="h", y=1.06, x=0, font=dict(size=12)))
    fig.update_xaxes(showspikes=True, spikemode="across", spikethickness=1)
    return theme.style_fig(fig)


def mini(df: pd.DataFrame, n: int = 126, height: int = 210) -> go.Figure:
    """보드용 작은 차트: 캔들 + 20·50·200일선."""
    b = _prep(df, n)
    fig = go.Figure(go.Candlestick(
        x=b["x"], open=b["open"], high=b["high"], low=b["low"], close=b["close"], showlegend=False,
        increasing=dict(line=dict(color=UP, width=1), fillcolor=UP),
        decreasing=dict(line=dict(color=DOWN, width=1), fillcolor=DOWN), hoverinfo="skip"))
    for (k, lab), c in zip(MA_SET, MA_COLORS):
        if k == 10:
            continue
        fig.add_trace(go.Scatter(x=b["x"], y=b[f"ma{k}"], mode="lines", line=dict(color=c, width=1.1),
                                 showlegend=False, hoverinfo="skip"))
    fig.update_xaxes(type="category", visible=False, rangeslider_visible=False)
    fig.update_yaxes(side="right", gridcolor="#F1F4F6", zeroline=False, tickfont=dict(size=10), nticks=4)
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=4, b=0), plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
                      font=FONT, dragmode=False)
    return theme.style_fig(fig)


def line(df: pd.DataFrame, title: str = "", color: str = "#2C5282", height: int = 260, zero: bool = False) -> go.Figure:
    """경제지표용 선 차트(date, value)."""
    fig = go.Figure(go.Scatter(x=df["date"], y=df["value"], mode="lines", line=dict(color=color, width=1.8),
                               hovertemplate="%{x|%Y-%m-%d} %{y:,.2f}<extra></extra>"))
    if zero:
        fig.add_hline(y=0, line=dict(color="#9AA5AE", width=1))
    fig.update_yaxes(side="right", gridcolor="#EEF1F3", zeroline=False)
    fig.update_xaxes(showgrid=False)
    fig.update_layout(title=dict(text=title, font=dict(size=13)) if title else None, height=height,
                      margin=dict(l=4, r=4, t=30 if title else 6, b=4), plot_bgcolor="#FFFFFF",
                      paper_bgcolor="#FFFFFF", font=FONT, hovermode="x")
    return theme.style_fig(fig)


def gauge(score: float, bands: list, height: int = 230) -> go.Figure:
    """비중 점수 반원 게이지. bands = alloc.BANDS(하한, 이름, 비중, 색, 설명)."""
    lows = sorted(b[0] for b in bands)
    steps = [dict(range=[lo, (lows + [100])[i + 1]], color=next(b[3] for b in bands if b[0] == lo))
             for i, lo in enumerate(lows)]
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=round(score), number=dict(suffix="점", font=dict(size=40, color="#111827")),
        gauge=dict(axis=dict(range=[0, 100], tickvals=lows[1:] + [100], tickfont=dict(size=11)),
                   bar=dict(color="rgba(17,24,39,.85)", thickness=0.22),
                   steps=[dict(s, color=s["color"] + "55") for s in steps], borderwidth=0,
                   threshold=dict(line=dict(color="#111827", width=3), thickness=0.9, value=score))))
    fig.update_layout(height=height, margin=dict(l=18, r=18, t=10, b=0), paper_bgcolor="#FFFFFF", font=FONT)
    return theme.style_fig(fig)


def score_history(h: pd.DataFrame, bands: list, height: int = 430) -> go.Figure:
    """위: 비중 점수(구간 색 띠) · 아래: 코스피·나스닥(시작=100)."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06, row_heights=[0.55, 0.45])
    lows = sorted(b[0] for b in bands)
    for i, lo in enumerate(lows):
        b = next(x for x in bands if x[0] == lo)
        fig.add_hrect(y0=lo, y1=(lows + [100])[i + 1], fillcolor=b[3], opacity=0.08, line_width=0, row=1, col=1)
        fig.add_annotation(x=1, xref="x domain", y=(lo + (lows + [100])[i + 1]) / 2, yref="y", text=f"{b[1]} {b[2]}",
                           showarrow=False, xanchor="right", font=dict(size=10, color=b[3]))
    fig.add_trace(go.Scatter(x=h["date"], y=h["score"], mode="lines", name="비중 점수", line=dict(color="#5B47F5", width=2),
                             hovertemplate="%{x|%Y-%m-%d} 점수 %{y:.0f}<extra></extra>"), row=1, col=1)
    for k, nm, col in (("kospi", "코스피", UP), ("nasdaq", "나스닥", "#111827")):
        if k in h and h[k].notna().any():
            s = h[k] / h[k].dropna().iloc[0] * 100
            fig.add_trace(go.Scatter(x=h["date"], y=s, mode="lines", name=nm, line=dict(color=col, width=1.5),
                                     hovertemplate=f"{nm} %{{y:.1f}}<extra></extra>"), row=2, col=1)
    fig.update_yaxes(range=[0, 100], row=1, col=1, side="right", gridcolor="#EEF1F3")
    fig.update_yaxes(row=2, col=1, side="right", gridcolor="#EEF1F3", title=dict(text="시작=100", font=dict(size=10)))
    fig.update_xaxes(showgrid=False)
    fig.update_layout(height=height, margin=dict(l=4, r=4, t=10, b=6), hovermode="x unified", plot_bgcolor="#FFFFFF",
                      paper_bgcolor="#FFFFFF", font=FONT, legend=dict(orientation="h", y=1.04, x=0))
    return theme.style_fig(fig)


def group_bars(groups: dict, height: int = 200) -> go.Figure:
    """묶음별 점수율(받은 점수 / 만점)."""
    names = list(groups)
    got = [(groups[n][0] or 0) / groups[n][1] * 100 if groups[n][1] and groups[n][0] is not None else 0 for n in names]
    cols = [UP if v >= 65 else "#B7791F" if v >= 45 else DOWN for v in got]
    txt = [f"{groups[n][0]:.0f}/{groups[n][1]}" if groups[n][0] is not None else "—" for n in names]
    fig = go.Figure(go.Bar(x=got, y=names, orientation="h", marker_color=cols, text=txt, textposition="outside",
                           hovertemplate="%{y} %{x:.0f}%<extra></extra>"))
    fig.update_xaxes(range=[0, 128], visible=False)
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(height=height, margin=dict(l=4, r=4, t=4, b=4), plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
                      font=FONT, bargap=0.35)
    return theme.style_fig(fig)
