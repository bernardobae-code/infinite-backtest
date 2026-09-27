import yfinance as yf
import pandas as pd
import streamlit as st
import datetime

st.set_page_config(page_title="무한매수법 백테스터", page_icon="📈")
st.title("📈 무한매수법 웹 백테스터")

st.markdown("과거 데이터를 바탕으로 TQQQ, SOXL 무한매수법의 성과를 시뮬레이션합니다.")

col1, col2 = st.columns(2)
with col1:
    ticker = st.selectbox("주식 종목", ["TQQQ", "SOXL"])
    t_value = st.selectbox("원금 분할 주기 (최대 T값)", [20, 30, 40], index=2)
with col2:
    start_date = st.date_input("시작 일자", datetime.date(2021, 1, 1))
    end_date = st.date_input("종료 일자", datetime.date(2024, 1, 1))
    
initial_capital = st.number_input("초기 자본금 ($)", value=10000, step=1000)

if st.button("🚀 백테스트 실행", type="primary"):
    if start_date >= end_date:
        st.error("종료 일자는 시작 일자보다 미래여야 합니다.")
    else:
        with st.spinner("주가 데이터를 불러오고 계산 중입니다..."):
            try:
                df = yf.download(ticker, start=start_date, end=end_date, progress=False)
                if df.empty:
                    st.error("❌ 해당 기간의 데이터가 없습니다. (상장일 이전이거나 주말/휴일일 수 있습니다.)")
                else:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = [col[0] for col in df.columns.values]
                        
                    cash = initial_capital
                    holding_qty = 0
                    avg_price = 0.0
                    current_cycle = 0
                    max_cycle_reached = 0
                    total_sell_count = 0
                    peak = initial_capital
                    max_drawdown = 0
                    
                    for date, row in df.iterrows():
                        open_p, high_p, low_p, close_p = row['Open'], row['High'], row['Low'], row['Close']
                        if pd.isna(close_p): continue
                        
                        # [매도 체크] 목표 수익률 +10%
                        if holding_qty > 0:
                            target_sell_price = avg_price * 1.10
                            if high_p >= target_sell_price:
                                cash += holding_qty * target_sell_price
                                holding_qty = 0
                                avg_price = 0.0
                                current_cycle = 0
                                total_sell_count += 1
                                
                        # [매수 체크]
                        total_eval = cash + (holding_qty * close_p)
                        unit_buy_budget = total_eval / t_value
                        
                        if holding_qty == 0:
                            buy_qty = int(unit_buy_budget / close_p)
                            if buy_qty > 0 and cash >= buy_qty * close_p:
                                holding_qty = buy_qty
                                avg_price = close_p
                                cash -= buy_qty * close_p
                                current_cycle = 1
                                if current_cycle > max_cycle_reached: max_cycle_reached = current_cycle
                        elif current_cycle < t_value:
                            half_budget = unit_buy_budget / 2.0
                            bought_amount = 0
                            bought_qty = 0
                            
                            # 조건 A: 평단가 이하 LOC
                            if close_p <= avg_price and cash >= half_budget:
                                q1 = int(half_budget / close_p)
                                bought_qty += q1
                                bought_amount += q1 * close_p
                                
                            # 조건 B: 평단가 + 1% 이하 LOC
                            if close_p <= avg_price * 1.01 and cash >= (half_budget + bought_amount):
                                q2 = int(half_budget / close_p)
                                bought_qty += q2
                                bought_amount += q2 * close_p
                                
                            if bought_qty > 0 and cash >= bought_amount:
                                cash -= bought_amount
                                new_total_qty = holding_qty + bought_qty
                                avg_price = ((holding_qty * avg_price) + bought_amount) / new_total_qty
                                holding_qty = new_total_qty
                                current_cycle += 1
                                if current_cycle > max_cycle_reached: max_cycle_reached = current_cycle

                        # 자산 평가액 및 MDD 계산
                        current_val = cash + (holding_qty * close_p)
                        if current_val > peak: peak = current_val
                        dd = (current_val - peak) / peak
                        if dd < max_drawdown: max_drawdown = dd
                        
                    final_val = cash + (holding_qty * df['Close'].iloc[-1])
                    total_return = ((final_val - initial_capital) / initial_capital) * 100
                    actual_start = df.index[0].strftime('%Y-%m-%d')
                    actual_end = df.index[-1].strftime('%Y-%m-%d')
                    
                    st.success("✅ 백테스트 완료!")
                    st.markdown(f"""
                    ### 📊 백테스트 결과 요약
                    * **실제 조회된 기간:** {actual_start} ~ {actual_end}
                    * **초기 자본금:** ${initial_capital:,.2f}
                    * **최종 자산:** **${final_val:,.2f}**
                    * **누적 수익률:** **{total_return:.2f}%**
                    * **최대 낙폭(MDD):** {max_drawdown*100:.2f}%
                    * **운용 요약:** 목표 달성 전량 익절(리셋) **{total_sell_count}회** / 최대 진입 **{max_cycle_reached}차수**(일) 도달
                    """)
            except Exception as e:
                st.error(f"오류 발생: {str(e)}")
