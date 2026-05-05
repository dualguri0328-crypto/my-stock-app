import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# 1. 페이지 레이아웃 설정
st.set_page_config(page_title="주식 분석 & 시뮬레이터", layout="wide")

# 2. 사이드바 - 사용자 입력 폼 (모바일에서는 메뉴 버튼 안에 위치)
st.sidebar.header("📈 분석 설정")
symbol = st.sidebar.text_input("종목코드 (예: 329200, SCHD)", value="SCHD")
my_avg_price = st.sidebar.number_input("매입단가 (원/$)", value=4750)
my_quantity = st.sidebar.number_input("보유 수량", value=350)
target_years = st.sidebar.slider("분석 기간 (년)", 1, 30, 10)
simulations = st.sidebar.number_input("시뮬레이션 횟수", value=5000)

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ 시뮬레이션 상세 설정")
apply_market_benchmark = st.sidebar.checkbox("시장 수익률 강제 적용", value=False)
market_benchmark_return = st.sidebar.number_input("시장 수익률 (0.08 = 8%)", value=0.08)

st.sidebar.subheader("💰 배당 성장 설정")
use_manual_growth = st.sidebar.checkbox("배당 성장률 수동 입력", value=False)
manual_div_growth = st.sidebar.number_input("수동 배당 성장률 (0.05 = 5%)", value=0.05)

# 종목 구분 및 티커 처리
if symbol.isdigit():
    yf_symbol, fdr_symbol = symbol + '.KS', symbol
else:
    yf_symbol, fdr_symbol = symbol, symbol

# 업체명 추출
try:
    ticker_obj = yf.Ticker(yf_symbol)
    stock_name = ticker_obj.info.get('longName') or ticker_obj.info.get('shortName') or symbol
except:
    stock_name = symbol

st.title(f"🚀 {stock_name} 분석 리포트")

