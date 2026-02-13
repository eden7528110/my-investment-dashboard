import streamlit as st
import yfinance as yf
import akshare as ak
import pandas as pd
import plotly.express as px
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# ----------------- 1. 配置与页面设置 -----------------
st.set_page_config(layout="wide", page_title="硬核投资决策仪表盘")
st.title("🛡️ 核心资产全维度看板 (含资金流/分红/估值)")

def highlight_flow(val):
    if not isinstance(val, (int, float)): return ''
    return 'color: #00ff00' if val > 0 else 'color: #ff4b4b' if val < 0 else ''

# ----------------- 2. 增强型数据抓取引擎 -----------------

@st.cache_data(ttl=3600)
def get_inventory_all():
    """回溯 10 天查找最新库存"""
    res = {}
    for i in range(10):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        try:
            df = ak.futures_inventory_shfe(date=d)
            if not df.empty:
                for _, row in df.iterrows():
                    res[f"SHFE_{row['品种'].strip()}"] = f"{row['合计']} ({d[4:6]}-{d[6:8]})"
                break
        except: continue
    return res

@st.cache_data(ttl=1200)
def get_full_market_data():
    """多源获取 A 股数据"""
    try:
        # 实时行情 + PE/PB
        df_spot = ak.stock_zh_a_spot_em()
        # 主力资金流 (含 5日, 20日)
        df_flow = ak.stock_individual_fund_flow_rank_em()
        return df_spot, df_flow
    except:
        return pd.DataFrame(), pd.DataFrame()

# ----------------- 3. 标的资产清单 -----------------
# 定义需要监控的股票清单
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

# ----------------- 4. 数据核心计算 -----------------
with st.spinner('正在同步数据矩阵，请稍候...'):
    inv_data = get_inventory_all()
    df_spot, df_flow = get_full_market_data()

# 整合列表
china_results = []
for name, yf_code in stock_list.items():
    pure_code = yf_code.split('.')[0]
    # 默认值
    item = {
        "名称": name, "最新价": "N/A", "涨跌%": 0.0, "PE(动)": "-", "PB": "-",
        "主力当日(万)": 0, "主力5日(万)": 0, "主力20日(万)": 0, "股息率%": "-"
    }
    
    # 尝试从 akshare 获取 (国内源快)
    if not df_spot.empty and '代码' in df_spot.columns:
        match = df_spot[df_spot['代码'] == pure_code]
        if not match.empty:
            m = match.iloc[0]
            item.update({
                "最新价": m['最新价'], "涨跌%": m['涨跌幅'],
                "PE(动)": m['市盈率-动态'], "PB": m['市净率']
            })
    
    # 尝试补充主力资金
    if not df_flow.empty and '代码' in df_flow.columns:
        f_match = df_flow[df_flow['代码'] == pure_code]
        if not f_match.empty:
            fm = f_match.iloc[0]
            item.update({
                "主力当日(万)": round(fm['今日主力净流入-净额']/10000, 0),
                "主力5日(万)": round(fm['5日主力净流入-净额']/10000, 0),
                "主力20日(万)": round(fm['20日主力净流入-净额']/10000, 0)
            })
            
    # 针对港股或失效标的，通过 yfinance 兜底获取基本面
    if item["最新价"] == "N/A" or "HK" in yf_code:
        try:
            tk = yf.Ticker(yf_code)
            inf = tk.info
            item.update({
                "最新价": inf.get('currentPrice', item["最新价"]),
                "PE(动)": inf.get('trailingPE', "-"),
                "PB": inf.get('priceToBook', "-"),
                "股息率%": round(inf.get('dividendYield', 0)*100, 2) if inf.get('dividendYield') else "-"
            })
        except: pass

    china_results.append(item)

# ----------------- 5. 页面渲染 -----------------

st.header("📊 核心资产全维度监控")
st.markdown("> **注**：影石创新、双欣环保暂未上市；主力资金数据单位为万元；库存非当日则显示具体日期。")

# A/H 股大数据表
df_final = pd.DataFrame(china_results)
st.dataframe(
    df_final.style.map(highlight_flow, subset=["涨跌%", "主力当日(万)", "主力5日(万)", "主力20日(万)"]),
    use_container_width=True, height=500
)

# 库存状态
with st.expander("📦 交易所库存快照 (T-10 自动回溯)"):
    cols = st.columns(4)
    metals = ["铜", "铝", "锌", "铅"]
    for idx, m in enumerate(metals):
        cols[idx].metric(f"SHFE {m} 库存", inv_data.get(f"SHFE_{m}", "无数据"))

# ----------------- 6. 趋势图修复 (铜金比专用) -----------------
st.header("📈 价格走势穿透")
sel = st.selectbox("选择分析标的", options=["铜金比 (Copper/Gold Ratio)"] + list(stock_list.keys()))

try:
    if "铜金比" in sel:
        cu = yf.download("HG=F", period="1y", progress=False)
        au = yf.download("GC=F", period="1y", progress=False)
        
        # 彻底解决 MultiIndex 导致的 Close_cu 缺失问题
        c_p = cu['Close'].values.flatten()
        a_p = au['Close'].values.flatten()
        ratio = (c_p / a_p) * 1000
        
        fig = px.line(x=cu.index, y=ratio, title="宏观经济心跳：铜金比 (6个月趋势)", template="plotly_dark")
        fig.update_yaxes(title="Cu/Au Ratio")
    else:
        code = stock_list[sel]
        hist = yf.download(code, period="1y", progress=False)
        # 兼容多级索引
        p_vals = hist['Close'].values.flatten()
        fig = px.line(x=hist.index, y=p_vals, title=f"{sel} 历史价格 (1年)", template="plotly_dark")

    st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.warning(f"由于网络或标的状态(未上市)，图表无法生成。详情: {e}")

st.caption(f"最后刷新: {datetime.now().strftime('%H:%M:%S')} | 链路状态: 已修复 KeyError 并集成资金流。")
