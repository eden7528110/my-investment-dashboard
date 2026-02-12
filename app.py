import streamlit as st
import yfinance as yf
import akshare as ak
import pandas as pd
import plotly.express as px
from datetime import datetime

# 高亮函数：正涨绿色加粗，负涨红色加粗
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

# 侧边栏设置
period = st.sidebar.selectbox("选择时间周期", ["1d", "5d", "1mo", "3mo", "ytd"], index=1)

# ----------------- 1. 全球大宗商品 -----------------
st.header("🌍 全球大宗商品价格与变化")
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
for name, ticker in com_tickers.items():
    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info
        price = info.get('regularMarketPrice') or info.get('previousClose') or 0
        change = info.get('regularMarketChangePercent') or 0
        com_data.append({"商品": name, "最新价": round(price, 2), "涨跌幅%": round(change, 2)})
    except:
        com_data.append({"商品": name, "最新价": "加载失败", "涨跌幅%": 0})

com_df = pd.DataFrame(com_data).sort_values("涨跌幅%", ascending=False, key=lambda x: pd.to_numeric(x, errors='coerce'))
styled_com = com_df.style.map(highlight_change, subset=["涨跌幅%"])
st.dataframe(styled_com, use_container_width=True)

# 商品走势图（加空保护）
selected_com = st.selectbox("选择商品查看走势", list(com_tickers.keys()))
selected_ticker = com_tickers[selected_com]
try:
    hist_com = yf.download(selected_ticker, period="6mo", progress=False)
    if not hist_com.empty and 'Close' in hist_com.columns:
        fig_com = px.line(hist_com, x=hist_com.index, y="Close", title=f"{selected_com} 6个月走势")
        st.plotly_chart(fig_com, use_container_width=True)
    else:
        st.warning(f"{selected_com} 暂无历史数据（可能休市、网络波动或合约问题），请稍后重试或换个商品")
except:
    st.warning(f"{selected_com} 数据加载失败，请刷新页面或稍后重试")

# ----------------- 2. 板块轮动 -----------------
st.header("🔄 全球板块轮动热度（资源型重点监控）")
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
try:
    spy_hist = yf.download("SPY", period=period, progress=False)
    spy_perf = (spy_hist['Close'][-1] / spy_hist['Close'][0] - 1) * 100 if not spy_hist.empty and len(spy_hist) > 1 else 0

    for name, ticker in sector_tickers.items():
        hist = yf.download(ticker, period=period, progress=False)
        if not hist.empty and len(hist) > 1:
            perf = (hist['Close'][-1] / hist['Close'][0] - 1) * 100
            relative = perf - spy_perf
        else:
            perf = relative = 0
        sector_data.append({"板块": name, "周期涨跌%": round(perf, 2), "相对大盘%": round(relative, 2)})
except:
    st.error("板块数据加载失败，请刷新页面")

sector_df = pd.DataFrame(sector_data).sort_values("周期涨跌%", ascending=False)
styled_sector = sector_df.style.map(highlight_change, subset=["周期涨跌%", "相对大盘%"])
st.dataframe(styled_sector, use_container_width=True)

# 轮动柱状图（加保护）
if not sector_df.empty:
    fig_bar = px.bar(sector_df, x="板块", y="周期涨跌%", color="相对大盘%", title="板块轮动排名（资源强则绿灯）")
    st.plotly_chart(fig_bar, use_container_width=True)
else:
    st.warning("板块轮动图暂无数据")

# ----------------- 3. 中国资源股 -----------------
st.header("🇨🇳 中国资源股监控（钨/稀土龙头）")
china_tickers = {
    "中钨高新": "000657.SZ",
    "厦门钨业": "600549.SH",
    "北方稀土": "600111.SH",
    "盛和资源": "600392.SH",
    "广晟有色": "600259.SH",
    "中国稀土": "000831.SZ",
}

china_data = []
for name, code in china_tickers.items():
    try:
        df = ak.stock_zh_a_hist(symbol=code, adjust="qfq", timeout=10).tail(5)
        if not df.empty and len(df) >= 2:
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            day_change = (latest['收盘'] / prev['收盘'] - 1) * 100
            china_data.append({"股票": name, "最新价": round(latest['收盘'], 2), "日涨跌%": round(day_change, 2), "成交量(万)": round(latest['成交量']/10000, 1)})
    except:
        pass

china_df = pd.DataFrame(china_data)
if not china_df.empty:
    china_df = china_df.sort_values("日涨跌%", ascending=False)
    styled_china = china_df.style.map(highlight_change, subset=["日涨跌%"])
    st.dataframe(styled_china, use_container_width=True)
else:
    st.warning("今日A股资源股数据暂无（可能休市、网络或假期）")

# ----------------- 4. 智能警报 -----------------
st.header("🚨 今日投资警报（你的80%预判触发器）")
alerts = []

strong_com = com_df[pd.to_numeric(com_df["涨跌幅%"], errors='coerce') > 3]
if not strong_com.empty:
    alerts.append(f"🔥 大宗异动：{', '.join(strong_com['商品'])}")

resource_sectors = sector_df[sector_df["板块"].str.contains("材料|能源")]
strong_resource = resource_sectors[(resource_sectors["周期涨跌%"] > 3) & (resource_sectors["相对大盘%"] > 0)]
if not strong_resource.empty:
    alerts.append(f"🛢️ 资源周期强势：{', '.join(strong_resource['板块'])} 排名前茅 + 超大盘")

if not china_df.empty:
    strong_china = china_df[china_df["日涨跌%"] > 5]
    if not strong_china.empty:
        alerts.append(f"🇨🇳 A股资源爆发：{', '.join(strong_china['股票'])}")

if alerts:
    for a in alerts:
        st.success(a)
else:
    st.info("今日无明显异动，保持观察")

st.caption(f"数据更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} | 如加载慢请刷新页面")
