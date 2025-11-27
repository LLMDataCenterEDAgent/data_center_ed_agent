# -*- coding: utf-8 -*-
import os, glob, sys
from datetime import datetime, timezone
from collections import Counter
import pandas as pd

print("Using Python:", sys.executable)

# ────────────────────────────────
# 사용자 설정
base_dir = r"D:\MIT Supercloud Dataset\202201\gpu"     # 0001~0099 폴더를 포함하는 상위 디렉토리
save_dir = r"C:\Users\Myungsuk\Desktop\새 폴더"
os.makedirs(save_dir, exist_ok=True)

# 분석 기간 (UTC)
start_ts = datetime(2021, 4, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp()
end_ts   = datetime(2021, 4, 30, 23, 59, 59, tzinfo=timezone.utc).timestamp()

# 15분(900초) 단위로 묶기 위한 크기
BIN_SIZE = 15 * 60  

# 폴더 리스트: 0001 ~ 0099
folders = [f"{i:04d}" for i in range(1, 100)]
# ────────────────────────────────

if not os.path.isdir(base_dir):
    print("ERROR: base_dir 경로가 없습니다:", base_dir)
    sys.exit(1)

# 15분 구간별 합계와 건수 카운터
sum_power = Counter()
cnt_power = Counter()

for folder in folders:
    folder_path = os.path.join(base_dir, folder)
    if not os.path.isdir(folder_path):
        continue

    print(f"[{folder}] 처리 중...")
    # merged_ 제외한 CSV 전부
    csvs = glob.glob(os.path.join(folder_path, "*.csv"))
    csvs = [f for f in csvs if not os.path.basename(f).startswith("merged_")]

    for fp in csvs:
        try:
            # 헤더에서 인덱스 찾기
            with open(fp, 'r', encoding='utf-8', errors='replace') as f:
                hdr = next(f).split(',')
                ts_i = hdr.index('timestamp')
                pw_i = hdr.index('power_draw_W')
        except Exception:
            continue

        # 데이터 읽어서 15분 bin에 누적
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

                # 15분 bin 키 계산
                bin_key = int(ts // BIN_SIZE) * BIN_SIZE
                sum_power[bin_key] += pw
                cnt_power[bin_key] += 1

# 카운터를 DataFrame 으로 변환
records = []
for bin_ts in sorted(sum_power):
    total_pw = sum_power[bin_ts]
    count   = cnt_power[bin_ts]
    avg_pw  = total_pw / count if count else 0.0
    # UTC epoch → 사람이 읽을 수 있는 시간으로 변환
    time_str = datetime.fromtimestamp(bin_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    records.append((time_str, avg_pw))

df = pd.DataFrame(records, columns=['period_start_UTC', 'avg_power_draw_W'])
out_path = os.path.join(save_dir, "1_month_15min.csv")
df.to_csv(out_path, index=False)

print(f"15분 단위 평균 전력 데이터 저장 완료 → {out_path}")
