import streamlit as st
import yfinance as yf
import akshare as ak
import pandas as pd
import plotly.express as px
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# ----------------- 1. 初始化 -----------------
st.set_page_config(layout="wide", page_title="硬核全维度资源看板-K线缩放版")
st.title("🛡️ 全球资源监控 & 投资全维度看板 (10年周期 + K线缩放)")

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
    "天然气 (NG=F)": "NG=F",
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

# ----------------- 3. 数据抓取 -----------------
@st.cache_data(ttl=3600)
def fetch_inventory():
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

with st.spinner('正在同步多源冗余数据并构建10年轴...'):
    inv_snapshot = fetch_inventory()
    try:
        df_spot, df_flow = ak.stock_zh_a_spot_em(), ak.stock_individual_fund_flow_rank_em()
    except:
        df_spot, df_flow = pd.DataFrame(), pd.DataFrame()

# ----------------- 4. 渲染：大宗商品表 -----------------
st.header("🌍 全球大宗商品 & 实时仓单快照")
com_res = []
cu_p, au_p = 1.0, 1.0

for label, ticker in com_tickers.items():
    try:
        t_info = yf.Ticker(ticker).fast_info
        p = t_info.last_price
        c = ((p / t_info.previous_close) - 1) * 100
        if "HG=F" in ticker: cu_p = p
        if "GC=F" in ticker: au_p = p
        com_res.append({
            "项目": label, "最新价": round(p, 3), "涨跌幅%": round(c, 2),
            "全球库存(LME)": inv_snapshot.get(label.split(' ')[0][1:].upper(), "无数据")
        })
    except: pass

# 插入铜金比行
com_res.append({"项目": "📈 铜金比 (Cu/Au x 1000)", "最新价": round((cu_p/au_p)*1000, 4), "涨跌幅%": "宏观指标", "全球库存(LME)": "---"})
st.dataframe(pd.DataFrame(com_res).style.map(highlight_flow, subset=['涨跌幅%']), use_container_width=True)

# ----------------- 5. 渲染：核心资产表 -----------------
st.header("🧱 核心资产监控 (冗余链路)")
china_res = []
for name, code in stock_list.items():
    pure_code = code.split('.')[0]
    row = {"名称": name, "价格": "N/A", "涨跌%": 0.0, "数据源": "Wait", "主力1d(万)": 0}
    if not df_spot.empty:
        m = df_spot[df_spot['代码'] == pure_code]
        if not m.empty:
            row.update({"价格": m.iloc[0]['最新价'], "涨跌%": m.iloc[0]['涨跌幅'], "数据源": "A股接口"})
    if row["价格"] == "N/A":
        try:
            t = yf.Ticker(code).fast_info
            row.update({"价格": round(t.last_price, 2), "涨跌%": round(((t.last_price/t.previous_close)-1)*100, 2), "数据源": "全球链路"})
        except: pass
    if not df_flow.empty:
        f = df_flow[df_flow['代码'] == pure_code]
        if not f.empty: row.update({"主力1d(万)": round(f.iloc[0]['今日主力净流入-净额']/10000, 0)})
    china_res.append(row)
st.dataframe(pd.DataFrame(china_res).style.map(highlight_flow, subset=['涨跌%', '主力1d(万)']), use_container_width=True)

# ----------------- 6. 渲染：10年缩放走势图 -----------------

st.header("📈 历史趋势分析 (K线级缩放控制)")

trend_opts = {"铜金比": "RATIO"}
trend_opts.update(com_tickers)
trend_opts.update(stock_list)

sel = st.selectbox("选择要分析的标的", options=list(trend_opts.keys()))
ticker = trend_opts[sel]

try:
    if ticker == "RATIO":
        cu = yf.download("HG=F", period="10y", progress=False)['Close']
        au = yf.download("GC=F", period="10y", progress=False)['Close']
        combined = pd.concat([cu, au], axis=1, join='inner')
        combined.columns = ['Cu', 'Au']
        y_data = (combined['Cu'] / combined['Au']) * 1000
        x_data = combined.index
    else:
        hist = yf.download(ticker, period="10y", progress=False)['Close']
        y_data = hist.values.flatten()
        x_data = hist.index

    fig = px.line(x=x_data, y=y_data, title=f"{sel} - 10年周期深度分析", template="plotly_dark")
    
    # --- 核心改进：添加K线风格的选择器和滑动条 ---
    fig.update_xaxes(
        rangeslider_visible=True,  # 显示底部的滑动缩放条
        rangeselector=dict(
            buttons=list([
                dict(count=1, label="1月", step="month", stepmode="backward"),
                dict(count=6, label="6月", step="month", stepmode="backward"),
                dict(count=1, label="1年", step="year", stepmode="backward"),
                dict(count=5, label="5年", step="year", stepmode="backward"),
                dict(step="all", label="全部")
            ]),
            bgcolor="#1f2630",
            activecolor="#00ff00",
            font=dict(color="white")
        )
    )
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
    st.info("💡 交互指南：点击上方按钮一键切换周期；拖动下方滑动条自由调整区间；在图表区域双击可恢复全部视图。")

except Exception as e:
    st.error(f"图表渲染失败: {e}")

st.caption(f"最后刷新: {datetime.now().strftime('%H:%M:%S')} | 数据已对齐并支持 K 线缩放交互")
