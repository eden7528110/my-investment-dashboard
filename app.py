import streamlit as st
import yfinance as yf
import akshare as ak
import pandas as pd
import plotly.express as px
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# ----------------- 1. 样式与初始化 -----------------
st.set_page_config(layout="wide", page_title="硬核全能资源看板")
st.title("🛢️ 全球资源监控 & 核心资产全维度看板")

def highlight_flow(val):
    if not isinstance(val, (int, float)): return ''
    return 'color: #00ff00' if val > 0 else 'color: #ff4b4b' if val < 0 else ''

# ----------------- 2. 增强型数据抓取引擎 -----------------

@st.cache_data(ttl=3600)
def get_inventory_snapshot():
    """整合 SMM 爬虫与 AkShare 回溯逻辑获取仓单"""
    inv_map = {}
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # 策略 A: SMM (metal.com)
    urls = {"LME": "https://www.metal.com/LME/Inventory", "SHFE": "https://www.metal.com/SHFE/Inventory"}
    for prefix, url in urls.items():
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(resp.text, 'html.parser')
            table = soup.find('table')
            if table:
                for row in table.find_all('tr')[1:]:
                    cols = row.find_all(['td', 'th'])
                    if len(cols) >= 2:
                        name = cols[0].text.strip().replace('LME ', '').split('(')[0].strip()
                        inv_map[f"{prefix}_{name}"] = f"{cols[1].text.strip()} (SMM)"
        except: pass

    # 策略 B: AkShare 补漏回溯
    for i in range(7):
        date_str = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        try:
            df = ak.futures_inventory_shfe(date=date_str)
            if not df.empty:
                for _, row in df.iterrows():
                    m_name = row['品种'].strip()
                    if f"SHFE_{m_name}" not in inv_map:
                        inv_map[f"SHFE_{m_name}"] = f"{row['合计']} ({date_str[4:6]}-{date_str[6:8]})"
                break
        except: continue
    return inv_map

@st.cache_data(ttl=1200)
def get_market_indicators():
    """获取 A 股行情及资金流排名，加入空表检查预防报错"""
    try:
        df_spot = ak.stock_zh_a_spot_em()
        df_flow = ak.stock_individual_fund_flow_rank_em()
        return df_spot, df_flow
    except:
        return pd.DataFrame(), pd.DataFrame()

# ----------------- 3. 监控标的配置 -----------------
# 大宗商品清单
com_tickers = {
    "期铜 (HG=F)": {"yf": "HG=F", "key": "铜"},
    "期铝 (ALI=F)": {"yf": "ALI=F", "key": "铝"},
    "黄金 (GC=F)": {"yf": "GC=F", "key": "黄金"},
    "白银 (SI=F)": {"yf": "SI=F", "key": "白银"},
    "原油 (CL=F)": {"yf": "CL=F", "key": "原油"}
}

# A股/港股全名单
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

# ----------------- 4. 数据计算逻辑 -----------------
with st.spinner('正在构建仓单与资金流矩阵...'):
    inv_snapshot = get_inventory_snapshot()
    df_spot, df_flow = get_market_indicators()

# A. 大宗仓单表计算
com_results = []
prices_for_ratio = {"HG=F": None, "GC=F": None}
for label, cfg in com_tickers.items():
    try:
        t = yf.Ticker(cfg["yf"])
        p = t.fast_info.last_price
        c = ((p / t.fast_info.previous_close) - 1) * 100
        com_results.append({
            "项目": label, "最新价": round(p, 2), "涨跌幅%": round(c, 2),
            "全球库存(LME)": inv_snapshot.get(f"LME_{cfg['key']}", "---"),
            "中国库存(SHFE)": inv_snapshot.get(f"SHFE_{cfg['key']}", "---"),
            "ticker": cfg["yf"]
        })
        if cfg["yf"] in prices_for_ratio: prices_for_ratio[cfg["yf"]] = p
    except: pass

