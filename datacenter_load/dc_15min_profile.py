import pandas as pd
import numpy as np
from pathlib import Path

# ================== 설정 ==================
DATA_DIR = Path(r"D:\data_center_ed_agent\datacenter_load")
FILE_NAME = "1_day_data_scaled_300MW_PUE1.5.csv"

# 전체 부하 컬럼 이름 (1~3단계 결과에서 썼던 이름)
TOTAL_COL = "power_total_scaled_MW"

# 유닉스 타임스탬프가 들어있는 컬럼 이름 (여기를 실제 컬럼명으로 바꿔줘!)
UNIX_COL = "timestamp"   # 예: "timestamp" 또는 "time" 등

# ED 타임스텝: 15분
ED_FREQ = "15T"   # 15-minute
ED_DT_MIN = 15    # 15 minutes
# ======================================


def main():
    csv_path = DATA_DIR / FILE_NAME
    if not csv_path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {csv_path}")

    df = pd.read_csv(csv_path)

    if TOTAL_COL not in df.columns:
        raise ValueError(f"CSV에 '{TOTAL_COL}' 컬럼이 없습니다. 실제 컬럼명을 확인해 주세요.")

    if UNIX_COL not in df.columns:
        raise ValueError(f"CSV에 유닉스 타임 컬럼 '{UNIX_COL}' 이 없습니다. 실제 컬럼명을 확인해 주세요.")

    # ------------------------------------------------
    # 1) Unix time(초, UTC 기준)을 KST(datetime)으로 변환
    #    예: 1617408000 → 2021-04-03 09:00:00 (KST)
    # ------------------------------------------------
    df["timestamp_kst"] = (
        pd.to_datetime(df[UNIX_COL], unit="s", utc=True)   # UTC 기준 datetime
          .dt.tz_convert("Asia/Seoul")                     # KST(UTC+9)로 변환
          .dt.tz_localize(None)   # ← 이 줄이 tz 정보 제거
    )

    # 리샘플을 위해 index를 KST timestamp로 설정
    df = df.set_index("timestamp_kst")

    # ------------------------------------------------
    # 2) 15분 평균으로 리샘플링 (ED 타임스텝용 프로파일 생성)
    # ------------------------------------------------
    df_15min = df.resample(ED_FREQ).mean()

    # ED에 쓸 부하 시계열
    P_15 = df_15min[TOTAL_COL].to_numpy(dtype=float)
    N_15 = len(P_15)

    # 15분 간격 (초/시간 기준)
    dt_min = ED_DT_MIN
    dt_hours = dt_min / 60.0
    dt_seconds = dt_min * 60.0

    # ------------------------------------------------
    # 3) 15분 기준 부하율 (Load factor)
    # ------------------------------------------------
    P_peak_15 = P_15.max()
    P_avg_15 = P_15.mean()
    load_factor_15 = P_avg_15 / P_peak_15 if P_peak_15 > 0 else np.nan

    # ------------------------------------------------
    # 4) 15분 램프 특성 (ΔP/Δt)
    # ------------------------------------------------
    dP_15 = np.diff(P_15)  # MW 단위 차이 (15분 간격)

    # MW per 15min (그냥 dP 자체)
    ramp_MW_per_15min = dP_15

    # MW per min
    ramp_MW_per_min = dP_15 / dt_min

    ramp_stats_15 = {
        "max_up_MW_per_15min": np.max(ramp_MW_per_15min),
        "max_down_MW_per_15min": np.min(ramp_MW_per_15min),
        "p95_abs_MW_per_15min": np.percentile(np.abs(ramp_MW_per_15min), 95),

        "max_up_MW_per_min": np.max(ramp_MW_per_min),
        "max_down_MW_per_min": np.min(ramp_MW_per_min),
        "p95_abs_MW_per_min": np.percentile(np.abs(ramp_MW_per_min), 95),
    }

    # ------------------------------------------------
    # 5) 15분 기준 에너지 (하루/연간)
    # ------------------------------------------------
    E_day_MWh_15 = P_15.sum() * dt_hours
    E_year_GWh_15 = E_day_MWh_15 * 365.0 / 1000.0

    # ------------------------------------------------
    # 6) ED 입력용 CSV 저장 (KST 타임스탬프 포함)
    # ------------------------------------------------
    out_profile_path = DATA_DIR / "dc_profile_15min_ED.csv"
    df_15min.reset_index()[["timestamp_kst", TOTAL_COL]].to_csv(out_profile_path, index=False)

    # ------------------------------------------------
    # 7) 결과 출력
    # ------------------------------------------------
    print("===== 15분 ED 프로파일 & 램프 보완 결과 =====")
    print(f"입력 파일(1초): {csv_path}")
    print(f"출력 파일(15분 ED 프로파일): {out_profile_path}")
    print()
    print(f"1초 → 15분 리샘플링 후 스텝 수: {N_15} 개 (하루 96개 예상)")
    print()
    print("---- 15분 기준 부하율 ----")
    print(f"피크 부하 P_peak_15: {P_peak_15:.3f} MW")
    print(f"평균 부하 P_avg_15:  {P_avg_15:.3f} MW")
    print(f"부하율 Load factor(15분): {load_factor_15:.4f}")
    print()
    print("---- 15분 기준 램프 특성 ----")
    print(f"최대 상승: {ramp_stats_15['max_up_MW_per_15min']:.3f} MW/15min "
          f"({ramp_stats_15['max_up_MW_per_min']:.3f} MW/min)")
    print(f"최대 하락: {ramp_stats_15['max_down_MW_per_15min']:.3f} MW/15min "
          f"({ramp_stats_15['max_down_MW_per_min']:.3f} MW/min)")
    print(f"95% 절대값: {ramp_stats_15['p95_abs_MW_per_15min']:.3f} MW/15min "
          f"({ramp_stats_15['p95_abs_MW_per_min']:.3f} MW/min)")
    print()
    print("---- 15분 기준 에너지 ----")
    print(f"하루 에너지: {E_day_MWh_15:.2f} MWh")
    print(f"연간 에너지(365일 가정): {E_year_GWh_15:.2f} GWh")
    print("=============================================")


if __name__ == "__main__":
    main()
