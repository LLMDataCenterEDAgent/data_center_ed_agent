# agents/parsing_agent.py

import pandas as pd
import os
from state.base_state import AgentState

class ParsingAgent:
    def run(self, state: AgentState) -> AgentState:
        print("\n--- Parsing Agent Started (Syncing Data) ---")
        scenario_config = state.get("scenario_config") or {}
        interval_minutes = int(scenario_config.get("interval_minutes", 15) or 15)
        if interval_minutes not in (15, 30, 60):
            print(f"[Parsing Warning] Unsupported interval {interval_minutes}; falling back to 15 minutes.")
            interval_minutes = 15
        aggregation_factor = max(1, interval_minutes // 15)
        
        # 파일 경로
        load_path = "datacenter_load/dc_profile_15min_ED.csv"
        pv_path = "datacenter_load/pv_profile_15min_ED.csv"
        
        try:
            # 1. Load 읽기
            if not os.path.exists(load_path) or not os.path.exists(pv_path):
                print(f"[Error] Files not found.")
                return state
                
            df_load = pd.read_csv(load_path)
            df_pv = pd.read_csv(pv_path)
            
            # 2. 시간 컬럼 찾기 & 통일
            t_col_load = [c for c in df_load.columns if 'time' in c.lower() or 'kst' in c.lower()][0]
            t_col_pv = [c for c in df_pv.columns if 'time' in c.lower() or 'kst' in c.lower()][0]
            
            df_load.rename(columns={t_col_load: 'timestamp'}, inplace=True)
            df_pv.rename(columns={t_col_pv: 'timestamp'}, inplace=True)
            
            df_load['timestamp'] = pd.to_datetime(df_load['timestamp'])
            df_pv['timestamp'] = pd.to_datetime(df_pv['timestamp'])
            
            # 3. 데이터 컬럼 찾기
            val_col_load = [c for c in df_load.columns if 'power' in c.lower() or 'load' in c.lower()][0]
            val_col_pv = [c for c in df_pv.columns if 'pv' in c.lower()][0]
            
            # 4. [핵심] 시간 동기화 (Inner Merge)
            # 09:00 Load와 09:00 PV를 정확히 매칭
            df_merged = pd.merge(
                df_load[['timestamp', val_col_load]], 
                df_pv[['timestamp', val_col_pv]], 
                on='timestamp', 
                how='inner'
            )
            df_merged.sort_values('timestamp', inplace=True)
            
            # Streamlit에서 선택한 구간 반영
            start_row = int(scenario_config.get("start_row", 0) or 0)
            time_steps = int(scenario_config.get("time_steps", 96) or 96)
            start_row = max(0, min(start_row, max(len(df_merged) - 1, 0)))
            available_steps = max(1, (len(df_merged) - start_row) // aggregation_factor)
            time_steps = max(1, min(time_steps, available_steps))
            raw_rows = time_steps * aggregation_factor
            df_merged = df_merged.iloc[start_row:start_row + raw_rows].copy()

            if aggregation_factor > 1:
                df_merged["dispatch_step"] = range(len(df_merged))
                df_merged["dispatch_step"] = df_merged["dispatch_step"] // aggregation_factor
                df_merged = (
                    df_merged
                    .groupby("dispatch_step", as_index=False)
                    .agg({
                        "timestamp": "first",
                        val_col_load: "mean",
                        val_col_pv: "mean",
                    })
                )
                
            print(f">> Data synced! Start: {df_merged['timestamp'].iloc[0]}, Count: {len(df_merged)}, Interval: {interval_minutes} min")
            
            # 5. Net Load 계산
            demand_raw = df_merged[val_col_load].tolist()
            pv_raw = df_merged[val_col_pv].tolist()
            
            net_demand = []
            for d, p in zip(demand_raw, pv_raw):
                net_demand.append(max(d - p, 0.0))
            
            # 6. 결과 저장
            state["parsed_data"] = {
                "net_demand_profile": net_demand,
                "pv_profile": pv_raw,
                "timestamps": df_merged['timestamp'].dt.strftime('%H:%M').tolist(),
                "interval_minutes": interval_minutes,
            }
            
        except Exception as e:
            print(f"[Parsing Error] {e}")
            import traceback
            traceback.print_exc()
            state["parsed_data"] = None

        return state
