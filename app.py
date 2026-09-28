import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st
import datetime
import math

st.set_page_config(page_title="무한매수법 V4.0 백테스터", page_icon="📈", layout="wide")
st.title("📈 무한매수법 V4.0 웹 백테스터")
st.markdown("V4.0 알고리즘(별지점, 쿼터매도, 리버스모드)을 바탕으로 과거 성과와 연평균 수익률(CAGR), 사이클별 내역을 시뮬레이션합니다.")

col1, col2 = st.columns(2)
with col1:
    ticker = st.selectbox("주식 종목", ["TQQQ", "SOXL"])
    t_value = st.selectbox("원금 분할 주기 (V4.0 기준)", [20, 40], index=1)
    target_profit = st.number_input("일반모드 목표 수익률 (%)", value=10.0, step=1.0) / 100.0
with col2:
    start_date = st.date_input("시작 일자", datetime.date(2021, 1, 1))
    end_date = st.date_input("종료 일자", datetime.date(2024, 1, 1))
    initial_capital = st.number_input("초기 자본금 ($)", value=20000, step=1000)

if st.button("🚀 V4.0 백테스트 실행", type="primary"):
    if start_date >= end_date:
        st.error("종료 일자는 시작 일자보다 미래여야 합니다.")
    else:
        with st.spinner("주가 데이터를 불러오고 V4.0 알고리즘을 계산 중입니다... (약 10~20초 소요)"):
            try:
                df = yf.download(ticker, start=start_date, end=end_date, progress=False)
                if df.empty:
                    st.error("❌ 해당 기간의 데이터가 없습니다. (상장일 이전이거나 주말/휴일일 수 있습니다.)")
                else:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = [col[0] for col in df.columns.values]
                        
                    cash = initial_capital
                    holdings = 0
                    avg_price = 0.0
                    T = 0.0
                    mode = 'general'
                    reverse_day = 0
                    
                    max_cycle_reached = 0
                    total_reset_count = 0
                    reverse_mode_count = 0
                    peak = initial_capital
                    max_drawdown = 0
                    
                    closes = df['Close'].values
                    highs = df['High'].values
                    dates = df.index
                    
                    # 사이클 기록용 변수
                    cycle_history = []
                    cycle_number = 1
                    cycle_start_date = dates[0]
                    cycle_start_val = initial_capital
                    cycle_max_T = 0.0
                    cycle_rev_triggered = False
                    
                    for i in range(len(df)):
                        close_p = closes[i]
                        high_p = highs[i]
                        date = dates[i]
                        if pd.isna(close_p): continue
                        
                        # --- 1. 일반 모드 (General Mode) ---
                        if mode == 'general':
                            # [1] 전체 익절 체크 (지정가 매도)
                            if holdings > 0:
                                target_price = avg_price * (1 + target_profit)
                                if high_p >= target_price:
                                    cash += holdings * target_price # 익절 체결
                                    
                                    # 사이클 기록 저장
                                    cycle_end_val = cash
                                    cycle_return = ((cycle_end_val - cycle_start_val) / cycle_start_val) * 100
                                    cycle_history.append({
                                        "사이클": f"{cycle_number}회차",
                                        "시작일": cycle_start_date.strftime('%Y-%m-%d'),
                                        "종료일": date.strftime('%Y-%m-%d'),
                                        "최대 T값": round(cycle_max_T, 2),
                                        "리버스 발동": "O" if cycle_rev_triggered else "X",
                                        "수익률 (%)": round(cycle_return, 2),
                                        "종료 자산 ($)": round(cycle_end_val, 2)
                                    })
                                    
                                    # 초기화 및 다음 사이클 준비
                                    holdings = 0
                                    avg_price = 0.0
                                    T = 0.0
                                    total_reset_count += 1
                                    
                                    cycle_number += 1
                                    cycle_start_date = date
                                    cycle_start_val = cash
                                    cycle_max_T = 0.0
                                    cycle_rev_triggered = False
                                    continue 
                            
                            # [2] 소진모드(Reverse Mode) 진입 체크
                            if T >= (t_value - 1):
                                mode = 'reverse'
                                reverse_day = 1
                                reverse_mode_count += 1
                                cycle_rev_triggered = True
                                
                            else:
                                # [3] 별지점 산출
                                if ticker == "TQQQ":
                                    star_pct = (15 - 1.5 * T) if t_value == 20 else (15 - 0.75 * T)
                                else: # SOXL
                                    star_pct = (20 - 2.0 * T) if t_value == 20 else (20 - T)
                                
                                star_point = avg_price * (1 + (star_pct / 100.0))
                                buy_point = star_point - 0.01
                                
                                # [4] 1회 매수 예산 산출
                                if T == 0:
                                    budget = (cash + holdings * close_p) / t_value
                                else:
                                    budget = cash / max(1.0, (t_value - T))
                                
                                q_sell_executed = False
                                buy_ratio = 0.0
                                bought_amt = 0.0
                                bought_qty = 0
                                
                                # [5] 쿼터 매도 (LOC)
                                if holdings > 0 and close_p >= star_point:
                                    q_sell_qty = max(1, int(holdings / 4))
                                    if q_sell_qty > holdings: q_sell_qty = holdings
                                    cash += q_sell_qty * close_p
                                    holdings -= q_sell_qty
                                    q_sell_executed = True
                                
                                # [6] 매수 진행 (LOC)
                                if T == 0:
                                    qty = int(budget / close_p)
                                    if qty > 0 and cash >= qty * close_p:
                                        bought_qty = qty
                                        bought_amt = qty * close_p
                                        buy_ratio = 1.0
                                elif T < t_value / 2:
                                    half_budget = budget / 2.0
                                    if close_p <= buy_point and cash >= half_budget:
                                        q1 = int(half_budget / close_p)
                                        bought_qty += q1
                                        bought_amt += q1 * close_p
                                        buy_ratio += 0.5
                                    if close_p <= avg_price and cash >= (half_budget + bought_amt):
                                        q2 = int(half_budget / close_p)
                                        bought_qty += q2
                                        bought_amt += q2 * close_p
                                        buy_ratio += 0.5
                                else:
                                    if close_p <= buy_point and cash >= budget:
                                        qty = int(budget / close_p)
                                        bought_qty = qty
                                        bought_amt = qty * close_p
                                        buy_ratio = 1.0
                                        
                                if bought_qty > 0:
                                    cash -= bought_amt
                                    new_holdings = holdings + bought_qty
                                    avg_price = ((holdings * avg_price) + bought_amt) / new_holdings
                                    holdings = new_holdings
                                
                                if q_sell_executed:
                                    T = T * 0.75
                                T += buy_ratio
                                
                                if T > max_cycle_reached: max_cycle_reached = T
                                if T > cycle_max_T: cycle_max_T = T

                        # --- 2. 리버스/소진 모드 (Reverse Mode) ---
                        if mode == 'reverse':
                            div_val = 10 if t_value == 20 else 20
                            
                            if reverse_day == 1:
                                if holdings > 0:
                                    sell_qty = max(1, int(holdings / div_val))
                                    if sell_qty > holdings: sell_qty = holdings
                                    cash += sell_qty * close_p
                                    holdings -= sell_qty
                                    T = T * (0.9 if t_value == 20 else 0.95)
                                reverse_day += 1
                                
                            else:
                                start_idx = max(0, i - 5)
                                rev_star_point = np.mean(closes[start_idx:i])
                                rev_buy_point = rev_star_point - 0.01
                                
                                budget = cash / 4.0
                                sell_executed = False
                                buy_executed = False
                                
                                if close_p >= rev_star_point and holdings > 0:
                                    sell_qty = max(1, int(holdings / div_val))
                                    if sell_qty > holdings: sell_qty = holdings
                                    cash += sell_qty * close_p
                                    holdings -= sell_qty
                                    sell_executed = True
                                
                                if close_p <= rev_buy_point and cash >= budget:
                                    qty = int(budget / close_p)
                                    if qty > 0:
                                        cash -= qty * close_p
                                        new_holdings = holdings + qty
                                        avg_price = ((holdings * avg_price) + (qty * close_p)) / new_holdings
                                        holdings = new_holdings
                                        buy_executed = True
                                        
                                if sell_executed:
                                    T = T * (0.9 if t_value == 20 else 0.95)
                                if buy_executed:
                                    T = T + (t_value - T) * 0.25
                                    
                            escape_limit = 0.85 if ticker == "TQQQ" else 0.80
                            if avg_price > 0 and close_p > (avg_price * escape_limit):
                                mode = 'general'
                                reverse_day = 0
                                
                            if T > max_cycle_reached: max_cycle_reached = T
                            if T > cycle_max_T: cycle_max_T = T
                                
                        # --- 3. 공통 자산 기록 ---
                        current_val = cash + (holdings * close_p)
                        if current_val > peak: peak = current_val
                        dd = (current_val - peak) / peak
                        if dd < max_drawdown: max_drawdown = dd

                    # 마지막 진행 중인 사이클 기록 정리
                    final_val = cash + (holdings * closes[-1])
                    if holdings > 0 or cash != cycle_start_val:
                        cycle_return = ((final_val - cycle_start_val) / cycle_start_val) * 100
                        cycle_history.append({
                            "사이클": f"{cycle_number}회차 (진행중)",
                            "시작일": cycle_start_date.strftime('%Y-%m-%d'),
                            "종료일": dates[-1].strftime('%Y-%m-%d'),
                            "최대 T값": round(cycle_max_T, 2),
                            "리버스 발동": "O" if cycle_rev_triggered else "X",
                            "수익률 (%)": round(cycle_return, 2),
                            "종료 자산 ($)": round(final_val, 2)
                        })

                    # 전체 결과 및 CAGR 산출
                    total_return = ((final_val - initial_capital) / initial_capital) * 100
                    delta_days = (dates[-1] - dates[0]).days
                    years = delta_days / 365.25
                    cagr = ((final_val / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else total_return
                    
                    actual_start = dates[0].strftime('%Y-%m-%d')
                    actual_end = dates[-1].strftime('%Y-%m-%d')
                    
                    st.success("✅ V4.0 백테스트 완료!")
                    
                    # 1. 요약 결과 렌더링
                    st.markdown(f"""
                    ### 📊 백테스트 결과 요약
                    * **실제 조회된 기간:** {actual_start} ~ {actual_end}
                    * **초기 자본금:** ${initial_capital:,.2f}
                    * **최종 자산:** **${final_val:,.2f}**
                    * **누적 수익률:** **{total_return:.2f}%**
                    * **연평균 수익률 (CAGR):** **{cagr:.2f}%**
                    * **최대 낙폭(MDD):** {max_drawdown*100:.2f}%
                    
                    ### 📌 V4.0 운용 히스토리
                    * **목표 달성 전체 익절(리셋) 횟수:** **{total_reset_count}회**
                    * **소진(리버스) 모드 발동 횟수:** **{reverse_mode_count}회** (하락장 방어)
                    * **최대 진입 T값(회차):** **{max_cycle_reached:.2f}T**
                    """)
                    
                    # 2. 사이클별 내역 표 렌더링
                    st.markdown("### 🔄 사이클(회차)별 상세 내역")
                    if cycle_history:
                        cycle_df = pd.DataFrame(cycle_history)
                        st.dataframe(cycle_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("기록된 사이클 내역이 없습니다.")
                        
            except Exception as e:
                st.error(f"오류 발생: {str(e)}")
