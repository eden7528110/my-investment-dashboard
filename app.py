import streamlit as st
import yfinance as yf
import akshare as ak
import pandas as pd
import plotly.express as px
from datetime import datetime

# 1. 样式与高亮函数
def highlight_change(val):
    if pd.isna(val): return ''
    try:
        val = float(val)
        if val > 0: return 'background-color: rgba(0, 255, 0, 0.1); color: #00ff00; font-weight: bold'
        elif val < 0: return 'background-color: rgba(255, 0, 0, 0.1); color: #ff4b4b; font-weight: bold'
    except: pass
    return ''

st.set_page_config(layout="wide", page_title="高级资源投资仪表盘")
st.title("🛢️ 全球资源监控 & 宏观库存仪表盘")

# ----------------- 核心配置清单 -----------------
com_tickers = {
    "原油 (CL=F)": "CL=F",
    "黄金 (GC=F)": "GC=F",
    "期铜 (HG=F)": "HG=F",
    "期铝 (ALI=F)": "ALI=F",
    "白银 (SI=F)": "SI=F",
    "天然气 (NG=F)": "NG=F",
    "稀土 ETF (REMX)": "REMX",
    "锂电 ETF (LIT)": "LIT"
}

# 增加 A 股代码对应的备用 Yahoo Finance 代码（如：002182 -> 002182.SZ）
china_tickers = {
    "宝武镁业(镁)": {"ak": "002182", "yf": "002182.SZ"},
    "中钨高新(钨)": {"ak": "000657", "yf": "000657.SZ"},
    "北方稀土(稀土)": {"ak": "600111", "yf": "600111.SS"},
    "江西铜业(铜)": {"ak": "600362", "yf": "600362.SS"},
    "中国铝业(铝)": {"ak": "601600", "yf": "601600.SS"}
}

# ----------------- 数据抓取逻辑 -----------------
com_data = []
prices_for_ratio = {"HG=F": None, "GC=F": None}
alerts = []

# 全球大宗看板抓取
for label, ticker in com_tickers.items():
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="2d")
        if not hist.empty:
            if isinstance(hist.columns, pd.MultiIndex): hist.columns = hist.columns.get_level_values(0)
            price = hist['Close'].iloc[-1]
            prev = hist['Close'].iloc[-2] if len(hist) > 1 else price
            change = ((price / prev) - 1) * 100
            com_data.append({
                "项目": label, 
                "最新价": round(float(price), 2), 
                "涨跌幅%": round(float(change), 2),
                "全球库存 (LME)": "查询中...", # 此处预留接口位
                "中国库存 (SHFE)": "查询中..."
            })
            if ticker in prices_for_ratio: prices_for_ratio[ticker] = price
            if change > 3: alerts.append(f"🔥 大宗异动：{label} 今日大涨 {round(change,2)}%！")
    except:
        com_data.append({"项目": label, "最新价": "N/A", "涨跌幅%": 0})

# ----------------- A股数据：多源热备逻辑 -----------------
china_data = []
for name, codes in china_tickers.items():
    success = False
    # 尝试一：Akshare (国内接口)
    try:
        df = ak.stock_zh_a_hist(symbol=codes["ak"], period="daily", adjust="qfq").tail(2)
        if not df.empty:
            latest = df.iloc[-1]
            prev = df.iloc[0]
            price, change = latest['收盘'], (latest['收盘'] / prev['收盘'] - 1) * 100
            amount = round(latest['成交额']/100000000, 2)
            source = "Sina/East"
            success = True
    except: pass

    # 尝试二：Yahoo Finance (备用接口)
    if not success:
        try:
            yt = yf.Ticker(codes["yf"])
            yh = yt.history(period="2d")
            if not yh.empty:
                price = yh['Close'].iloc[-1]
                change = ((price / yh['Close'].iloc[-2]) - 1) * 100
                amount = "N/A"
                source = "Yahoo(Backup)"
                success = True
        except: pass

    if success:
        china_data.append({
            "关联标的": name, 
            "价格": round(price, 2), 
            "日涨跌%": round(change, 2), 
            "成交额(亿)": amount,
            "数据来源": source,
            "全球库存": "监控中", 
            "中国库存": "监控中"
        })
        if isinstance(change, (int, float)) and change > 5:
            alerts.append(f"🇨🇳 A股爆发：{name} 今日异动拉升 {round(change,2)}%！")

# ----------------- 页面显示 -----------------

# 1. 警报模块
st.header("🚨 风险与机会实时警报")
if alerts:
    for a in alerts: st.warning(a)
else: st.info("当前市场波动平稳。")

# 2. 全球大宗看板 (含库存列)
st.header("🌍 全球大宗商品看板 (含库存指标)")
if com_data:
    df_com = pd.DataFrame(com_data)
    st.dataframe(df_com.style.map(highlight_change, subset=["涨跌幅%"]), use_container_width=True)

# 3. A股资源监控 (含热备显示)
st.header("🧱 资源龙头监控 (多源备份)")
if china_data:
    df_china = pd.DataFrame(china_data)
    st.dataframe(df_china.style.map(highlight_change, subset=["日涨跌%"]), use_container_width=True)
else:
    st.error("❌ 国内及备用接口均抓取失败。请检查网络环境。")

# 4. 走势分析
st.header("📊 历史周期走势")
select_options = {v: k for k, v in com_tickers.items()}
selected_ticker = st.selectbox("选择商品", options=list(select_options.keys()), format_func=lambda x: select_options[x])

try:
    h_data = yf.download(selected_ticker, period="6mo", progress=False)
    if not h_data.empty:
        if isinstance(h_data.columns, pd.MultiIndex): h_data.columns = h_data.columns.get_level_values(0)
        st.plotly_chart(px.line(h_data, x=h_data.index, y="Close", title=f"{select_options[selected_ticker]} 6个月走势"), use_container_width=True)
except: st.error("绘图失败。")

st.caption(f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 已启用 Yahoo Finance 作为 A 股备用数据源。")
