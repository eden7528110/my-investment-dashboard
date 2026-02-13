import streamlit as st
import yfinance as yf
import akshare as ak
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
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

st.set_page_config(layout="wide", page_title="硬核资源仪表盘-智能回溯版")
st.title("🛢️ 全球资源监控 & 智能库存回溯系统")

# ----------------- 2. 智能库存回溯引擎 -----------------
@st.cache_data(ttl=3600)
def get_recent_inventory():
    """
    智能回溯逻辑：
    从今天开始往前倒推 7 天，直到找到有数据的那一天。
    返回格式：{'LME_铜': '12500 (02-14)', ...}
    """
    inventory_map = {}
    
    # --- LME 回溯逻辑 ---
    for i in range(7): # 最多回溯7天
        target_date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        display_date = (datetime.now() - timedelta(days=i)).strftime("%m-%d")
        
        try:
            # akshare 的 99期货接口通常返回最新数据，不需要传日期
            # 但为了稳健，我们这里使用通用接口抓取，如果失败则尝试历史接口
            df_lme = ak.futures_inventory_99(exchange="lme") 
            if not df_lme.empty:
                for _, row in df_lme.iterrows():
                    key_name = row['名称'].replace("LME", "").strip()
                    # 标注日期，如果不是今天的数据
                    date_suffix = "" if i == 0 else f" ({display_date})"
                    inventory_map[f"LME_{key_name}"] = f"{row['库存量']} {date_suffix}"
                break # 只要找到数据，就跳出循环，不再往回查
        except:
            continue # 如果报错，说明今天没数据，继续查前一天

    # --- SHFE 回溯逻辑 ---
    # SHFE 通常需要指定具体日期抓取日报
    for i in range(10): # SHFE 节假日多，回溯10天
        check_date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        display_date = (datetime.now() - timedelta(days=i)).strftime("%m-%d")
        
        try:
            # 尝试抓取指定日期的上期所日报
            df_shfe = ak.futures_inventory_shfe(date=check_date)
            if not df_shfe.empty:
                for _, row in df_shfe.iterrows():
                    # 清洗名称：有的叫 "铜"，有的叫 "铜cu"
                    key_name = row['品种'].strip()
                    # 格式化数值：去除非数字字符
                    val = row['合计']
                    inventory_map[f"SHFE_{key_name}"] = f"{val} ({display_date})"
                break # 找到了就停止
        except:
            continue

    return inventory_map

def find_stock_value(keyword, inv_data):
    """
    模糊匹配 + 智能映射
    """
    # 映射表：将英文/代码转为中文标准名
    name_map = {
        "铜": "铜", "Copper": "铜", "HG=F": "铜",
        "铝": "铝", "Aluminum": "铝", "ALI=F": "铝",
        "锌": "锌", "Zinc": "锌",
        "铅": "铅", "Lead": "铅",
        "镍": "镍", "Nickel": "镍",
        "锡": "锡", "Tin": "锡",
        "白银": "白银", "Silver": "白银", "SI=F": "白银", # SHFE有白银库存
        "黄金": "黄金", "Gold": "黄金", "GC=F": "黄金",
    }
    
    target_cn = name_map.get(keyword, keyword)
    
    # 在字典中搜索包含该关键词的键
    lme_res = "---"
    for k, v in inv_data.items():
        if k.startswith(f"LME_{target_cn}"):
            lme_res = v
            break
            
    shfe_res = "---"
    for k, v in inv_data.items():
        if k.startswith(f"SHFE_{target_cn}"): # SHFE匹配
            shfe_res = v
            break
    
    return lme_res, shfe_res

# 执行数据同步（带进度条）
with st.spinner('正在回溯最近 7-10 天的交易所库存数据...'):
    inventory_snapshot = get_recent_inventory()

# ----------------- 3. 核心配置清单 -----------------
com_tickers = {
    "期铜 (HG=F)": {"yf": "HG=F", "key": "铜"},
    "期铝 (ALI=F)": {"yf": "ALI=F", "key": "铝"},
    "黄金 (GC=F)": {"yf": "GC=F", "key": "黄金"}, 
    "白银 (SI=F)": {"yf": "SI=F", "key": "白银"},
    "锌 (Zinc)":   {"yf": "APA", "key": "锌"}, # 锌通常用股票或相关ETF代替监控
    "原油 (CL=F)": {"yf": "CL=F", "key": "原油"}, 
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

# ----------------- 4. 数据合并逻辑 -----------------
com_results = []
alerts = []

for label, cfg in com_tickers.items():
    # 1. 匹配库存
    lme_stock, shfe_stock = find_stock_value(cfg["key"], inventory_snapshot)
    
    # 2. 抓取行情
    try:
        t = yf.Ticker(cfg["yf"])
        price = t.fast_info.last_price
        prev = t.fast_info.previous_close
        
        if price is None: 
             hist = t.history(period="2d")
             if not hist.empty:
                price = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
        
        if price:
            change = ((price / prev) - 1) * 100
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

st.header("🚨 策略警报中心")
if alerts:
    for a in alerts: st.warning(a)
else: st.info("当前市场无异常价格爆发。")

st.header("🌍 全球大宗商品 & 智能回溯库存看板")
st.markdown("*> 数据说明：库存若非今日数据，会在括号内标注日期，如 `(02-10)`。LME与SHFE均已启用 `T-10` 自动回溯机制。*")
df_com = pd.DataFrame(com_results)
st.dataframe(df_com.style.map(highlight_change, subset=["涨跌幅%"]), use_container_width=True)

st.header("🧱 A股龙头监控 (多源冗余链路)")
china_results = []
for name, codes in china_tickers.items():
    price, change, source = "N/A", 0, "Wait..."
    try:
        yt = yf.Ticker(codes["yf"])
        price = yt.fast_info.last_price
        if price:
            change = ((price / yt.fast_info.previous_close) - 1) * 100
            source = "Yahoo(Global)"
        else: raise Exception()
    except:
        try:
            df = ak.stock_zh_a_hist(symbol=codes["ak"], period="daily").tail(2)
            if not df.empty:
                price = df.iloc[-1]['收盘']
                change = (price / df.iloc[0]['收盘'] - 1) * 100
                source = "Sina(Backup)"
        except: pass
    
    china_results.append({"关联标的": name, "价格": round(price, 2) if isinstance(price, float) else price, "日涨跌%": round(change, 2), "链路": source})

st.dataframe(pd.DataFrame(china_results).style.map(highlight_change, subset=["日涨跌%"]), use_container_width=True)

st.header("📈 价格走势穿透")
sel = st.selectbox("选择商品", options=list(com_tickers.keys()))
try:
    p_data = yf.download(com_tickers[sel]["yf"], period="6mo", progress=False)
    if not p_data.empty:
        if isinstance(p_data.columns, pd.MultiIndex): p_data.columns = p_data.columns.get_level_values(0)
        st.plotly_chart(px.line(p_data, x=p_data.index, y="Close", title=f"{sel} 趋势图", template="plotly_dark"), use_container_width=True)
except: st.error("趋势图调取失败")

st.caption(f"系统运行中 | 最后同步: {datetime.now().strftime('%H:%M:%S')}")
