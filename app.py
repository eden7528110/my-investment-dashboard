import streamlit as st
import yfinance as yf
import akshare as ak
import pandas as pd
import plotly.express as px
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# ----------------- 1. 初始化设置 -----------------
st.set_page_config(layout="wide", page_title="硬核全维度资源看板-10年周期版")
st.title("🛡️ 全球资源监控 & 投资全维度看板 (10年长周期版)")

def highlight_flow(val):
    if not isinstance(val, (int, float)): return ''
    return 'color: #00ff00' if val > 0 else 'color: #ff4b4b' if val < 0 else ''

def highlight_concentration(val):
    if not isinstance(val, (int, float)): return ''
    return 'background-color: rgba(0, 255, 0, 0.1); color: #00ff00' if val < 0 else 'color: #ff4b4b'

# ----------------- 2. 标的清单整合 -----------------
# 大宗商品清单
com_tickers = {
    "期铜 (HG=F)": "HG=F",
    "黄金 (GC=F)": "GC=F",
    "期铝 (ALI=F)": "ALI=F",
    "白银 (SI=F)": "SI=F",
    "原油 (CL=F)": "CL=F"
}

# A股/港股核心清单 (保持你要求的24+标的)
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

# ----------------- 3. 数据抓取引擎 -----------------

@st.cache_data(ttl=3600)
def get_inventory_snapshot():
    """保留：SMM爬虫 + AkShare库存回溯"""
    inv_map = {}
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        urls = {"LME": "https://www.metal.com/LME/Inventory", "SHFE": "https://www.metal.com/SHFE/Inventory"}
        for prefix, url in urls.items():
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
def get_investment_data():
    """获取A股深度投资指标（含筹码/分红/资金流）"""
    try:
        df_spot = ak.stock_zh_a_spot_em()
        df_flow = ak.stock_individual_fund_flow_rank_em()
        df_gdhs = ak.stock_zh_a_gdhs_em()
        df_div = ak.stock_fhps_detail_em()
        return df_spot, df_flow, df_gdhs, df_div
    except:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# ----------------- 4. 逻辑处理 -----------------

with st.spinner('正在同步全球仓单与10年历史数据...'):
    inv_snapshot = get_inventory_snapshot()
    df_spot, df_flow, df_gdhs, df_div = get_investment_data()

# 4.1 大宗仓单表逻辑
com_table_data = []
for label, ticker in com_tickers.items():
    try:
        t_info = yf.Ticker(ticker).fast_info
        p = t_info.last_price
        c = ((p / t_info.previous_close) - 1) * 100
        com_table_data.append({
            "项目": label, "最新价": round(p, 2), "涨跌幅%": round(c, 2),
            "全球库存(LME)": inv_snapshot.get(f"LME_{label[1:2]}", "---"), # 提取名称
            "中国库存(SHFE)": inv_snapshot.get(f"SHFE_{label[1:2]}", "---")
        })
    except: pass

# 4.2 核心资产表逻辑 (整合筹码、资金流、分红)
china_results = []
for name, yf_code in stock_list.items():
    pure_code = yf_code.split('.')[0]
    row = {"名称": name, "价格": "N/A", "涨跌%": 0.0, "PE(动)": "-", "PB": "-", "主力1d(万)": 0, "主力5d(万)": 0, "筹码变动%": "-", "最新分红": "无"}
    
    if not df_spot.empty:
        m = df_spot[df_spot['代码'] == pure_code]
        if not m.empty:
            row.update({"价格": m.iloc[0]['最新价'], "涨跌%": m.iloc[0]['涨跌幅'], "PE(动)": m.iloc[0]['市盈率-动态'], "PB": m.iloc[0]['市净率']})
    
    if not df_flow.empty:
        f = df_flow[df_flow['代码'] == pure_code]
        if not f.empty:
            row.update({"主力1d(万)": round(f.iloc[0]['今日主力净流入-净额']/10000, 0), "主力5d(万)": round(f.iloc[0]['5日主力净流入-净额']/10000, 0)})

    if not df_gdhs.empty:
        g = df_gdhs[df_gdhs['代码'] == pure_code]
        if not g.empty: row.update({"筹码变动%": g.iloc[0]['股东户数逐季增减']})

    if not df_div.empty:
        d = df_div[df_div['代码'] == pure_code].head(1)
        if not d.empty: row.update({"最新分红": f"{d.iloc[0]['派息']}(元/10股)"})
        
    china_results.append(row)

# ----------------- 5. 页面渲染 -----------------

# [一] 大宗商品仓单快照
st.header("🌍 全球大宗商品 & 实时仓单快照")
st.dataframe(pd.DataFrame(com_table_data).style.map(highlight_flow, subset=['涨跌幅%']), use_container_width=True)

# [二] 核心资产监控表
st.header("🧱 核心资产监控 (筹码/分红/资金流)")
st.dataframe(
    pd.DataFrame(china_results).style.map(highlight_flow, subset=['涨跌%', '主力1d(万)', '主力5d(万)'])
                  .map(highlight_concentration, subset=['筹码变动%']),
    use_container_width=True, height=500
)

# [三] 10年趋势穿透分析 (包含大宗商品回归)
st.header("📈 价格走势穿透 (10年长周期历史数据)")

# 整合所有可选标的，包含大宗和个股
trend_options = {"铜金比": "RATIO"}
trend_options.update(com_tickers)
trend_options.update(stock_list)

sel_label = st.selectbox("选择要分析的标的 (支持大宗商品、铜金比及A/H股)", options=list(trend_options.keys()))
sel_ticker = trend_options[sel_label]

try:
    if sel_ticker == "RATIO":
        # 抓取10年数据计算铜金比
        cu = yf.download("HG=F", period="10y", progress=False)['Close']
        au = yf.download("GC=F", period="10y", progress=False)['Close']
        c_vals = cu.values.flatten()
        a_vals = au.values.flatten()
        ratio = (c_vals / a_vals) * 1000
        fig = px.line(x=cu.index, y=ratio, title="宏观经济长周期：铜金比 (10年趋势)", template="plotly_dark")
    else:
        # 抓取10年数据
        hist = yf.download(sel_ticker, period="10y", progress=False)['Close']
        p_vals = hist.values.flatten()
        fig = px.line(x=hist.index, y=p_vals, title=f"{sel_label} 10年价格走势", template="plotly_dark")
    
    # 开启交互式缩放工具栏
    fig.update_layout(dragmode='zoom', hovermode='x unified')
    st.plotly_chart(fig, use_container_width=True)
    st.info("💡 提示：按住鼠标左键并在图表中拖动即可局部放大查看早期细节。双击图表恢复原样。")

except Exception as e:
    st.warning(f"数据加载失败: 该标的上市时间可能不足10年或网络受限。 详情: {e}")

st.caption(f"系统运行中 | 最后刷新: {datetime.now().strftime('%H:%M:%S')} | 数据周期: 2016 - 2026")
