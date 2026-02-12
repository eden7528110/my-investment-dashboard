import streamlit as st
import yfinance as yf
import akshare as ak
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(layout="wide", page_title="资源 & 轮动投资仪表盘")
st.title("🛢️ 资源型 & 板块轮动实时仪表盘（全球 + A股）")

# 侧边栏设置
period = st.sidebar.selectbox("选择时间周期", ["1d", "5d", "1mo", "3mo", "ytd"], index=1)  # 默认5天，便于看轮动

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
    info = yf.Ticker(ticker).info
    price = info.get('regularMarketPrice') or info.get('previousClose') or 0
    change = info.get('regularMarketChangePercent') or 0
    com_data.append({"商品": name, "最新价": round(price, 2), "涨跌幅%": round(change, 2)})

com_df = pd.DataFrame(com_data).sort_values("涨跌幅%", ascending=False)
st.dataframe(com_df.style.background_gradient(cmap='RdYlGn', subset=["涨跌幅%"]), use_container_width=True)

# 商品走势图
selected_com = st.selectbox("选择商品查看走势", list(com_tickers.keys()))
hist_com = yf.download(com_tickers[selected_com], period="6mo")
fig_com = px.line(hist_com, x=hist_com.index, y="Close", title=f"{selected_com} 6个月走势")
st.plotly_chart(fig_com, use_container_width=True)

# ----------------- 2. 板块轮动（美国11大板块） -----------------
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
spy_hist = yf.download("SPY", period=period)
spy_perf = (spy_hist['Close'][-1] / spy_hist['Close'][0] - 1) * 100 if len(spy_hist) > 1 else 0

for name, ticker in sector_tickers.items():
    hist = yf.download(ticker, period=period)
    if len(hist) > 1:
        perf = (hist['Close'][-1] / hist['Close'][0] - 1) * 100
        relative = perf - spy_perf
    else:
        perf = relative = 0
    sector_data.append({"板块": name, "周期涨跌%": round(perf, 2), "相对大盘%": round(relative, 2)})

sector_df = pd.DataFrame(sector_data).sort_values("周期涨跌%", ascending=False)
st.dataframe(sector_df.style.background_gradient(cmap='RdYlGn', subset=["周期涨跌%", "相对大盘%"]), use_container_width=True)

# 轮动柱状图
fig_bar = px.bar(sector_df, x="板块", y="周期涨跌%", color="相对大盘%", title="板块轮动排名（资源强则绿灯）")
st.plotly_chart(fig_bar, use_container_width=True)

# ----------------- 3. 中国资源股重点 -----------------
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
        df = ak.stock_zh_a_hist(symbol=code, adjust="qfq").tail(5)
        if not df.empty:
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            day_change = (latest['收盘'] / prev['收盘'] - 1) * 100
            china_data.append({"股票": name, "最新价": round(latest['收盘'], 2), "日涨跌%": round(day_change, 2), "成交量(万)": round(latest['成交量']/10000, 1)})
    except:
        pass

china_df = pd.DataFrame(china_data)
if not china_df.empty:
    china_df = china_df.sort_values("日涨跌%", ascending=False)
    st.dataframe(china_df.style.background_gradient(cmap='RdYlGn', subset=["日涨跌%"]), use_container_width=True)

# ----------------- 4. 智能警报 -----------------
st.header("🚨 今日投资警报（你的80%预判触发器）")
alerts = []

# 商品警报
strong_com = com_df[com_df["涨跌幅%"] > 3]
if not strong_com.empty:
    alerts.append(f"🔥 大宗异动：{', '.join(strong_com['商品'])}")

# 资源板块轮动警报
resource_sectors = sector_df[sector_df["板块"].str.contains("材料|能源")]
strong_resource = resource_sectors[(resource_sectors["周期涨跌%"] > 3) & (resource_sectors["相对大盘%"] > 0)]
if not strong_resource.empty:
    alerts.append(f"🛢️ 资源周期强势：{', '.join(strong_resource['板块'])} 排名前茅 + 超大盘")

# 中国股警报
if not china_df.empty:
    strong_china = china_df[china_df["日涨跌%"] > 5]
    if not strong_china.empty:
        alerts.append(f"🇨🇳 A股资源爆发：{', '.join(strong_china['股票'])}")

if alerts:
    for a in alerts:
        st.success(a)
else:
    st.info("今日无明显异动，保持观察")

st.caption(f"数据更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} | 建议每天早盘打开审阅")