# 분석 실행 버튼
if st.sidebar.button("📊 데이터 분석 및 시뮬레이션 시작"):
    with st.spinner('데이터를 분석 중입니다...'):
        # 시세 데이터 가져오기
        df_price = fdr.DataReader(fdr_symbol, '1990-01-01')

        if df_price.empty:
            st.error("시세 데이터를 불러오지 못했습니다. 종목코드를 확인해 주세요.")
        else:
            # --- [섹션 1: 주요 재무 지표] ---
            st.header("🏢 최근 주요 재무 및 지표")
            try:
                f_annual = ticker_obj.financials
                b_annual = ticker_obj.balance_sheet
                current_price = df_price.iloc[-1]['Close']

                # 재무 데이터 프레임 생성
                rev = f_annual.loc['Total Revenue'] / 1e8 if 'Total Revenue' in f_annual.index else None
                op_inc = f_annual.loc['Operating Income'] / 1e8 if 'Operating Income' in f_annual.index else None
                net_inc = f_annual.loc['Net Income'] / 1e8 if 'Net Income' in f_annual.index else None
                eps = f_annual.loc['Basic EPS'] if 'Basic EPS' in f_annual.index else None
                
                if 'Total Assets' in b_annual.index and 'Stockholders Equity' in b_annual.index:
                    debt_ratio = ((b_annual.loc['Total Assets'] - b_annual.loc['Stockholders Equity']) / b_annual.loc['Stockholders Equity']) * 100
                else: debt_ratio = None

                df_fin = pd.DataFrame({'매출액(억)': rev, '영업이익(억)': op_inc, '순이익(억)': net_inc, 'EPS(원)': eps, '부채비율(%)': debt_ratio}).sort_index()
                
                # 핵심 지표 계산
                latest_date = df_fin.index[-1]
                latest_eps = df_fin.loc[latest_date, 'EPS(원)']
                shares = ticker_obj.info.get('sharesOutstanding')
                equity = b_annual.loc['Stockholders Equity', latest_date] if 'Stockholders Equity' in b_annual.index else None
                
                # 메트릭 카드 표시
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("현재가", f"{current_price:,.0f}")
                if latest_eps and latest_eps > 0:
                    m2.metric("PER", f"{current_price / latest_eps:.2f}")
                if shares and equity:
                    m3.metric("PBR", f"{current_price / (equity / shares):.2f}")
                    m4.metric("ROE", f"{(df_fin.loc[latest_date, '순이익(억)'] * 1e8 / equity) * 100:.2f}%")
                
                with st.expander("📊 재무 데이터프레임 상세 보기"):
                    st.dataframe(df_fin.tail(10).style.format("{:,.1f}"))
            except:
                st.info("💡 재무 데이터가 제공되지 않는 종목(ETF 등)입니다.")

            # --- [섹션 2: 투자 분석 결과] ---
            st.divider()
            st.header("📈 투자 분석 결과")
            
            start_date_str = df_price.index[0].strftime('%Y-%m-%d')
            start_price = df_price.iloc[0]['Close']
            end_price = df_price.iloc[-1]['Close']
            duration_years = (df_price.index[-1] - df_price.index[0]).days / 365.25
            cagr_price = (end_price / start_price) ** (1 / duration_years) - 1
            adjusted_cagr = market_benchmark_return if apply_market_benchmark else cagr_price
            
            divs = ticker_obj.dividends
            if not divs.empty:
                annual_divs = divs.groupby(divs.index.year).sum().to_frame(name='연간 분배금')
                avg_annual_div_yield = (divs.sum() / duration_years) / end_price
                
                c1, c2, c3 = st.columns(3)
                c1.write(f"**상장일:** {start_date_str}")
                c1.write(f"**상장일가:** {start_price:,.0f}")
                c2.write(f"**실제 CAGR:** {cagr_price:.2%}")
                c2.write(f"**적용 수익률:** {adjusted_cagr:.2%}")
                c3.write(f"**연평균 배당률:** {avg_annual_div_yield:.2%}")
                c3.write(f"**총 기대수익률:** {adjusted_cagr + avg_annual_div_yield:.2%}")
                
                with st.expander("📅 연도별 분배금 내역"):
                    st.table(annual_divs.tail(10))

                # --- [섹션 3: 향후 배당금 및 성장 분석] ---
                st.divider()
                st.header(f"💰 향후 {target_years}년 배당 예측")
                
                now_year = datetime.now().year
                full_years_data = annual_divs[annual_divs.index < now_year]
                last_complete_year = full_years_data.index[-1]
                last_div_per_share = full_years_data.loc[last_complete_year].values[0]
                initial_investment = my_avg_price * my_quantity

                col_div1, col_div2 = st.columns(2)
                
                with col_div1:
                    st.subheader("📍 주가 비례 예측")
                    years_list, div_list = [], []
                    for year in range(1, target_years + 1):
                        expected_price = end_price * np.exp(adjusted_cagr * year)
                        expected_div = expected_price * (last_div_per_share / end_price) * my_quantity
                        yoc = (expected_div / initial_investment) * 100
                        st.write(f"**{last_complete_year + year}년:** {expected_div:,.0f}원 ({yoc:.2f}%)")
                        years_list.append(str(last_complete_year + year))
                        div_list.append(expected_div)

                with col_div2:
                    st.subheader("📍 배당 자체 성장 분석")
                    if len(full_years_data) >= 2:
                        start_comp_year = full_years_data.index[1]
                        start_comp_div = full_years_data.loc[start_comp_year].values[0]
                        n_years_gap = last_complete_year - start_comp_year
                        
                        calc_div_cagr = manual_div_growth if use_manual_growth else (last_div_per_share / start_comp_div)**(1/n_years_gap) - 1
                        st.info(f"산출 성장률: {calc_div_cagr:.2%}")
                        
                        start_total_div_pure = last_div_per_share * my_quantity
                        for y in range(1, target_years + 1):
                            proj_div = start_total_div_pure * ((1 + calc_div_cagr) ** y)
                            yoc_pure = (proj_div / initial_investment) * 100
                            st.write(f"**{last_complete_year + y}년:** {proj_div:,.0f}원 ({yoc_pure:.2f}%)")
                    else:
                        st.write("데이터 부족으로 분석 불가")

                # --- [섹션 4: 몬테카를로 시뮬레이션] ---
                st.divider()
                st.header(f"🔮 {target_years}년 뒤 자산 예측")
                
                daily_vol = df_price['Close'].pct_change().std()
                trading_days = 252 * target_years
                dt = 1 / 252
                drift = (adjusted_cagr - 0.5 * (daily_vol**2 * 252)) * dt
                vol = daily_vol * np.sqrt(252) * np.sqrt(dt)
                path_returns = np.exp(drift + vol * np.random.normal(size=(simulations, trading_days)))
                final_assets = end_price * np.prod(path_returns, axis=1) * my_quantity

                res1, res2, res3 = st.columns(3)
                res1.metric("평균 예상 자산", f"{np.mean(final_assets):,.0f}")
                res2.metric("최악 (하위 5%)", f"{np.percentile(final_assets, 5):,.0f}")
                res3.metric("최고 (상위 5%)", f"{np.percentile(final_assets, 95):,.0f}")

                # 시각화 차트
                tab1, tab2 = st.tabs(["📊 자산 분포도", "📉 배당금 흐름"])
                with tab1:
                    fig1, ax1 = plt.subplots(figsize=(10, 5))
                    ax1.hist(final_assets, bins=50, color='royalblue', edgecolor='black', alpha=0.7)
                    ax1.axvline(initial_investment, color='red', linestyle='--', label='Initial')
                    st.pyplot(fig1)
                with tab2:
                    fig2, ax2 = plt.subplots(figsize=(10, 5))
                    ax2.plot(years_list, div_list, marker='o', color='forestgreen', linewidth=2)
                    plt.xticks(rotation=45)
                    st.pyplot(fig2)

            else:
                st.error("배당 내역을 불러오지 못했습니다.")

    st.success("✅ 분석이 완료되었습니다!")
