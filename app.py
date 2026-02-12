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

st.set_page_config(layout="wide", page_title="硬核资源仪表盘-V3")
st.title("🛢️ 全球资源监控 & 穿透式库存看板")

# ----------------- 2. 增强型库存抓取引擎 -----------------
@st.cache_data(ttl=3600)
def get_inventory_data():
    """从多个源头抓取原始库存表格"""
    stocks = {"LME": pd.DataFrame(), "SHFE": pd.DataFrame()}
    try:
        # 抓取全球库存 (LME)
        stocks["LME"] = ak.futures_comm_stock_lme()
    except: pass

    try:
        # 抓取中国库存 (SHFE)
        stocks["SHFE"] = ak.futures_inventory_shfe()
    except: pass
    return stocks

def find_stock(keyword, stock_dict):
    """模糊匹配逻辑：在库存表中寻找关键词"""
    # 处理 LME
    lme_val = "无数据"
    if not stock_dict["LME"].empty:
        # LME 原始表匹配
        match = stock_dict["LME"][stock_dict["LME"]['item'].str.contains(keyword, na=False)]
        if not match.empty:
            lme_val = f"{match.iloc[0]['stock']} {match.iloc[0].get('unit', '吨')}"
    
    # 处理 SHFE
    shfe_val = "无数据"
    if not stock_dict["SHFE"].empty:
        # SHFE 原始表匹配 (通常 symbol 字段是 'cu', 'al' 等)
        # 映射表
        mapping = {"铜": "cu", "铝": "al", "天然气": "ng", "白银": "ag", "黄金": "au"}
        shfe_key = mapping.get(keyword, keyword)
        match = stock_dict["SHFE"][stock_dict["SHFE"]['symbol'].str.contains(shfe_key, case=False, na=False)]
        if not match.empty:
            shfe_val = f"{match.iloc[0]['inventory']} 吨"
            
    return lme_val, shfe_val

# 获取数据快照
inventory_snapshot = get_inventory_data()

# ----------------- 3. 配置清单 -----------------
com_tickers = {
    "期铜 (HG=F)": {"yf": "HG=F", "key": "铜"},
    "期铝 (ALI=F)": {"yf": "ALI=F", "key": "铝"},
    "黄金 (GC=F)": {"yf": "GC=F", "key": "黄金"},
    "原油 (CL=F)": {"yf": "CL=F", "key": "原油"},
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

# ----------------- 4. 数据合并 -----------------
com_results = []
alerts = []

for label, cfg in com_tickers.items():
    lme_stock, shfe_stock = find_stock(cfg["key"], inventory_snapshot)
    try:
        t = yf.Ticker(cfg["yf"])
        hist = t.history(period="2d")
        if not hist.empty:
            if isinstance(hist.columns, pd.MultiIndex): hist.columns = hist.columns.get_level_values(0)
            price = hist['Close'].iloc[-1]
            change = ((price / hist['Close'].iloc[-2]) - 1) * 100 if len(hist)>1 else 0
            
            com_results.append({
                "项目": label, 
                "最新价": round(price, 2), 
                "涨跌幅%": round(change, 2),
                "全球库存 (LME)": lme_stock,
                "中国库存 (SHFE)": shfe_stock
            })
            if change > 3: alerts.append(f"🔥 大宗暴涨：{label} 涨幅 {round(change,2)}%！")
    except:
        com_results.append({"项目": label, "最新价": "N/A", "涨跌幅%": 0, "全球库存": lme_stock, "中国库存": shfe_stock})

# ----------------- 5. 页面渲染 -----------------

# 警报
st.header("🚨 策略警报中心")
if alerts:
    for a in alerts: st.error(a)
else: st.info("当前市场无异常价格爆发。")

# 全球看板
st.header("🌍 全球大宗商品 & 实时仓单快照")
df_com = pd.DataFrame(com_results)
st.dataframe(df_com.style.map(highlight_change, subset=["涨跌幅%"]), use_container_width=True)

# A股资源 (针对截图1的修复)
st.header("🧱 A股龙头监控 (多源冗余链路)")
china_results = []
for name, codes in china_tickers.items():
    # 强制优先使用 yfinance 避免截图中的“抓取受限”
    try:
        yt = yf.Ticker(codes["yf"])
        yh = yt.history(period="2d")
        if not yh.empty:
            price = yh['Close'].iloc[-1]
            change = ((price / yh['Close'].iloc[-2]) - 1) * 100
            source = "Yahoo(稳定)"
        else: raise Exception()
    except:
        try:
            df = ak.stock_zh_a_hist(symbol=codes["ak"], period="daily").tail(2)
            price, change, source = df.iloc[-1]['收盘'], (df.iloc[-1]['收盘']/df.iloc[0]['收盘']-1)*100, "Sina(国内)"
        except: price, change, source = "N/A", 0, "失效"
    
    china_results.append({"关联标的": name, "价格": price, "日涨跌%": round(change, 2), "链路": source})

st.dataframe(pd.DataFrame(china_results).style.map(highlight_change, subset=["日涨跌%"]), use_container_width=True)

# 图表
st.header("📈 价格走势穿透")
sel = st.selectbox("选择商品", options=list(com_tickers.keys()))
try:
    p_data = yf.download(com_tickers[sel]["yf"], period="6mo", progress=False)
    if isinstance(p_data.columns, pd.MultiIndex): p_data.columns = p_data.columns.get_level_values(0)
    st.plotly_chart(px.line(p_data, x=p_data.index, y="Close", title=f"{sel} 趋势图", template="plotly_dark"), use_container_width=True)
except: st.error("趋势图调取失败")

st.caption(f"最后巡检时间: {datetime.now().strftime('%H:%M:%S')} | 库存数据已通过 fuzzy_match 引擎重连")
