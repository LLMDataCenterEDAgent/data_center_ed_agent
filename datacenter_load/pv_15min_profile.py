import pandas as pd
from pathlib import Path

# ================== 설정 ==================
DATA_DIR = Path(r"D:\data_center_ed_agent\datacenter_load")

PV_EXCEL_FILE = "한국남부_남제주소내태양광_2020.xlsx"  # 원본 PV p.u. 데이터
P_RATED_MW = 100.0                                   # PV 설비 용량 [MW]

# 사용할 날짜 (0-based index)
# 0 → 엑셀에서 실제 1일차(2020-01-01)
TARGET_DAY_INDEX = 0

# ED 기준 시작 시간 (DC 부하 기준 시간축과 맞추고 싶으면 여기 조정)
ED_START_KST = pd.Timestamp("2021-04-03 09:00:00", tz="Asia/Seoul")

# 출력 해상도
ED_FREQ = "15min"

# 시간 시프트 (예: -9 → 전체 타임스탬프를 9시간 앞으로 당김)
TIME_SHIFT_HOURS = -9

# 출력 파일 이름
OUT_FILE = "pv_profile_15min_ED_final.csv"
# ======================================


def main():
    # 1) 엑셀 읽기 (header 없음)
    excel_path = DATA_DIR / PV_EXCEL_FILE
    pv_raw = pd.read_excel(excel_path, header=None)

    # 2) 헤더/인덱스 제거 후 순수 p.u. 데이터만 추출
    #    row 0: 시간 헤더 (0~23), col 0: 날짜 인덱스 → 둘 다 제거
    pv_pu_table = pv_raw.iloc[1:, 1:25].reset_index(drop=True)  # shape ~ (365, 24)

    # 3) 특정 날짜(TARGET_DAY_INDEX)의 24시간 p.u. 값 선택
    pv_pu_1h = pv_pu_table.iloc[TARGET_DAY_INDEX].to_numpy(dtype=float)

    # 4) p.u. → MW 변환
    pv_MW_1h = pv_pu_1h * P_RATED_MW

    # 5) 1시간 단위 타임스탬프 생성 (KST)
    t_index_1h = pd.date_range(
        start=ED_START_KST,  # 예: 2021-04-03 09:00 ~ 24시간
        periods=24,
        freq="1H",
    )

    df_1h = (
        pd.DataFrame({"timestamp_kst": t_index_1h, "pv_power_MW": pv_MW_1h})
        .set_index("timestamp_kst")
    )

    # 6) 15분 해상도로 리샘플링 (에너지 보존 위해 ffill)
    df_15min = df_1h.resample(ED_FREQ).ffill()

    # 7) 시간 시프트 적용 (전체 타임스탬프를 TIME_SHIFT_HOURS 만큼 이동)
    if TIME_SHIFT_HOURS != 0:
        df_15min.index = df_15min.index + pd.Timedelta(hours=TIME_SHIFT_HOURS)

    # 8) 타임존 꼬리표(+09:00) 제거 → naive datetime으로 변환
    if df_15min.index.tz is not None:
        df_15min.index = df_15min.index.tz_localize(None)

    # 9) 간단 검증 출력
    dt_hours = 15.0 / 60.0
    P_max = df_15min["pv_power_MW"].max()
    P_avg = df_15min["pv_power_MW"].mean()
    E_day = (df_15min["pv_power_MW"] * dt_hours).sum()
    CF_day = E_day / (P_RATED_MW * 24.0) if P_RATED_MW > 0 else float("nan")

    print("===== PV 15분 ED 프로파일 생성 결과 =====")
    print(f"원본 엑셀: {excel_path}")
    print(f"선택 day index: {TARGET_DAY_INDEX}")
    print(f"시작 시각 (원래 기준): {ED_START_KST}")
    print(f"시간 시프트: {TIME_SHIFT_HOURS} 시간")
    print(f"최종 시작 시각: {df_15min.index[0]}")
    print(f"타임스텝 수: {len(df_15min)} (15분 기준 96 expected)")
    print("---- 출력 특성 ----")
    print(f"피크 출력:  {P_max:.3f} MW")
    print(f"평균 출력:  {P_avg:.3f} MW")
    print(f"하루 에너지: {E_day:.2f} MWh")
    print(f"하루 CF: {CF_day:.4f}")
    print("=======================================")

    # 10) CSV 저장
    out_path = DATA_DIR / OUT_FILE
    df_15min.reset_index(names=["timestamp_kst"])[
        ["timestamp_kst", "pv_power_MW"]
    ].to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"저장 완료: {out_path}")


if __name__ == "__main__":
    main()
