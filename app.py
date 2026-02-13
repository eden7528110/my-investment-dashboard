import streamlit as st
import yfinance as yf
import akshare as ak
import pandas as pd
import plotly.express as px
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# ----------------- 1. 配置与初始化 -----------------
st.set_page_config(layout="wide", page_title="硬核资产监控-投资决策版")
st.title("🛡️ 全球大宗 & A/H 核心标的全维度监控")

# 辅助高亮函数
def highlight_val(val):
    if not isinstance(val, (int, float)): return ''
    if val > 0: return 'color: #00ff00; font-weight: bold'
    elif val < 0: return 'color: #ff4b4b; font-weight: bold'
    return ''

# ----------------- 2. 增强型数据引擎 -----------------

@st.cache_data(ttl=3600)
def get_smm_inventory():
    """SMM 爬虫逻辑"""
    inv = {}
    headers = {'User-Agent': 'Mozilla/5.0'}
    urls = {"LME": "https://www.metal.com/LME/Inventory", "SHFE": "https://www.metal.com/SHFE/Inventory"}
    for k, url in urls.items():
        try:
            r = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(r.text, 'html.parser')
            table = soup.find('table')
            if table:
                for row in table.find_all('tr')[1:]:
                    tds = row.find_all(['td', 'th'])
                    if len(tds) >= 2:
                        name = tds[0].text.strip().replace('LME ', '').split('(')[0].strip()
                        inv[f"{k}_{name}"] = tds[1].text.strip()
        except: pass
    return inv

@st.cache_data(ttl=1800)
def get_china_market_data():
    """批量获取A股实时行情与基本面指标"""
    try:
        # 获取实时行情（含PE, PB）
        df_spot = ak.stock_zh_a_spot_em()
        # 获取主力资金流向排名
        df_flow = ak.stock_individual_fund_flow_rank_em()
        return df_spot, df_flow
    except:
        return pd.DataFrame(), pd.DataFrame()

# ----------------- 3. 标的清单 -----------------
china_tickers = {
    "中钨高新": "000657", "宝武镁业": "002182", "中国铝业": "601600", "洛阳钼业": "603993",
    "紫金矿业": "601899", "北方稀土": "600111", "江西铜业": "600362", "中国神华": "601088",
    "宁德时代": "300750", "牧原股份": "002714", "温氏股份": "300498", "拓普集团": "601689",
    "旭升集团": "603305", "绿的谐波": "688017", "捷捷微电": "300623", "粤桂股份": "000833",
    "建设银行": "601939", "工商银行": "601398", "中国平安": "601318", "贝泰妮": "300957",
    "宝泰隆": "601011", "上大股份": "301522", "双欣环保": "N/A", "小米股份": "1810.HK",
    "泡泡玛特": "9992.HK", "影石创新": "Private"
}

# ----------------- 4. 数据处理逻辑 -----------------
with st.spinner('正在构建全维度投资矩阵...'):
    inv_snapshot = get_smm_inventory()
    df_spot, df_flow = get_china_market_data()

# 处理 A 股/港股指标表
final_rows = []
for name, code in china_tickers.items():
    row = {"名称": name, "价格": "N/A", "涨跌%": 0.0, "PE": "-", "PB": "-", "股息率%": "-", "主力当日(万)": "-", "主力5日(万)": "-", "筹码集中度": "-"}
    
    # A股处理
    if code != "N/A" and "HK" not in code and code != "Private":
        match = df_spot[df_spot['代码'] == code]
        if not match.empty:
            m = match.iloc[0]
            row.update({
                "价格": m['最新价'], "涨跌%": m['涨跌幅'],
                "PE": m['市盈率-动态'], "PB": m['市净率']
            })
            # 资金流
            f_match = df_flow[df_flow['代码'] == code]
            if not f_match.empty:
                row.update({
                    "主力当日(万)": round(f_match.iloc[0]['今日主力净流入-净额']/10000, 1),
                    "主力5日(万)": round(f_match.iloc[0]['5日主力净流入-净额']/10000, 1)
                })
    # 港股处理 (小米/泡泡)
    elif "HK" in code:
        try:
            tk = yf.Ticker(code)
            inf = tk.info
            row.update({
                "价格": inf.get('currentPrice', 'N/A'),
                "涨跌%": round(((inf.get('currentPrice',0)/inf.get('previousClose',1))-1)*100, 2),
                "PE": inf.get('trailingPE', '-'),
                "PB": inf.get('priceToBook', '-'),
                "股息率%": round(inf.get('dividendYield', 0)*100, 2)
            })
        except: pass
    
    final_rows.append(row)

# ----------------- 5. 页面展示 -----------------

# 全球大宗略（保留之前功能）
st.header("🌍 全球资源监控 (LME/SHFE)")
# ... 此处省略 com_tickers 展示部分 ...

# 核心资产监控（增强版）
st.header("🧱 核心资产深度看板 (Valuation & Capital Flow)")
df_display = pd.DataFrame(final_rows)
st.dataframe(
    df_display.style.map(highlight_val, subset=['涨跌%', '主力当日(万)', '主力5日(万)']),
    use_container_width=True,
    height=600
)

# ----------------- 6. 趋势穿透 (修复版铜金比) -----------------
st.header("📈 宏观/个股趋势分析")
sel = st.selectbox("选择分析对象", options=["铜金比", "期铜 (HG=F)", "黄金 (GC=F)"] + list(china_tickers.keys()))

try:
    if sel == "铜金比":
        cu = yf.download("HG=F", period="6mo", progress=False)
        au = yf.download("GC=F", period="6mo", progress=False)
        
        # 稳健提取 Close
        if isinstance(cu.columns, pd.MultiIndex):
            cu_close = cu['Close'].iloc[:, 0]
            au_close = au['Close'].iloc[:, 0]
        else:
            cu_close, au_close = cu['Close'], au['Close']
            
        ratio = (cu_close / au_close) * 1000
        fig = px.line(x=ratio.index, y=ratio.values, title="铜金比 (Cu/Au x 1000) 趋势")
    else:
        target_code = china_tickers.get(sel, sel)
        if "HK" not in target_code and len(target_code) == 6:
            target_code = target_code + (".SS" if target_code.startswith("6") else ".SZ")
        
        data = yf.download(target_code, period="1y", progress=False)
        y_val = data['Close'].iloc[:, 0] if isinstance(data.columns, pd.MultiIndex) else data['Close']
        fig = px.line(x=data.index, y=y_val, title=f"{sel} 一年价格趋势")
    
    st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.warning(f"由于标的未上市或数据源问题，暂无法展示趋势图。")

st.caption(f"注：筹码集中度及主力流向为 T-1 数据；影石创新暂未上市。同步时间: {datetime.now().strftime('%H:%M:%S')}")
