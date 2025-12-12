# agents/parsing_agent.py

import pandas as pd
import os
from state.base_state import AgentState

class ParsingAgent:
    def run(self, state: AgentState) -> AgentState:
        print("\n--- Parsing Agent Started (Syncing Data) ---")
        
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
            
            # 24시간 제한
            if len(df_merged) > 96:
                df_merged = df_merged.iloc[:96]
                
            print(f">> Data synced! Start: {df_merged['timestamp'].iloc[0]}, Count: {len(df_merged)}")
            
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
                "timestamps": df_merged['timestamp'].dt.strftime('%H:%M').tolist()
            }
            
        except Exception as e:
            print(f"[Parsing Error] {e}")
            import traceback
            traceback.print_exc()
            state["parsed_data"] = None

        return state