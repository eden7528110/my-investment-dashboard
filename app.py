import streamlit as st
import yfinance as yf
import akshare as ak
import pandas as pd
import plotly.express as px
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# ----------------- 1. 样式与高亮 -----------------
def highlight_change(val):
    if pd.isna(val) or isinstance(val, str): return ''
    try:
        val = float(val)
        if val > 0: return 'background-color: rgba(0, 255, 0, 0.1); color: #00ff00; font-weight: bold'
        elif val < 0: return 'background-color: rgba(255, 0, 0, 0.1); color: #ff4b4b; font-weight: bold'
    except: pass
    return ''

st.set_page_config(layout="wide", page_title="资源监控终极版")
st.title("🛢️ 全球资源监控 & 宏观走势系统 (SMM源+回溯)")

# ----------------- 2. SMM 爬虫 + 智能回溯引擎 -----------------
@st.cache_data(ttl=3600)
def get_combined_inventory():
    inventory_map = {}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    # 策略 A: 尝试爬取 SMM (metal.com)
    urls = {
        "LME": "https://www.metal.com/LME/Inventory",
        "SHFE": "https://www.metal.com/SHFE/Inventory"
    }
    for prefix, url in urls.items():
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            table = soup.find('table') # 抓取页面第一个表格
            if table:
                rows = table.find_all('tr')
                for row in rows[1:]:
                    cols = row.find_all(['td', 'th'])
                    if len(cols) >= 2:
                        name = cols[0].text.strip().replace('LME ', '').split('(')[0].strip()
                        val = cols[1].text.strip()
                        inventory_map[f"{prefix}_{name}"] = f"{val} (SMM)"
        except: pass

    # 策略 B: 回退至 AkShare 日期回溯逻辑 (如果SMM部分缺失)
    metal_keys = ["铜", "铝", "锌", "铅", "镍", "锡"]
    for i in range(7):
        if all(f"SHFE_{m}" in inventory_map for m in metal_keys): break
        check_date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        try:
            df_shfe = ak.futures_inventory_shfe(date=check_date)
            if not df_shfe.empty:
                for _, row in df_shfe.iterrows():
                    m_name = row['品种'].strip()
                    if f"SHFE_{m_name}" not in inventory_map:
                        inventory_map[f"SHFE_{m_name}"] = f"{row['合计']} ({check_date[4:6]}-{check_date[6:8]})"
                break
        except: continue
    return inventory_map

def find_stock_val(keyword, inv_data):
    # 建立多语言映射
    mapping = {"铜": ["Copper", "铜", "HG=F"], "铝": ["Aluminum", "铝", "ALI=F"], "黄金": ["Gold", "黄金"], "白银": ["Silver", "白银"]}
    target = keyword
    for k, v in mapping.items():
        if keyword in v: target = k; break
    
    lme = "---"
    for k, v in inv_data.items():
        if k.startswith("LME_") and target in k: lme = v; break
    shfe = "---"
    for k, v in inv_data.items():
        if k.startswith("SHFE_") and target in k: shfe = v; break
    return lme, shfe

with st.spinner('正在同步全球库存(SMM)与价格数据...'):
    inventory_snapshot = get_combined_inventory()

# ----------------- 3. 配置 -----------------
com_tickers = {
    "期铜 (HG=F)": {"yf": "HG=F", "key": "铜"},
    "期铝 (ALI=F)": {"yf": "ALI=F", "key": "铝"},
    "黄金 (GC=F)": {"yf": "GC=F", "key": "黄金"},
    "白银 (SI=F)": {"yf": "SI=F", "key": "白银"},
    "原油 (CL=F)": {"yf": "CL=F", "key": "原油"}
}

# ----------------- 4. 数据合并 -----------------
com_results = []
prices_for_ratio = {"HG=F": None, "GC=F": None}

for label, cfg in com_tickers.items():
    lme, shfe = find_stock_val(cfg["key"], inventory_snapshot)
    try:
        t = yf.Ticker(cfg["yf"])
        price = t.fast_info.last_price
        change = ((price / t.fast_info.previous_close) - 1) * 100
        com_results.append({"项目": label, "最新价": round(price, 2), "涨跌幅%": round(change, 2), "全球库存 (LME)": lme, "中国库存 (SHFE)": shfe, "ticker": cfg["yf"]})
        if cfg["yf"] in prices_for_ratio: prices_for_ratio[cfg["yf"]] = price
    except: pass

if prices_for_ratio["HG=F"] and prices_for_ratio["GC=F"]:
    rv = (prices_for_ratio["HG=F"] / prices_for_ratio["GC=F"]) * 1000
    com_results.append({"项目": "📈 铜金比 (Cu/Au x 1000)", "最新价": round(rv, 4), "涨跌幅%": "宏观指标", "全球库存 (LME)": "---", "中国库存 (SHFE)": "---", "ticker": "RATIO"})

# ----------------- 5. 页面展示 -----------------
st.header("🌍 全球大宗商品看板")
df_com = pd.DataFrame(com_results)
st.dataframe(df_com.drop(columns=['ticker']).style.map(highlight_change, subset=["涨跌幅%"]), use_container_width=True)

# ----------------- 6. 趋势分析 (修复 KeyError: 'Close_cu') -----------------
st.header("📊 历史趋势分析")
opts = {cfg["yf"]: label for label, cfg in com_tickers.items()}
opts["RATIO"] = "📈 铜金比 (Copper/Gold Ratio)"
sel = st.selectbox("选择要查看趋势的标的", options=list(opts.keys()), format_func=lambda x: opts[x])

try:
    if sel == "RATIO":
        # 获取6个月数据
        d_cu = yf.download("HG=F", period="6mo", progress=False)[['Close']]
        d_au = yf.download("GC=F", period="6mo", progress=False)[['Close']]
        
        # 关键修复：处理 MultiIndex
        d_cu.columns = ['Close_cu']
        d_au.columns = ['Close_au']
        
        # 合并
        r_df = pd.merge(d_cu, d_au, left_index=True, right_index=True)
        r_df['ratio'] = (r_df['Close_cu'] / r_df['Close_au']) * 1000
        
        fig = px.line(r_df, x=r_df.index, y="ratio", title="铜金比 6个月趋势 (宏观经济风向标)", template="plotly_dark")
    else:
        h_data = yf.download(sel, period="6mo", progress=False)[['Close']]
        h_data.columns = ['Price']
        fig = px.line(h_data, x=h_data.index, y="Price", title=f"{opts[sel]} 趋势", template="plotly_dark")
    
    st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.error(f"图表生成失败: {str(e)}")

st.caption(f"最后同步: {datetime.now().strftime('%H:%M:%S')} | 已修复铜金比数据对齐逻辑")
