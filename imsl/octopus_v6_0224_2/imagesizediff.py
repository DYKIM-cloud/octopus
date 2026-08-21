import cv2, numpy as np, pandas as pd, matplotlib.pyplot as plt
from skimage.feature import blob_log
from skimage.filters import median
from skimage.morphology import disk
from pathlib import Path

# === 사용자 설정 ===
img_path = "100000X0006.jpg"
nm_per_px = 50/920  # 예: 스케일바 20 nm가 80 px이면 20/80=0.25 nm/px
min_d_nm, max_d_nm = 3.0, 6.0  # 기대 지름 범위
# ==================

# 1) 로드/전처리
g = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)

g = cv2.equalizeHist(g)
g = median(g, disk(1))

# 2) LoG-blob으로 원형 입자 탐지 (sigma ~ 반지름/√2)
min_sigma = (min_d_nm/2)/nm_per_px/np.sqrt(2)
max_sigma = (max_d_nm/2)/nm_per_px/np.sqrt(2)
blobs = blob_log(255-g, min_sigma=min_sigma, max_sigma=max_sigma, num_sigma=15, threshold=0.02)

# 3) blob_log는 sigma를 줌 → 지름(px)=2*sqrt(2)*sigma, nm 변환
rows = []
for (y, x, sigma) in blobs:
    d_px = 2*np.sqrt(2)*sigma
    d_nm = d_px * nm_per_px
    rows.append({"x_px":x, "y_px":y, "d_px":d_px, "d_nm":d_nm})

df = pd.DataFrame(rows)
mean_d = df["d_nm"].mean()
std_d  = df["d_nm"].std(ddof=1)
cv_pct = 100*std_d/mean_d

print(f"Mean diameter: {mean_d:.2f} ± {std_d:.2f} nm ({cv_pct:.1f}%)")
df.to_csv("particle_sizes_nm.csv", index=False)

# 4) 히스토그램/오버레이 저장
plt.figure(); plt.hist(df["d_nm"], bins=15); plt.xlabel("Diameter (nm)"); plt.ylabel("Count"); plt.tight_layout()
plt.savefig("histogram_nm.png", dpi=300)

rgb = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
for _, r in df.iterrows():
    R = (r["d_px"]/2)
    cv2.circle(rgb, (int(r["x_px"]), int(r["y_px"])), int(R), (255,0,0), 1)
cv2.imwrite("overlay_detected.png", rgb)
