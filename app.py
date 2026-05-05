import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="나만의 주식 분석기", layout="wide")

# 2. 사이드바 입력 폼 (모바일에서는 메뉴 버튼 내 위치)
st.sidebar.header("📌 투자 및 시뮬레이션 설정")
symbol = st.sidebar.text_input("종목코드 (예: 329200, SCHD)", value="SCHD")
my_avg_price = st.sidebar.number_input("매입단가", value=4750)
my_quantity = st.sidebar.number_input("보유 수량", value=350)
target_years = st.sidebar.slider("분석 기간 (년)", 1, 30, 10)
simulations = st.sidebar.number_input("시뮬레이션 횟수", value=5000)

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ 고급 설정")
apply_market_benchmark = st.sidebar.checkbox("시장 평균 수익률 강제 적용", value=False)
market_benchmark_return = st.sidebar.number_input("시장 수익률 (0.08 = 8%)", value=0.08)
use_manual_growth = st.sidebar.checkbox("배당 성장률 수동 입력", value=False)
manual_div_growth = st.sidebar.number_input("배당 성장률 (0.05 = 5%)", value=0.05)

# 종목 구분 로직
if symbol.isdigit():
    yf_symbol, fdr_symbol = symbol + '.KS', symbol
else:
    yf_symbol, fdr_symbol = symbol, symbol

# 3. 업체명 추출
try:
    ticker_info = yf.Ticker(yf_symbol).info
    stock_name = ticker_info.get('longName') or ticker_info.get('shortName') or symbol
except:
    stock_name = symbol

st.title(f"🚀 {stock_name} 분석 리포트")

