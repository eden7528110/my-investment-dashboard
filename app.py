import streamlit as st
import yfinance as yf
import akshare as ak
import pandas as pd
import plotly.express as px
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

st.set_page_config(layout="wide", page_title="硬核资源仪表盘-全功能版")
st.title("🛢️ 全球资源监控 & 宏观走势穿透系统")

# ----------------- 2. 智能库存回溯引擎 -----------------
@st.cache_data(ttl=3600)
def get_recent_inventory():
    inventory_map = {}
    # LME 回溯
    try:
        df_lme = ak.futures_inventory_99(exchange="lme") 
        if not df_lme.empty:
            for _, row in df_lme.iterrows():
                key_name = row['名称'].replace("LME", "").strip()
                inventory_map[f"LME_{key_name}"] = f"{row['库存量']}"
    except: pass

    # SHFE 回溯 (查询最近 7 天)
    for i in range(7):
        check_date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        display_date = (datetime.now() - timedelta(days=i)).strftime("%m-%d")
        try:
            df_shfe = ak.futures_inventory_shfe(date=check_date)
            if not df_shfe.empty:
                for _, row in df_shfe.iterrows():
                    inventory_map[f"SHFE_{row['品种'].strip()}"] = f"{row['合计']} ({display_date})"
                break
        except: continue
    return inventory_map

def find_stock_value(keyword, inv_data):
    name_map = {"铜": "铜", "HG=F": "铜", "铝": "铝", "ALI=F": "铝", "黄金": "黄金", "GC=F": "黄金", "白银": "白银", "SI=F": "白银"}
    target_cn = name_map.get(keyword, keyword)
    lme = inv_data.get(f"LME_{target_cn}", "---")
    shfe = inv_data.get(f"SHFE_{target_cn}", "---")
    return lme, shfe

with st.spinner('正在同步全球库存与宏观数据...'):
    inventory_snapshot = get_recent_inventory()

# ----------------- 3. 配置清单 -----------------
com_tickers = {
    "期铜 (HG=F)": {"yf": "HG=F", "key": "铜"},
    "期铝 (ALI=F)": {"yf": "ALI=F", "key": "铝"},
    "黄金 (GC=F)": {"yf": "GC=F", "key": "黄金"},
    "白银 (SI=F)": {"yf": "SI=F", "key": "白银"},
    "原油 (CL=F)": {"yf": "CL=F", "key": "原油"},
    "天然气 (NG=F)": {"yf": "NG=F", "key": "天然气"}
}

# ----------------- 4. 数据合并与比率计算 -----------------
com_results = []
prices_for_ratio = {"HG=F": None, "GC=F": None}

for label, cfg in com_tickers.items():
    lme_stock, shfe_stock = find_stock_value(cfg["key"], inventory_snapshot)
    try:
        t = yf.Ticker(cfg["yf"])
        price = t.fast_info.last_price
        prev = t.fast_info.previous_close
        if price:
            change = ((price / prev) - 1) * 100
            com_results.append({"项目": label, "最新价": round(price, 2), "涨跌幅%": round(change, 2), "全球库存 (LME)": lme_stock, "中国库存 (SHFE)": shfe_stock, "ticker": cfg["yf"]})
            if cfg["yf"] in prices_for_ratio: prices_for_ratio[cfg["yf"]] = price
    except: pass

# 添加铜金比到表格
if prices_for_ratio["HG=F"] and prices_for_ratio["GC=F"]:
    ratio_val = (prices_for_ratio["HG=F"] / prices_for_ratio["GC=F"]) * 1000
    com_results.append({"项目": "📈 铜金比 (Cu/Au x 1000)", "最新价": round(ratio_val, 4), "涨跌幅%": "宏观指标", "全球库存 (LME)": "---", "中国库存 (SHFE)": "---", "ticker": "RATIO"})

# ----------------- 5. 页面渲染 -----------------
st.header("🌍 全球大宗商品看板")
df_com = pd.DataFrame(com_results)
st.dataframe(df_com.drop(columns=['ticker']).style.map(highlight_change, subset=["涨跌幅%"]), use_container_width=True)

# ----------------- 6. 趋势穿透 (核心修复：支持铜金比绘图) -----------------
st.header("📊 历史趋势分析")
plot_options = {cfg["yf"]: label for label, cfg in com_tickers.items()}
plot_options["RATIO"] = "📈 铜金比 (Copper/Gold Ratio)"

selected_plot = st.selectbox("选择要查看趋势的标的", options=list(plot_options.keys()), format_func=lambda x: plot_options[x])

try:
    if selected_plot == "RATIO":
        # 下载两份数据进行计算
        data_cu = yf.download("HG=F", period="6mo", progress=False)['Close']
        data_au = yf.download("GC=F", period="6mo", progress=False)['Close']
        
        # 处理 MultiIndex 
        if isinstance(data_cu, pd.DataFrame): data_cu = data_cu.iloc[:, 0]
        if isinstance(data_au, pd.DataFrame): data_au = data_au.iloc[:, 0]
        
        # 合并并计算比率
        ratio_df = pd.merge(data_cu, data_au, left_index=True, right_index=True, suffixes=('_cu', '_au'))
        ratio_df['ratio'] = (ratio_df['Close_cu'] / ratio_df['Close_au']) * 1000
        
        fig = px.line(ratio_df, x=ratio_df.index, y="ratio", title="铜金比 (Cu/Au x 1000) 6个月宏观趋势", template="plotly_dark")
        fig.update_yaxes(title="比值 (数值越高代表经济预期越强)")
    else:
        # 普通商品绘图
        h_data = yf.download(selected_plot, period="6mo", progress=False)['Close']
        if isinstance(h_data, pd.DataFrame): h_data = h_data.iloc[:, 0]
        fig = px.line(h_data, x=h_data.index, y=h_data.values, title=f"{plot_options[selected_plot]} 趋势图", template="plotly_dark")
        fig.update_yaxes(title="价格")

    st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.error(f"图表生成失败: {e}")

st.caption(f"数据实时更新 | 最后同步: {datetime.now().strftime('%H:%M:%S')}")
