import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# 1. 페이지 레이아웃 및 스타일 설정
st.set_page_config(page_title="Pro Stock Analyzer", layout="wide")
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; }
    </style>
    """, unsafe_allow_html=True)

# 2. 사이드바 - 사용자 입력 컨트롤 (모바일에서는 메뉴 내 위치)
st.sidebar.header("⚙️ 시뮬레이션 설정")
symbol = st.sidebar.text_input("종목코드 (예: SCHD, 005930)", value="SCHD").upper()
my_avg_price = st.sidebar.number_input("평균 매입단가", value=4750)
my_quantity = st.sidebar.number_input("보유 수량", value=350)
target_years = st.sidebar.slider("분석 기간 (년)", 1, 30, 10)
simulations = st.sidebar.number_input("몬테카를로 실행 횟수", value=5000)

with st.sidebar.expander("🛠 고급 설정 (시장수익률/배당성장)"):
    apply_market_benchmark = st.checkbox("시장 평균 강제 적용", value=False)
    market_benchmark_return = st.number_input("시장 평균 수익률 (0.08=8%)", value=0.08)
    use_manual_growth = st.checkbox("배당 성장률 수동 입력", value=False)
    manual_div_growth = st.number_input("수동 배당 성장률 (0.05=5%)", value=0.05)

# 종목 구분 처리 로직
if symbol.isdigit():
    yf_symbol, fdr_symbol = symbol + '.KS', symbol
else:
    yf_symbol, fdr_symbol = symbol, symbol

# 3. 데이터 로딩 및 분석 엔진
try:
    ticker_obj = yf.Ticker(yf_symbol)
    stock_name = ticker_obj.info.get('longName') or ticker_obj.info.get('shortName') or symbol
    df_price = fdr.DataReader(fdr_symbol, '1990-01-01')
except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
    st.stop()

if df_price.empty:
    st.warning("시세 데이터를 찾을 수 없습니다. 종목 코드를 확인해주세요.")
else:
    st.title(f"📈 {stock_name} 전문 분석 리포트")
    st.caption(f"분석 기준일: {datetime.now().strftime('%Y-%m-%d')} | 데이터 출처: Yahoo Finance, FinanceDataReader")

    # --- [섹션 1: 기업 재무 상태 분석] ---
    st.header("🏢 기업 주요 재무 지표")
    try:
        f_annual = ticker_obj.financials
        b_annual = ticker_obj.balance_sheet
        current_price = df_price.iloc[-1]['Close']

        # 데이터 가공 (단위: 억)
        rev = f_annual.loc['Total Revenue'] / 1e8 if 'Total Revenue' in f_annual.index else None
        op_inc = f_annual.loc['Operating Income'] / 1e8 if 'Operating Income' in f_annual.index else None
        net_inc = f_annual.loc['Net Income'] / 1e8 if 'Net Income' in f_annual.index else None
        eps = f_annual.loc['Basic EPS'] if 'Basic EPS' in f_annual.index else None
        
        # 지표 계산
        latest_date = f_annual.columns[0]
        latest_eps = eps[0] if eps is not None else 0
        shares = ticker_obj.info.get('sharesOutstanding')
        equity = b_annual.loc['Stockholders Equity'][0] if 'Stockholders Equity' in b_annual.index else None
        
        calc_per = current_price / latest_eps if latest_eps > 0 else "N/A"
        calc_roe = (net_inc[0] * 1e8 / equity) * 100 if equity and net_inc is not None else "N/A"
        
        # 가로 지표 레이아웃
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("현재가", f"{current_price:,.0f}")
        m2.metric("계산된 PER", f"{calc_per:.2f}" if isinstance(calc_per, float) else calc_per)
        m3.metric("계산된 ROE", f"{calc_roe:.2%}" if isinstance(calc_roe, float) else calc_roe)
        m4.metric("최근 순이익(억)", f"{net_inc[0]:,.0f}" if net_inc is not None else "N/A")

        with st.expander("📋 연간 재무제표 상세보기"):
            df_fin = pd.DataFrame({
                '매출액(억)': rev, '영업이익(억)': op_inc, '순이익(억)': net_inc, 'EPS(원)': eps
            }).sort_index(ascending=False)
            st.dataframe(df_fin.style.format("{:,.0f}"))
    except:
        st.info("💡 본 종목은 ETF 또는 재무 정보를 제공하지 않는 종목입니다.")

    # --- [섹션 2: 과거 성과 분석] ---
    st.divider()
    st.header("⏳ 과거 투자 성과 (Back-test)")
    
    start_price = df_price.iloc[0]['Close']
    end_price = df_price.iloc[-1]['Close']
    duration_years = (df_price.index[-1] - df_price.index[0]).days / 365.25
    cagr_price = (end_price / start_price) ** (1 / duration_years) - 1
    adjusted_cagr = market_benchmark_return if apply_market_benchmark else cagr_price

    divs = ticker_obj.dividends
    if not divs.empty:
        annual_divs = divs.groupby(divs.index.year).sum().to_frame(name='분배금 합계')
        avg_div_yield = (divs.sum() / duration_years) / end_price
        
        c1, c2, c3 = st.columns(3)
        c1.metric("실제 시세 CAGR", f"{cagr_price:.2%}")
        c2.metric("연평균 배당수익률", f"{avg_div_yield:.2%}")
        c3.metric("총 합산 기대수익률", f"{(adjusted_cagr + avg_div_yield):.2%}")

        # --- [섹션 3: 미래 배당금 성장 시뮬레이션] ---
        st.divider()
        st.header(f"💰 향후 {target_years}년 배당금 예측")
        
        now_year = datetime.now().year
        full_years_data = annual_divs[annual_divs.index < now_year]
        last_complete_year = full_years_data.index[-1]
        last_div_per_share = full_years_data.loc[last_complete_year].values[0]
        initial_investment = my_avg_price * my_quantity

        tab1, tab2 = st.tabs(["📉 주가 비례 배당 예측", "📈 배당 성장률 기반 예측 (YoC)"])
        
        with tab1:
            st.subheader("주가 상승 시나리오에 따른 배당")
            y_list, d_list = [], []
            for year in range(1, target_years + 1):
                exp_price = end_price * np.exp(adjusted_cagr * year)
                exp_div = exp_price * (last_div_per_share / end_price) * my_quantity
                y_list.append(str(last_complete_year + year))
                d_list.append(exp_div)
                st.write(f"📅 **{last_complete_year + year}년**: 약 **{exp_div:,.0f}원** (월 평균 {exp_div/12:,.0f}원)")

        with tab2:
            st.subheader("과거 배당 성장 추세 기반 분석")
            if len(full_years_data) >= 2:
                start_comp_year = full_years_data.index[1]
                start_comp_div = full_years_data.loc[start_comp_year].values[0]
                n_gap = last_complete_year - start_comp_year
                
                div_cagr = manual_div_growth if use_manual_growth else (last_div_per_share / start_comp_div)**(1/n_gap) - 1
                st.info(f"분석된 배당 성장률: {div_cagr:.2%}")
                
                curr_total_div = last_div_per_share * my_quantity
                for y in range(1, target_years + 1):
                    proj_div = curr_total_div * ((1 + div_cagr) ** y)
                    yoc = (proj_div / initial_investment) * 100
                    st.write(f"📅 **{last_complete_year + y}년**: **{proj_div:,.0f}원** | 매수가 대비 수익률(YoC): **{yoc:.2f}%**")
            else:
                st.write("데이터 부족으로 분석할 수 없습니다.")

        # --- [섹션 4: 몬테카를로 자산 예측 시뮬레이션] ---
        st.divider()
        st.header(f"🔮 {target_years}년 뒤 자산 분포 예측")
        
        daily_vol = df_price['Close'].pct_change().std()
        trading_days = 252 * target_years
        dt = 1 / 252
        
        # 시뮬레이션 계산
        shocks = np.random.normal(size=(simulations, trading_days))
        drift = (adjusted_cagr - 0.5 * (daily_vol**2 * 252)) * dt
        vol = daily_vol * np.sqrt(252) * np.sqrt(dt)
        path = np.exp(drift + vol * shocks)
        final_vals = end_price * np.prod(path, axis=1) * my_quantity

        col_res1, col_res2 = st.columns([1, 2])
        with col_res1:
            st.write(f"**초기 투자금:** {initial_investment:,.0f}원")
            st.success(f"**평균 예상 자산:** {np.mean(final_vals):,.0f}원")
            st.info(f"**중앙값 자산:** {np.median(final_vals):,.0f}원")
            st.warning(f"**하위 5% (최악):** {np.percentile(final_vals, 5):,.0f}원")
            st.error(f"**상위 5% (최고):** {np.percentile(final_vals, 95):,.0f}원")

        with col_res2:
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.hist(final_vals, bins=50, color='#3498db', edgecolor='white', alpha=0.8)
            ax.axvline(initial_investment, color='red', linestyle='--', label='Initial Inv')
            ax.set_title("Asset Distribution Histogram")
            st.pyplot(fig)

    else:
        st.error("배당 정보를 불러올 수 없는 종목입니다.")
