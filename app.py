import streamlit as st
import yfinance as yf
import akshare as ak
import pandas as pd
import plotly.express as px
from datetime import datetime

# ----------------- 1. 样式与高亮 -----------------
def highlight_change(val):
    if pd.isna(val): return ''
    try:
        val = float(val)
        if val > 0: return 'background-color: rgba(0, 255, 0, 0.1); color: #00ff00; font-weight: bold'
        elif val < 0: return 'background-color: rgba(255, 0, 0, 0.1); color: #ff4b4b; font-weight: bold'
    except: pass
    return ''

st.set_page_config(layout="wide", page_title="硬核资源投资仪表盘")
st.title("🛢️ 全球资源监控 & 实时库存分析系统")

# ----------------- 2. 库存抓取引擎 -----------------
@st.cache_data(ttl=3600) # 缓存1小时，避免频繁请求被封
def get_inventory_data():
    """抓取 LME 和 SHFE 核心库存数据"""
    stocks = {"LME": {}, "SHFE": {}}
    try:
        # 抓取全球库存 (LME)
        lme_df = ak.futures_comm_stock_lme()
        if not lme_df.empty:
            # 匹配 铜、铝 等关键词
            stocks["LME"] = lme_df.set_index('item')['stock'].to_dict()
    except: pass

    try:
        # 抓取中国库存 (SHFE)
        shfe_df = ak.futures_inventory_shfe()
        if not shfe_df.empty:
            stocks["SHFE"] = shfe_df.set_index('symbol')['inventory'].to_dict()
    except: pass
    return stocks

# 获取库存快照
inventory_snapshot = get_inventory_data()

# ----------------- 3. 核心配置清单 -----------------
com_tickers = {
    "原油 (CL=F)": {"yf": "CL=F", "key": "原油"},
    "黄金 (GC=F)": {"yf": "GC=F", "key": "黄金"},
    "期铜 (HG=F)": {"yf": "HG=F", "key": "铜"},
    "期铝 (ALI=F)": {"yf": "ALI=F", "key": "铝"},
    "白银 (SI=F)": {"yf": "SI=F", "key": "白银"},
    "天然气 (NG=F)": {"yf": "NG=F", "key": "天然气"},
    "稀土 ETF (REMX)": {"yf": "REMX", "key": "稀土"},
    "锂电 ETF (LIT)": {"yf": "LIT", "key": "锂"}
}

china_tickers = {
    "宝武镁业(镁)": {"ak": "002182", "yf": "002182.SZ"},
    "中钨高新(钨)": {"ak": "000657", "yf": "000657.SZ"},
    "北方稀土(稀土)": {"ak": "600111", "yf": "600111.SS"},
    "江西铜业(铜)": {"ak": "600362", "yf": "600362.SS"},
    "中国铝业(铝)": {"ak": "601600", "yf": "601600.SS"}
}

# ----------------- 4. 数据处理 -----------------
com_data = []
alerts = []

for label, cfg in com_tickers.items():
    try:
        # 抓取行情
        t = yf.Ticker(cfg["yf"])
        hist = t.history(period="2d")
        if not hist.empty:
            if isinstance(hist.columns, pd.MultiIndex): hist.columns = hist.columns.get_level_values(0)
            price = hist['Close'].iloc[-1]
            change = ((price / hist['Close'].iloc[-2]) - 1) * 100 if len(hist)>1 else 0
            
            # 匹配库存数据
            lme_val = inventory_snapshot["LME"].get(cfg["key"], "无数据")
            shfe_val = inventory_snapshot["SHFE"].get(cfg["key"], "无数据")

            com_data.append({
                "项目": label, 
                "最新价": round(price, 2), 
                "涨跌幅%": round(change, 2),
                "全球库存 (LME)": lme_val,
                "中国库存 (SHFE)": shfe_val
            })
            if change > 3: alerts.append(f"🔥 大宗异动：{label} 今日拉升 {round(change,2)}%！")
    except:
        com_data.append({"项目": label, "最新价": "N/A", "涨跌幅%": 0, "全球库存": "-", "中国库存": "-"})

# ----------------- 5. 页面渲染 -----------------

# 警报
st.header("🚨 实时风险警报")
if alerts:
    for a in alerts: st.warning(a)
else: st.info("市场情绪平稳，暂无重大价格异动。")

# 大宗商品看板
st.header("🌍 全球大宗商品 & 实时库存看板")
df_com = pd.DataFrame(com_data)
st.dataframe(df_com.style.map(highlight_change, subset=["涨跌幅%"]), use_container_width=True)

# A股资源监控 (增加自动容错显示)
st.header("🧱 资源龙头监控 (A股/备用多链路)")
china_results = []
for name, codes in china_tickers.items():
    price, change, source = "N/A", 0, "None"
    # 先尝试国际源 (yfinance)，通常对海外部署更友好
    try:
        yt = yf.Ticker(codes["yf"])
        yh = yt.history(period="2d")
        if not yh.empty:
            price = yh['Close'].iloc[-1]
            change = ((price / yh['Close'].iloc[-2]) - 1) * 100
            source = "Yahoo(Global)"
    except:
        # 失败则尝试国内源
        try:
            df = ak.stock_zh_a_hist(symbol=codes["ak"], period="daily").tail(2)
            price = df.iloc[-1]['收盘']
            change = (price / df.iloc[0]['收盘'] - 1) * 100
            source = "Sina(China)"
        except: pass
    
    china_results.append({"关联标的": name, "价格": price, "日涨跌%": round(change, 2), "来源": source})

df_china = pd.DataFrame(china_results)
st.dataframe(df_china.style.map(highlight_change, subset=["日涨跌%"]), use_container_width=True)

# 历史趋势对比
st.header("📊 关键商品 6个月趋势分析")
selected_label = st.selectbox("选择要查看的商品走势", options=list(com_tickers.keys()))
target_ticker = com_tickers[selected_label]["yf"]

try:
    plot_data = yf.download(target_ticker, period="6mo", progress=False)
    if isinstance(plot_data.columns, pd.MultiIndex): plot_data.columns = plot_data.columns.get_level_values(0)
    st.plotly_chart(px.line(plot_data, x=plot_data.index, y="Close", title=f"{selected_label} 周期走势", template="plotly_dark"), use_container_width=True)
except:
    st.error("图表数据加载失败")

st.caption(f"系统运行中 | 最后同步: {datetime.now().strftime('%H:%M:%S')} | 库存数据每小时自动更新")
