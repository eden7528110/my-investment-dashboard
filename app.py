import streamlit as st
import yfinance as yf
import akshare as ak
import pandas as pd
import plotly.express as px
from datetime import datetime

# 高亮函数
def highlight_change(val):
    if pd.isna(val): return ''
    try:
        val = float(val)
        if val > 0: return 'color: #00ff00; font-weight: bold' # 亮绿
        elif val < 0: return 'color: #ff4b4b; font-weight: bold' # 亮红
    except: pass
    return ''

st.set_page_config(layout="wide", page_title="资源 & 轮动投资仪表盘")
st.title("🛢️ 资源型 & 宏观风向标实时仪表盘")

# ----------------- 1. 全球大宗商品 & 宏观比例 -----------------
st.header("🌍 全球大宗商品 & 宏观比率")

com_tickers = {
    "原油 CL=F": "CL=F",
    "黄金 GC=F": "GC=F",
    "铜 HG=F": "HG=F",
    "铝 ALI=F": "ALI=F",
    "白银 SI=F": "SI=F",
    "天然气 NG=F": "NG=F",
    "稀土 ETF REMX": "REMX",
}

com_data = []
# 用于计算铜金比的临时变量
prices_for_ratio = {"HG=F": None, "GC=F": None}

for name, ticker in com_tickers.items():
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="2d")
        if not hist.empty:
            # 处理 MultiIndex 情况
            if isinstance(hist.columns, pd.MultiIndex):
                hist.columns = hist.columns.get_level_values(0)
            
            price = hist['Close'].iloc[-1]
            prev = hist['Close'].iloc[-2] if len(hist) > 1 else price
            change = ((price / prev) - 1) * 100
            com_data.append({"项目": name, "最新价": round(float(price), 2), "涨跌幅%": round(float(change), 2)})
            
            # 存入比率计算
            if ticker in prices_for_ratio:
                prices_for_ratio[ticker] = price
    except:
        com_data.append({"项目": name, "最新价": "N/A", "涨跌幅%": 0})

# --- 计算铜金比 ---
if prices_for_ratio["HG=F"] and prices_for_ratio["GC=F"]:
    cu_au_ratio = prices_for_ratio["HG=F"] / prices_for_ratio["GC=F"]
    # 铜金比通常放大 1000 倍观察更直观
    com_data.append({"项目": "📈 铜金比 (Cu/Au x 1000)", "最新价": round(cu_au_ratio * 1000, 4), "涨跌幅%": 0})

com_df = pd.DataFrame(com_data)
com_df["涨跌幅%"] = pd.to_numeric(com_df["涨跌幅%"], errors='coerce').fillna(0)
st.dataframe(com_df.style.map(highlight_change, subset=["涨跌幅%"]), use_container_width=True)

# ----------------- 2. 金属镁专题 (A股龙头) -----------------
st.header("🧱 金属镁 & 战略资源监控 (A股)")

# 云海金属已更名为宝武镁业，代码 002182
mag_tickers = {
    "宝武镁业(镁业龙头)": "002182",
    "中钨高新(钨业)": "000657",
    "北方稀土(稀土)": "600111",
    "中国铝业(铝业)": "601600"
}

mag_data = []
for name, code in mag_tickers.items():
    try:
        # 使用 akshare 获取最近数据
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(2)
        if not df.empty:
            latest = df.iloc[-1]
            prev = df.iloc[0]
            change = (latest['收盘'] / prev['收盘'] - 1) * 100
            mag_data.append({
                "关联标的": name, 
                "价格": latest['收盘'], 
                "日涨跌%": round(change, 2),
                "成交额(亿)": round(latest['成交额']/100000000, 2)
            })
    except:
        pass

if mag_data:
    st.dataframe(pd.DataFrame(mag_data).style.map(highlight_change, subset=["日涨跌%"]), use_container_width=True)
else:
    st.info("A股数据暂未开市或抓取受限")

# ----------------- 3. 走势对比可视化 -----------------
st.header("📊 关键走势对比 (近6个月)")
target = st.selectbox("选择对比基准", ["HG=F", "GC=F", "CL=F"])
hist_data = yf.download(target, period="6mo", progress=False)
if isinstance(hist_data.columns, pd.MultiIndex):
    hist_data.columns = hist_data.columns.get_level_values(0)

if not hist_data.empty:
    fig = px.line(hist_data, x=hist_data.index, y="Close", title=f"{target} 周期走势分析")
    st.plotly_chart(fig, use_container_width=True)

st.caption(f"系统侦测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 铜金比上涨通常代表市场风险偏好回归。")
