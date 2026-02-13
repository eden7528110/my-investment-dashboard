import streamlit as st
import yfinance as yf
import akshare as ak
import pandas as pd
import plotly.express as px
from datetime import datetime
import time

# ----------------- 1. 样式与高亮 -----------------
def highlight_change(val):
    if pd.isna(val): return ''
    try:
        if isinstance(val, str): return ''
        val = float(val)
        if val > 0: return 'background-color: rgba(0, 255, 0, 0.1); color: #00ff00; font-weight: bold'
        elif val < 0: return 'background-color: rgba(255, 0, 0, 0.1); color: #ff4b4b; font-weight: bold'
    except: pass
    return ''

st.set_page_config(layout="wide", page_title="硬核资源仪表盘-终极版")
st.title("🛢️ 全球资源监控 & 穿透式库存看板")

# ----------------- 2. 增强型库存抓取引擎 (核心修复) -----------------
@st.cache_data(ttl=3600)
def get_inventory_data():
    """
    使用 '99期货' 接口，这是目前免费渠道中最稳定的库存源。
    涵盖：上海期货交易所(SHFE)、伦敦金属交易所(LME)
    """
    inventory_map = {}
    
    # 1. 抓取 LME 库存 (99期货源)
    try:
        df_lme = ak.futures_inventory_99(exchange="lme")
        # 清洗数据：通常包含 '名称', '库存量', '增减'
        if not df_lme.empty:
            for _, row in df_lme.iterrows():
                # 建立映射：LME铜 -> {'val': 12345, 'change': -50}
                key_name = row['名称'].replace("LME", "").strip() # 去掉前缀，只留 "铜"
                inventory_map[f"LME_{key_name}"] = f"{row['库存量']} ({row['增减']})"
    except Exception as e:
        print(f"LME Source Error: {e}")

    # 2. 抓取 SHFE 库存 (99期货源 或 交易所源)
    try:
        df_shfe = ak.futures_inventory_99(exchange="shfe") 
        if not df_shfe.empty:
            for _, row in df_shfe.iterrows():
                key_name = row['名称'].strip()
                inventory_map[f"SHFE_{key_name}"] = f"{row['库存量']} ({row['增减']})"
    except Exception as e:
        print(f"SHFE Source Error: {e}")
        
    return inventory_map

def find_stock_value(keyword, inv_data):
    """
    在清洗后的数据中查找，支持模糊匹配
    keyword: '铜', '铝', 'Gold'...
    """
    # 字典映射：将英文/代码关键字转为中文标准名
    name_map = {
        "铜": "铜", "Copper": "铜", "HG=F": "铜",
        "铝": "铝", "Aluminum": "铝", "ALI=F": "铝",
        "锌": "锌", "Zinc": "锌",
        "铅": "铅", "Lead": "铅",
        "镍": "镍", "Nickel": "镍",
        "锡": "锡", "Tin": "锡",
        "白银": "白银", "Silver": "白银", "SI=F": "白银",
        "黄金": "黄金", "Gold": "黄金", "GC=F": "黄金",
    }
    
    target_cn = name_map.get(keyword, keyword)
    
    lme_res = inv_data.get(f"LME_{target_cn}", "---")
    shfe_res = inv_data.get(f"SHFE_{target_cn}", "---")
    
    return lme_res, shfe_res

# 获取库存快照 (带加载提示)
with st.spinner('正在同步全球交易所库存数据...'):
    inventory_snapshot = get_inventory_data()

