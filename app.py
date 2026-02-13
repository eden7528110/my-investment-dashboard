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

st.set_page_config(layout="wide", page_title="硬核全能资源仪表盘")
st.title("🚀 全球资源 & A股/港股核心标的监控系统")

# ----------------- 2. 智能库存回溯引擎 (SMM + Akshare) -----------------
@st.cache_data(ttl=3600)
def get_combined_inventory():
    inventory_map = {}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    urls = {"LME": "https://www.metal.com/LME/Inventory", "SHFE": "https://www.metal.com/SHFE/Inventory"}
    
    for prefix, url in urls.items():
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            table = soup.find('table') 
            if table:
                rows = table.find_all('tr')
                for row in rows[1:]:
                    cols = row.find_all(['td', 'th'])
                    if len(cols) >= 2:
                        name = cols[0].text.strip().replace('LME ', '').split('(')[0].strip()
                        inventory_map[f"{prefix}_{name}"] = f"{cols[1].text.strip()} (SMM)"
        except: pass

    # 回溯逻辑
    for i in range(7):
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
    mapping = {"铜": ["Copper", "铜", "HG=F"], "铝": ["Aluminum", "铝", "ALI=F"], "黄金": ["Gold", "黄金"], "白银": ["Silver", "白银"]}
    target = keyword
    for k, v in mapping.items():
        if keyword in v: target = k; break
    lme = inv_data.get(f"LME_{target}", "---")
    shfe = inv_data.get(f"SHFE_{target}", "---")
    return lme, shfe

with st.spinner('正在同步全球交易所数据...'):
    inventory_snapshot = get_combined_inventory()

# ----------------- 3. 增强型标的配置 (A股/港股/大宗) -----------------
com_tickers = {
    "期铜 (HG=F)": {"yf": "HG=F", "key": "铜"},
    "期铝 (ALI=F)": {"yf": "ALI=F", "key": "铝"},
    "黄金 (GC=F)": {"yf": "GC=F", "key": "黄金"},
    "白银 (SI=F)": {"yf": "SI=F", "key": "白银"},
    "原油 (CL=F)": {"yf": "CL=F", "key": "原油"}
}

# 包含了你要求的所有标的
china_tickers = {
    "中钨高新": {"yf": "000657.SZ"}, "宝武镁业": {"yf": "002182.SZ"}, 
    "中国铝业": {"yf": "601600.SS"}, "洛阳钼业": {"yf": "603993.SS"},
    "紫金矿业": {"yf": "601899.SS"}, "北方稀土": {"yf": "600111.SS"},
    "江西铜业": {"yf": "600362.SS"}, "中国神华": {"yf": "601088.SS"},
    "宁德时代": {"yf": "300750.SZ"}, "牧原股份": {"yf": "002714.SZ"},
    "温氏股份": {"yf": "300498.SZ"}, "拓普集团": {"yf": "601689.SS"},
    "旭升集团": {"yf": "603305.SS"}, "绿的谐波": {"yf": "688017.SS"},
    "捷捷微电": {"yf": "300623.SZ"}, "粤桂股份": {"yf": "000833.SZ"},
    "建设银行": {"yf": "601939.SS"}, "工商银行": {"yf": "601398.SS"},
    "中国平安": {"yf": "601318.SS"}, "贝泰妮":   {"yf": "300957.SZ"},
    "宝泰隆":   {"yf": "601011.SS"}, "上大股份": {"yf": "301522.SZ"},
    "双欣环保": {"yf": "双欣环保.SS"}, # 注：部分新股或环保票如未上市会显示N/A
    "小米股份": {"yf": "1810.HK"},   "泡泡玛特": {"yf": "9992.HK"},
    "影石创新": {"yf": "INSTA360.PRIVATE"} # 未上市标的
}

# ----------------- 4. 数据计算 -----------------
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
    com_results.append({"项目": "📈 铜金比", "最新价": round(rv, 4), "涨跌幅%": "宏观指标", "全球库存 (LME)": "---", "中国库存 (SHFE)": "---", "ticker": "RATIO"})

# ----------------- 5. 页面渲染 -----------------
st.header("🌍 全球大宗商品看板")
st.dataframe(pd.DataFrame(com_results).drop(columns=['ticker']).style.map(highlight_change, subset=["涨跌幅%"]), use_container_width=True)

st.header("🧱 核心资产监控 (A股/港股)")
china_results = []
for name, cfg in china_tickers.items():
    price, change, source = "N/A", 0, "Wait"
    try:
        yt = yf.Ticker(cfg["yf"])
        price = yt.fast_info.last_price
        if price:
            change = ((price / yt.fast_info.previous_close) - 1) * 100
            source = "Global"
        else:
            # 针对部分标的的回退逻辑
            df = ak.stock_zh_a_spot_em()
            match = df[df['名称'] == name]
            if not match.empty:
                price, change, source = match.iloc[0]['最新价'], match.iloc[0]['涨跌幅'], "Domestic"
    except: pass
    china_results.append({"名称": name, "最新价": price, "涨跌幅%": round(change, 2), "数据源": source})

st.dataframe(pd.DataFrame(china_results).style.map(highlight_change, subset=["涨跌幅%"]), use_container_width=True)

# ----------------- 6. 历史趋势 -----------------
st.header("📈 趋势穿透对比")
plot_opts = {cfg["yf"]: label for label, cfg in com_tickers.items()}
plot_opts["RATIO"] = "📈 铜金比"
# 同时也允许查看A股走势
for n, c in china_tickers.items(): plot_opts[c["yf"]] = n

sel = st.selectbox("选择对比基准", options=list(plot_opts.keys()), format_func=lambda x: plot_opts[x])

try:
    if sel == "RATIO":
        d_cu = yf.download("HG=F", period="6mo", progress=False)[['Close']]
        d_au = yf.download("GC=F", period="6mo", progress=False)[['Close']]
        d_cu.columns, d_au.columns = ['Close_cu'], ['Close_au']
        r_df = pd.merge(d_cu, d_au, left_index=True, right_index=True)
        r_df['ratio'] = (r_df['Close_cu'] / r_df['Close_au']) * 1000
        fig = px.line(r_df, x=r_df.index, y="ratio", title="铜金比趋势", template="plotly_dark")
    else:
        h_data = yf.download(sel, period="6mo", progress=False)[['Close']]
        h_data.columns = ['Price']
        fig = px.line(h_data, x=h_data.index, y="Price", title=f"{plot_opts[sel]} 趋势分析", template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.error(f"图表加载失败: {str(e)}")

st.caption(f"系统运行中 | 最后刷新: {datetime.now().strftime('%H:%M:%S')}")
