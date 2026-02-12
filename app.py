import streamlit as st
import yfinance as yf
import akshare as ak
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# 高亮函数
def highlight_change(val):
    if pd.isna(val):
        return ''
    try:
        val = float(val)
        if val > 0:
            return 'color: green; font-weight: bold'
        elif val < 0:
            return 'color: red; font-weight: bold'
    except:
        pass
    return ''

st.set_page_config(layout="wide", page_title="资源 & 轮动投资仪表盘")
st.title("🛢️ 资源型 & 板块轮动实时仪表盘（全球 + A股）")

# 侧边栏
period = st.sidebar.selectbox("选择时间周期", ["1d", "5d", "1mo", "3mo", "ytd"], index=1)

# ----------------- 1. 全球大宗商品 -----------------
st.header("🌍 全球大宗商品价格与变化（实时优先，失败回退最近交易日）")
com_tickers = {
    "原油 CL=F": "CL=F",
    "黄金 GC=F": "GC=F",
    "铜 HG=F": "HG=F",
    "白银 SI=F": "SI=F",
    "天然气 NG=F": "NG=F",
    "锂 ETF LIT": "LIT",
    "稀土 ETF REMX": "REMX",
    "商品指数 DBC": "DBC",
}

com_data = []
data_date = "实时"
for name, ticker in com_tickers.items():
    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info
        price = info.get('regularMarketPrice') or info.get('previousClose')
        change = info.get('regularMarketChangePercent')
        if price is None or change is None:  # 实时失败，回退历史
            raise Exception("实时数据缺失")
        com_data.append({"商品": name, "最新价": round(price, 2), "涨跌幅%": round(change, 2) if change else 0})
        data_date = "实时"
    except:
        try:
            hist = yf.download(ticker, period="5d", progress=False)
            if not hist.empty:
                latest = hist.iloc[-1]
                prev = hist.iloc[-2] if len(hist) > 1 else latest
                price = latest['Close']
                change = (price / prev['Close'] - 1) * 100 if prev['Close'] != 0 else 0
                data_date = hist.index[-1].strftime("%Y-%m-%d")
            else:
                price = change = 0
            com_data.append({"商品": name, "最新价": round(price, 2), "涨跌幅%": round(change, 2)})
        except:
            com_data.append({"商品": name, "最新价": "N/A", "涨跌幅%": 0})

com_df = pd.DataFrame(com_data)
com_df["涨跌幅%"] = pd.to_numeric(com_df["涨跌幅%"], errors='coerce').fillna(0)
com_df = com_df.sort_values("涨跌幅%", ascending=False)
styled_com = com_df.style.map(highlight_change, subset=["涨跌幅%"])
st.dataframe(styled_com, use_container_width=True)
st.caption(f"数据日期：{data_date}（实时失败时自动回退最近交易日）")

# 商品走势图（强制显示历史）
selected_com = st.selectbox("选择商品查看走势", list(com_tickers.keys()))
selected_ticker = com_tickers[selected_com]
hist_com = yf.download(selected_ticker, period="6mo", progress=False)
if not hist_com.empty and 'Close' in hist_com.columns:
    fig_com = px.line(hist_com, x=hist_com.index, y="Close", title=f"{selected_com} 6个月走势（最新至 {hist_com.index[-1].strftime('%Y-%m-%d')})")
    st.plotly_chart(fig_com, use_container_width=True)
else:
    st.warning(f"{selected_com} 暂无历史数据")

# ----------------- 2. 板块轮动 -----------------
st.header("🔄 全球板块轮动热度（资源型重点监控，失败回退最近交易日）")
sector_tickers = {
    "材料 XLB（资源）": "XLB",
    "能源 XLE（资源）": "XLE",
    "金融 XLF": "XLF",
    "科技 XLK": "XLK",
    "消费非必需 XLY": "XLY",
    "工业 XLI": "XLI",
    "医疗 XLV": "XLV",
    "消费必需 XLP": "XLP",
    "公用 XLU": "XLU",
    "地产 XLRE": "XLRE",
    "通信 XLC": "XLC",
}

sector_data = []
sector_date = "实时"
try:
    spy_hist = yf.download("SPY", period=period, progress=False)
    if spy_hist.empty:
        raise Exception("SPY空")
    spy_perf = (spy_hist['Close'][-1] / spy_hist['Close'][0] - 1) * 100

    for name, ticker in sector_tickers.items():
        hist = yf.download(ticker, period=period, progress=False)
        if not hist.empty and len(hist) > 1:
            perf = (hist['Close'][-1] / hist['Close'][0] - 1) * 100
        else:
            perf = 0
        relative = perf - spy_perf
        sector_data.append({"板块": name, "周期涨跌%": round(perf, 2), "相对大盘%": round(relative, 2)})
    sector_date = spy_hist.index[-1].strftime("%Y-%m-%d")
except:
    # 回退到最近5个交易日
    try:
        spy_hist = yf.download("SPY", period="10d", progress=False)
        if not spy_hist.empty:
            spy_perf = (spy_hist['Close'][-1] / spy_hist['Close'][-2] - 1) * 100 if len(spy_hist) > 1 else 0
            sector_date = spy_hist.index[-1].strftime("%Y-%m-%d（回退）")
            for name, ticker in sector_tickers.items():
                hist = yf.download(ticker, period="10d", progress=False)
                if not hist.empty and len(hist) > 1:
                    perf = (hist['Close'][-1] / hist['Close'][-2] - 1) * 100
                else:
                    perf = 0
                relative = perf - spy_perf
                sector_data.append({"板块": name, "周期涨跌%": round(perf, 2), "相对大盘%": round(relative, 2)})
    except:
        st.warning("板块数据完全加载失败，使用空表占位")
        sector_date = "无"

sector_df = pd.DataFrame(sector_data) if sector_data else pd.DataFrame(columns=["板块", "周期涨跌%", "相对大盘%"])
sector_df["周期涨跌%"] = pd.to_numeric(sector_df["周期涨跌%"], errors='coerce').fillna(0)
sector_df["相对大盘%"] = pd.to_numeric(sector_df["相对大盘%"], errors='coerce').fillna(0)
sector_df = sector_df.sort_values("周期涨跌%", ascending=False)
styled_sector = sector_df.style.map(highlight_change, subset=["周期涨跌%", "相对大盘%"])
st.dataframe(styled_sector, use_container_width=True)
st.caption(f"轮动数据日期：{sector_date}")

if not sector_df.empty:
    fig_bar = px.bar(sector_df, x="板块", y="周期涨跌%", color="相对大盘%", title="板块轮动排名")
    st.plotly_chart(fig_bar, use_container_width=True)

# ----------------- 3. 中国资源股 -----------------
st.header("🇨🇳 中国资源股监控（钨/稀土龙头，失败回退最近交易日）")
china_tickers = {
    "中钨高新": "000657.SZ",
    "厦门钨业": "600549.SH",
    "北方稀土": "600111.SH",
    "盛和资源": "600392.SH",
    "广晟有色": "600259.SH",
    "中国稀土": "000831.SZ",
}

china_data = []
china_date = "今日"
for name, code in china_tickers.items():
    try:
        df = ak.stock_zh_a_hist(symbol=code, adjust="qfq", timeout=15).tail(10)  # 多取几天防休市
        if not df.empty:
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest
            day_change = (latest['收盘'] / prev['收盘'] - 1) *