if st.sidebar.button("📊 분석 및 시뮬레이션 시작"):
    with st.spinner('데이터를 수집하고 분석 중입니다...'):
        df_price = fdr.DataReader(fdr_symbol, '1990-01-01')

        if df_price.empty:
            st.error("데이터를 불러오지 못했습니다. 종목코드를 확인하세요.")
        else:
            # --- [섹션 1: 기업 주요 지표] ---
            st.header("🏢 기업 주요 재무 지표")
            try:
                ticker_obj = yf.Ticker(yf_symbol)
                f_annual, b_annual = ticker_obj.financials, ticker_obj.balance_sheet
                current_price = df_price.iloc[-1]['Close']

                rev = f_annual.loc['Total Revenue'] / 1e8 if 'Total Revenue' in f_annual.index else None
                net_inc = f_annual.loc['Net Income'] / 1e8 if 'Net Income' in f_annual.index else None
                eps = f_annual.loc['Basic EPS'] if 'Basic EPS' in f_annual.index else None
                
                df_fin = pd.DataFrame({
                    '매출액(억)': rev, '순이익(억)': net_inc, 'EPS(원)': eps
                }).sort_index()

                latest_date = df_fin.index[-1]
                latest_eps = df_fin.loc[latest_date, 'EPS(원)']
                shares = ticker_obj.info.get('sharesOutstanding')
                equity = b_annual.loc['Stockholders Equity', latest_date] if 'Stockholders Equity' in b_annual.index else None
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("현재가", f"{current_price:,.0f}")
                if latest_eps and latest_eps > 0: m2.metric("PER", f"{current_price / latest_eps:.2f}")
                if shares and equity:
                    m3.metric("PBR", f"{current_price / (equity / shares):.2f}")
                    m4.metric("ROE", f"{(df_fin.loc[latest_date, '순이익(억)'] * 1e8 / equity) * 100:.2f}%")
                
                with st.expander("세부 재무제표 확인"):
                    st.dataframe(df_fin.tail(5).style.format("{:,.0f}"))
            except:
                st.info("💡 재무 데이터가 제공되지 않는 종목입니다.")

            # --- [섹션 2: 수익률 분석] ---
            st.divider()
            st.header("📈 투자 수익률 분석")
            
            start_price = df_price.iloc[0]['Close']
            end_price = df_price.iloc[-1]['Close']
            duration_years = (df_price.index[-1] - df_price.index[0]).days / 365.25
            cagr_price = (end_price / start_price) ** (1 / duration_years) - 1
            adjusted_cagr = market_benchmark_return if apply_market_benchmark else cagr_price
            
            divs = yf.Ticker(yf_symbol).dividends
            if not divs.empty:
                annual_divs = divs.groupby(divs.index.year).sum().to_frame(name='연간 분배금 합계')
                avg_annual_div_yield = (divs.sum() / duration_years) / end_price

                c1, c2, c3 = st.columns(3)
                c1.metric("실제 CAGR", f"{cagr_price:.2%}")
                c2.metric("적용 수익률", f"{adjusted_cagr:.2%}")
                c3.metric("연평균 배당률", f"{avg_annual_div_yield:.2%}")
                st.success(f"**💡 총 합산 기대수익률: {(adjusted_cagr + avg_annual_div_yield):.2%}**")

                # --- [섹션 3: 배당 성장 상세 분석] ---
                st.header("💰 배당 성장 상세 분석")
                now_year = datetime.now().year
                full_years_data = annual_divs[annual_divs.index < now_year]
                
                if len(full_years_data) >= 2:
                    last_complete_year = full_years_data.index[-1]
                    last_div_per_share = full_years_data.loc[last_complete_year].values[0]
                    start_comp_year = full_years_data.index[1]
                    start_comp_div = full_years_data.loc[start_comp_year].values[0]
                    n_years_gap = last_complete_year - start_comp_year
                    
                    if use_manual_growth: calc_div_cagr = manual_div_growth
                    else: calc_div_cagr = (last_div_per_share / start_comp_div)**(1/n_years_gap) - 1 if n_years_gap > 0 else 0
                    
                    st.write(f"▶ **산출된 배당 성장률:** `{calc_div_cagr:.2%}`")
                    
                    # 향후 배당 예측 (YoC 포함)
                    initial_inv = my_avg_price * my_quantity
                    start_total_div_pure = last_div_per_share * my_quantity
                    
                    proj_data = []
                    for y in range(1, target_years + 1):
                        p_div = start_total_div_pure * ((1 + calc_div_cagr) ** y)
                        yoc = (p_div / initial_inv) * 100
                        proj_data.append({"연도": last_complete_year + y, "예상 배당금": f"{p_div:,.0f}원", "YoC": f"{yoc:.2f}%"})
                    
                    st.table(proj_data[:target_years])
                else:
                    st.warning("배당 성장 분석을 위한 충분한 과거 데이터가 없습니다.")

                # --- [섹션 4: 미래 자산 시뮬레이션] ---
                st.divider()
                st.header(f"🔮 {target_years}년 뒤 미래 자산 예측")
                
                daily_vol = df_price['Close'].pct_change().std()
                drift = (adjusted_cagr - 0.5 * (daily_vol**2 * 252)) * (1/252)
                vol = daily_vol * np.sqrt(252) * np.sqrt(1/252)
                path_returns = np.exp(drift + vol * np.random.normal(size=(simulations, 252 * target_years)))
                simulation_results = end_price * np.prod(path_returns, axis=1) * my_quantity

                r1, r2, r3 = st.columns(3)
                r1.metric("평균 예상 자산", f"{np.mean(simulation_results):,.0f}원")
                r2.metric("하위 5% (최악)", f"{np.percentile(simulation_results, 5):,.0f}원")
                r3.metric("상위 5% (최고)", f"{np.percentile(simulation_results, 95):,.0f}원")

                # 차트 레이아웃
                tab1, tab2 = st.tabs(["자산 분포 히스토그램", "주가 히스토리"])
                with tab1:
                    fig1, ax1 = plt.subplots(figsize=(10, 5))
                    ax1.hist(simulation_results, bins=50, color='royalblue', edgecolor='black', alpha=0.7)
                    ax1.axvline(initial_inv, color='red', linestyle='--')
                    st.pyplot(fig1)
                with tab2:
                    fig2, ax2 = plt.subplots(figsize=(10, 5))
                    ax2.plot(df_price.index, df_price['Close'], color='black')
                    st.pyplot(fig2)

            else:
                st.error("배당 정보를 찾을 수 없습니다.")