# ----------------- 3. 配置清单 -----------------
com_tickers = {
    "期铜 (HG=F)": {"yf": "HG=F", "key": "铜"},
    "期铝 (ALI=F)": {"yf": "ALI=F", "key": "铝"},
    "黄金 (GC=F)": {"yf": "GC=F", "key": "黄金"}, # 注：黄金库存通常较少变动
    "白银 (SI=F)": {"yf": "SI=F", "key": "白银"},
    "原油 (CL=F)": {"yf": "CL=F", "key": "原油"}, # 原油通常看EIA数据，交易所无库存
    "天然气 (NG=F)": {"yf": "NG=F", "key": "天然气"},
    "稀土 ETF (REMX)": {"yf": "REMX", "key": "稀土"}, # ETF无物理库存
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
    # 1. 匹配库存
    lme_stock, shfe_stock = find_stock_value(cfg["key"], inventory_snapshot)
    
    # 2. 抓取行情 (Yfinance)
    try:
        t = yf.Ticker(cfg["yf"])
        # 获取 fast info 以提高速度
        price = t.fast_info.last_price
        prev_close = t.fast_info.previous_close
        
        if price is None: # 回退到 history
             hist = t.history(period="2d")
             if not hist.empty:
                price = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2]
        
        if price:
            change = ((price / prev_close) - 1) * 100
            com_results.append({
                "项目": label, 
                "最新价": round(price, 2), 
                "涨跌幅%": round(change, 2),
                "全球库存 (LME/吨)": lme_stock,
                "中国库存 (SHFE/吨)": shfe_stock
            })
            if abs(change) > 3: alerts.append(f"🔥 {label} 剧烈波动：{round(change,2)}%！")
        else:
            raise Exception("No Data")
            
    except:
        com_results.append({
            "项目": label, "最新价": "N/A", "涨跌幅%": 0, 
            "全球库存 (LME/吨)": lme_stock, "中国库存 (SHFE/吨)": shfe_stock
        })

# ----------------- 5. 页面渲染 -----------------

# 警报
st.header("🚨 策略警报中心")
if alerts:
    for a in alerts: st.warning(a)
else: st.info("当前市场无异常价格爆发。")

# 全球看板
st.header("🌍 全球大宗商品 & 实时仓单快照")
st.markdown("*> 数据说明：库存格式为 `总量 (较昨日增减)`，数据源自99期货聚合接口。原油/ETF无物理交割库存。*")
df_com = pd.DataFrame(com_results)
st.dataframe(df_com.style.map(highlight_change, subset=["涨跌幅%"]), use_container_width=True)

# A股资源 (冗余链路)
st.header("🧱 A股龙头监控 (多源冗余链路)")
china_results = []
for name, codes in china_tickers.items():
    price, change, source = "N/A", 0, "连接中..."
    # 链路1: Yahoo Finance (海外最稳)
    try:
        yt = yf.Ticker(codes["yf"])
        price = yt.fast_info.last_price
        prev = yt.fast_info.previous_close
        if price:
            change = ((price / prev) - 1) * 100
            source = "Yahoo(Global)"
        else: raise Exception()
    except:
        # 链路2: Sina (备用)
        try:
            df = ak.stock_zh_a_hist(symbol=codes["ak"], period="daily").tail(2)
            if not df.empty:
                price = df.iloc[-1]['收盘']
                change = (price / df.iloc[0]['收盘'] - 1) * 100
                source = "Sina(Backup)"
        except: pass
    
    china_results.append({"关联标的": name, "价格": round(price, 2) if isinstance(price, float) else price, "日涨跌%": round(change, 2), "链路": source})

st.dataframe(pd.DataFrame(china_results).style.map(highlight_change, subset=["日涨跌%"]), use_container_width=True)

# 图表
st.header("📈 价格走势穿透")
sel = st.selectbox("选择商品", options=list(com_tickers.keys()))
try:
    p_data = yf.download(com_tickers[sel]["yf"], period="6mo", progress=False)
    if not p_data.empty:
        if isinstance(p_data.columns, pd.MultiIndex): p_data.columns = p_data.columns.get_level_values(0)
        st.plotly_chart(px.line(p_data, x=p_data.index, y="Close", title=f"{sel} 趋势图", template="plotly_dark"), use_container_width=True)
except: st.error("趋势图调取失败")

st.caption(f"系统运行中 | 最后同步: {datetime.now().strftime('%H:%M:%S')}")
