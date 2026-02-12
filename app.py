import streamlit as st
import yfinance as yf
import akshare as ak
import pandas as pd
import plotly.express as px
from datetime import datetime

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
st.title("🛢️ 资源型 & 板块轮动实时仪表盘")

# 侧边栏
period = st.sidebar.selectbox("选择时间周期", ["1d", "5d", "1mo", "3mo", "ytd"], index=1)

# ----------------- 1. 全球大宗商品 -----------------
st.header("🌍 全球大宗商品价格与变化")
com_tickers = {
    "原油 CL=F": "CL=F",
    "黄金 GC=F": "GC=F",
    "铜 HG=F": "HG=F",
    "铝 ALI=F": "ALI=F",
    "煤炭 QL=F": "QL=F",
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
        # 尝试获取实时数据
        t = yf.Ticker(ticker)
        # 修复点：改用 fast_info 或 history 以增强稳定性
        hist = t.history(period="2d")
        if not hist.empty and len(hist) >= 1:
            price = hist['Close'].iloc[-1]
            prev_price = hist['Close'].iloc[-2] if len(hist) > 1 else price
            change = ((price / prev_price) - 1) * 100 if prev_price != 0 else 0
            com_data.append({"商品": name, "最新价": round(float(price), 2), "涨跌幅%": round(float(change), 2)})
            data_date = hist.index[-1].strftime("%Y-%m-%d")
        else:
            raise Exception("数据为空")
    except:
        com_data.append({"商品": name, "最新价": "N/A", "涨跌幅%": 0})

com_df = pd.DataFrame(com_data)
# --- 核心修复行 ---
com_df["涨跌幅%"] = pd.to_numeric(com_df["涨跌幅%"], errors='coerce').fillna(0)
# -----------------
com_df = com_df.sort_values("涨跌幅%", ascending=False)
styled_com = com_df.style.map(highlight_change, subset=["涨跌幅%"])
st.dataframe(styled_com, use_container_width=True)

# 商品走势图
selected_com = st.selectbox("选择商品查看走势", list(com_tickers.keys()))
selected_ticker = com_tickers[selected_com]
hist_com = yf.download(selected_ticker, period="6mo", progress=False)

# 修复 yfinance 返回 MultiIndex 导致绘图报错的问题
if isinstance(hist_com.columns, pd.MultiIndex):
    hist_com.columns = hist_com.columns.get_level_values(0)

if not hist_com.empty and 'Close' in hist_com.columns:
    fig_com = px.line(hist_com, x=hist_com.index, y="Close", title=f"{selected_com} 6个月走势")
    st.plotly_chart(fig_com, use_container_width=True)

# ----------------- 2. 板块轮动 -----------------
st.header("🔄 全球板块轮动热度")
sector_tickers = {
    "材料 XLB": "XLB", "能源 XLE": "XLE", "金融 XLF": "XLF",
    "科技 XLK": "XLK", "工业 XLI": "XLI", "医疗 XLV": "XLV"
}

sector_data = []
try:
    spy_hist = yf.download("SPY", period=period, progress=False)
    if isinstance(spy_hist.columns, pd.MultiIndex): spy_hist.columns = spy_hist.columns.get_level_values(0)
    spy_perf = (spy_hist['Close'].iloc[-1] / spy_hist['Close'].iloc[0] - 1) * 100

    for name, ticker in sector_tickers.items():
        s_hist = yf.download(ticker, period=period, progress=False)
        if isinstance(s_hist.columns, pd.MultiIndex): s_hist.columns = s_hist.columns.get_level_values(0)
        if not s_hist.empty:
            perf = (s_hist['Close'].iloc[-1] / s_hist['Close'].iloc[0] - 1) * 100
            sector_data.append({"板块": name, "周期涨跌%": round(perf, 2), "相对大盘%": round(perf - spy_perf, 2)})
except:
    st.warning("板块数据加载受限")

sector_df = pd.DataFrame(sector_data)
if not sector_df.empty:
    st.dataframe(sector_df.style.map(highlight_change, subset=["周期涨跌%", "相对大盘%"]), use_container_width=True)

# ----------------- 3. 中国资源股 -----------------
st.header("🇨🇳 中国资源股监控")
china_tickers = {"中钨高新": "000657", "北方稀土": "600111", "中国铝业": "601600"}

china_data = []
for name, code in china_tickers.items():
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(5)
        if not df.empty:
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            change = (latest['收盘'] / prev['收盘'] - 1) * 100
            china_data.append({"股票": name, "最新价": latest['收盘'], "日涨跌%": round(change, 2)})
    except:
        pass

if china_data:
    st.dataframe(pd.DataFrame(china_data).style.map(highlight_change, subset=["日涨跌%"]), use_container_width=True)

st.caption(f"系统运行正常 | 更新时间: {datetime.now().strftime('%H:%M:%S')}")
