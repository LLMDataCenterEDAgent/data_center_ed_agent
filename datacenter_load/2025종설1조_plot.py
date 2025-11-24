# -*- coding: utf-8 -*-
import os, glob, sys
from datetime import datetime, timezone
from collections import Counter
import pandas as pd

print("Using Python:", sys.executable)

# ────────────────────────────────
# 사용자 설정
base_dir = r"D:\MIT Supercloud Dataset\202201\gpu"
save_dir = r"C:\Users\Myungsuk\Desktop\새 폴더"
os.makedirs(save_dir, exist_ok=True)

# 분석 기간 (UTC)
start_ts = datetime(2021,4,1, tzinfo=timezone.utc).timestamp()
end_ts   = datetime(2021,4,7,23,59,59, tzinfo=timezone.utc).timestamp()

dt = 0.1  # 샘플링 주기 (초)
folders = [f"{i:04d}" for i in range(5, 100)]
# ────────────────────────────────

if not os.path.isdir(base_dir):
    print("ERROR: base_dir 경로가 없습니다:", base_dir)
    sys.exit(1)

for folder in folders:
    folder_path = os.path.join(base_dir, folder)
    if not os.path.isdir(folder_path):
        print(f"[{folder}] 폴더 없음, 스킵")
        continue

    print(f"[{folder}] started (2021-04-01 ~ 2021-04-07)")
    csvs = [f for f in glob.glob(os.path.join(folder_path, "*.csv"))
            if not os.path.basename(f).startswith("merged_")]
    total = len(csvs)
    if total == 0:
        print(f"[{folder}] CSV 없음, 스킵\n")
        continue

    acc = Counter()
    for idx, fp in enumerate(csvs, 1):
        # 헤더에서 인덱스 찾기
        try:
            with open(fp, 'r', encoding='utf-8', errors='replace') as f:
                hdr = next(f).split(',')
                ts_i    = hdr.index('timestamp')
                pw_i    = hdr.index('power_draw_W')
        except Exception:
            # 헤더 오류 시 스킵
            continue

        # 데이터 읽기
        with open(fp, 'r', encoding='utf-8', errors='replace') as f:
            next(f)
            for line in f:
                parts = line.strip().split(',')
                if len(parts) <= max(ts_i, pw_i):
                    continue
                try:
                    ts = float(parts[ts_i])
                except:
                    continue
                if ts < start_ts or ts > end_ts:
                    continue
                try:
                    pw = float(parts[pw_i])
                except:
                    continue
                # timestamp별 power 누적
                acc[round(ts,2)] += pw

        # 진행 로그
        if idx % 100 == 0 or idx == total:
            print(f"  processed {idx}/{total} files")

    if not acc:
        print(f"[{folder}] 유효 데이터 없음, 스킵\n")
        continue

    # DataFrame 생성
    df = pd.DataFrame.from_records(
        [(ts, pw, pw*dt/3600.0) for ts, pw in acc.items()],
        columns=['timestamp','power_draw_W','energy_Wh']
    )
    df.sort_values('timestamp', inplace=True)

    # 파일 저장
    out_csv = os.path.join(save_dir, f"merged_{folder}_power_energy.csv")
    df.to_csv(out_csv, index=False)
    print(f"[{folder}] completed → saved {out_csv}\n")

print("All folders processed!")  