# 插入铜金比
if prices_for_ratio["HG=F"] and prices_for_ratio["GC=F"]:
    rv = (prices_for_ratio["HG=F"] / prices_for_ratio["GC=F"]) * 1000
    com_results.append({"项目": "📈 铜金比", "最新价": round(rv, 4), "涨跌幅%": "宏观指标", "全球库存(LME)": "---", "中国库存(SHFE)": "---", "ticker": "RATIO"})

# B. 核心资产表计算
china_results = []
for name, yf_code in stock_list.items():
    pure_code = yf_code.split('.')[0]
    row = {"名称": name, "价格": "N/A", "涨跌%": 0.0, "PE(动)": "-", "PB": "-", "主力当日(万)": 0, "主力5日(万)": 0, "股息率%": "-"}
    
    # 国内源匹配 (带 KeyError 防护)
    if not df_spot.empty and '代码' in df_spot.columns:
        match = df_spot[df_spot['代码'] == pure_code]
        if not match.empty:
            m = match.iloc[0]
            row.update({"价格": m['最新价'], "涨跌%": m['涨跌幅'], "PE(动)": m['市盈率-动态'], "PB": m['市净率']})
    
    if not df_flow.empty and '代码' in df_flow.columns:
        f_match = df_flow[df_flow['代码'] == pure_code]
        if not f_match.empty:
            fm = f_match.iloc[0]
            row.update({
                "主力当日(万)": round(fm['今日主力净流入-净额']/10000, 0),
                "主力5日(万)": round(fm['5日主力净流入-净额']/10000, 0)
            })
    
    # 港股或缺失项通过 yf 补全
    if row["价格"] == "N/A" or "HK" in yf_code:
        try:
            inf = yf.Ticker(yf_code).info
            row.update({
                "价格": inf.get('currentPrice', "N/A"), "PE(动)": inf.get('trailingPE', "-"),
                "PB": inf.get('priceToBook', "-"), "股息率%": round(inf.get('dividendYield', 0)*100, 2) if inf.get('dividendYield') else "-"
            })
        except: pass
    china_results.append(row)

# ----------------- 5. 页面渲染 -----------------

# 第一部分：大宗商品仓单
st.header("🌍 全球大宗商品 & 实时仓单快照")
st.dataframe(pd.DataFrame(com_results).drop(columns=['ticker']).style.map(highlight_flow, subset=['涨跌幅%']), use_container_width=True)

# 第二部分：核心资产深度看板
st.header("🧱 核心资产监控 (含资金流/基本面)")
df_final = pd.DataFrame(china_results)
st.dataframe(
    df_final.style.map(highlight_flow, subset=['涨跌%', '主力当日(万)', '主力5日(万)']),
    use_container_width=True, height=500
)

# 第三部分：趋势分析 (铜金比修复)

st.header("📈 价格走势穿透")
sel = st.selectbox("选择要分析的标的", options=["铜金比 (Copper/Gold Ratio)"] + list(stock_list.keys()))

try:
    if "铜金比" in sel:
        cu = yf.download("HG=F", period="1y", progress=False)
        au = yf.download("GC=F", period="1y", progress=False)
        # 修复多级索引：通过 values.flatten() 确保拿到底层 Series
        c_p = cu['Close'].values.flatten()
        a_p = au['Close'].values.flatten()
        ratio = (c_p / a_p) * 1000
        fig = px.line(x=cu.index, y=ratio, title="宏观经济风向标：铜金比 (1年趋势)", template="plotly_dark")
    else:
        code = stock_list[sel]
        hist = yf.download(code, period="1y", progress=False)
        p_vals = hist['Close'].values.flatten()
        fig = px.line(x=hist.index, y=p_vals, title=f"{sel} 价格走势 (1年)", template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.warning(f"趋势图生成受限: {e}")

st.caption(f"数据实时同步 | 最后更新: {datetime.now().strftime('%H:%M:%S')} | 已集成 SMM/资金流/PE/PB")
