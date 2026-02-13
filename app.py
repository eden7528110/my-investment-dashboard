import streamlit as st
import yfinance as yf
import akshare as ak
import pandas as pd
import plotly.express as px
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# ----------------- 1. 初始化 -----------------
st.set_page_config(layout="wide", page_title="硬核全维度资源监控")
st.title("🛡️ 全球资源监控 & 核心资产看板 (修复版)")

def highlight_flow(val):
    if not isinstance(val, (int, float)): return ''
    return 'color: #00ff00' if val > 0 else 'color: #ff4b4b' if val < 0 else ''

# ----------------- 2. 标的配置 -----------------
com_tickers = {
    "期铜 (HG=F)": "HG=F",
    "黄金 (GC=F)": "GC=F",
    "期铝 (ALI=F)": "ALI=F",
    "白银 (SI=F)": "SI=F",
    "原油 (CL=F)": "CL=F",
    "稀土 ETF (REMX)": "REMX",
    "锂电 ETF (LIT)": "LIT"
}

stock_list = {
    "中钨高新": "000657.SZ", "宝武镁业": "002182.SZ", "中国铝业": "601600.SS", 
    "洛阳钼业": "603993.SS", "紫金矿业": "601899.SS", "北方稀土": "600111.SS",
    "江西铜业": "600362.SS", "中国神华": "601088.SS", "宁德时代": "300750.SZ",
    "牧原股份": "002714.SZ", "温氏股份": "300498.SZ", "拓普集团": "601689.SS",
    "旭升集团": "603305.SS", "绿的谐波": "688017.SS", "捷捷微电": "300623.SZ",
    "粤桂股份": "000833.SZ", "建设银行": "601939.SS", "工商银行": "601398.SS",
    "中国平安": "601318.SS", "贝泰妮": "300957.SZ", "宝泰隆": "601011.SS",
    "上大股份": "301522.SZ", "小米股份": "1810.HK", "泡泡玛特": "9992.HK"
}

# ----------------- 3. 增强型数据引擎 -----------------

@st.cache_data(ttl=3600)
def fetch_inventory():
    """抓取库存数据"""
    inv = {}
    try:
        url = "https://www.metal.com/LME/Inventory"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        table = soup.find('table')
        if table:
            for row in table.find_all('tr')[1:]:
                cols = row.find_all(['td', 'th'])
                if len(cols) >= 2:
                    name = cols[0].text.strip().upper()
                    inv[name] = cols[1].text.strip()
    except: pass
    return inv

# ----------------- 4. 页面逻辑 -----------------
with st.spinner('正在同步多源冗余数据...'):
    inv_data = fetch_inventory()
    # 尝试抓取 A 股深度数据
    try:
        df_spot = ak.stock_zh_a_spot_em()
        df_flow = ak.stock_individual_fund_flow_rank_em()
    except:
        df_spot, df_flow = pd.DataFrame(), pd.DataFrame()

# [一] 全球大宗商品 & 实时铜金比
st.header("🌍 全球大宗商品 & 实时仓单快照")
com_res = []
cu_p, au_p = 1.0, 1.0

for label, ticker in com_tickers.items():
    try:
        info = yf.Ticker(ticker).fast_info
        price = info.last_price
        chg = ((price / info.previous_close) - 1) * 100
        # 为铜金比留存价格
        if "HG=F" in ticker: cu_p = price
        if "GC=F" in ticker: au_p = price
        
        com_res.append({
            "项目": label, "最新价": round(price, 3), "涨跌幅%": round(chg, 2),
            "全球库存(LME)": inv_data.get(label.split(' ')[0][1:].upper(), "无数据")
        })
    except: pass

# 强制插入铜金比行
com_res.append({
    "项目": "📈 铜金比 (Cu/Au x 1000)", 
    "最新价": round((cu_p / au_p) * 1000, 4), 
    "涨跌幅%": "宏观指标", "全球库存(LME)": "---"
})

st.dataframe(pd.DataFrame(com_res).style.map(highlight_flow, subset=['涨跌幅%']), use_container_width=True)

# [二] 核心资产表 (双链路修复)
st.header("🧱 核心资产监控 (筹码/分红/资金流)")
china_res = []
for name, code in stock_list.items():
    pure_code = code.split('.')[0]
    # 默认值
    row = {"名称": name, "价格": "N/A", "涨跌%": 0.0, "PE(动)": "-", "主力1d(万)": 0, "数据源": "Wait"}
    
    # 链路 A: AkShare (深度指标)
    if not df_spot.empty and '代码' in df_spot.columns:
        m = df_spot[df_spot['代码'] == pure_code]
        if not m.empty:
            row.update({"价格": m.iloc[0]['最新价'], "涨跌%": m.iloc[0]['涨跌幅'], "PE(动)": m.iloc[0]['市盈率-动态'], "数据源": "Domestic"})
    
    # 链路 B: Yahoo Finance (冗余价格保障)
    if row["价格"] == "N/A":
        try:
            t = yf.Ticker(code).fast_info
            row.update({"价格": round(t.last_price, 2), "涨跌%": round(((t.last_price/t.previous_close)-1)*100, 2), "数据源": "Global"})
        except: pass

    # 资金流匹配
    if not df_flow.empty and '代码' in df_flow.columns:
        f = df_flow[df_flow['代码'] == pure_code]
        if not f.empty: row.update({"主力1d(万)": round(f.iloc[0]['今日主力净流入-净额']/10000, 0)})
        
    china_res.append(row)

st.dataframe(pd.DataFrame(china_res).style.map(highlight_flow, subset=['涨跌%', '主力1d(万)']), use_container_width=True)

# [三] 10年趋势 (计算对齐修复)
st.header("📈 价格走势穿透 (10年长周期历史数据)")
trend_opts = {"铜金比": "RATIO"}
trend_opts.update(com_tickers)
trend_opts.update(stock_list)

sel = st.selectbox("选择分析标的", options=list(trend_opts.keys()))
ticker = trend_opts[sel]

try:
    if ticker == "RATIO":
        cu = yf.download("HG=F", period="10y", progress=False)['Close']
        au = yf.download("GC=F", period="10y", progress=False)['Close']
        combined = pd.concat([cu, au], axis=1, join='inner')
        combined.columns = ['Cu', 'Au']
        fig = px.line(x=combined.index, y=(combined['Cu']/combined['Au'])*1000, title="铜金比 10年周期", template="plotly_dark")
    else:
        hist = yf.download(ticker, period="10y", progress=False)['Close']
        fig = px.line(x=hist.index, y=hist.values.flatten(), title=f"{sel} 10年趋势", template="plotly_dark")
    
    st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.error(f"图表加载失败: {e}")

st.caption(f"最后刷新: {datetime.now().strftime('%H:%M:%S')} | 已激活冗余数据链路")
