import tkinter as tk
from tkinter import filedialog, messagebox
import numpy as np

# Excel 저장을 위해 필요 (없으면 xlsx 저장 부분을 주석 처리해도 됨)
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


def read_spectrum_file(path):
    """
    스펙트럼 txt 파일 하나를 읽어서
    (wavelengths, intensities) = (1D numpy array, 1D numpy array) 형태로 반환.
    """
    wavelengths = []
    intensities = []

    in_data = False
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # 데이터 시작 지점 찾기
            if "Begin Spectral Data" in line:
                in_data = True
                continue

            if not in_data:
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            try:
                wl = float(parts[0])
                val = float(parts[1])
            except ValueError:
                # 숫자로 변환 안 되면 스킵
                continue

            wavelengths.append(wl)
            intensities.append(val)

    if not wavelengths:
        raise ValueError(f"데이터를 읽을 수 없습니다: {path}")

    return np.array(wavelengths), np.array(intensities)


def process_files():
    # 1) 파일 선택 (n개)
    filepaths = filedialog.askopenfilenames(
        title="스펙트럼 파일을 선택하세요 (여러 개 선택 가능)",
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
    )

    if not filepaths:
        return  # 선택 취소

    try:
        base_wl = None
        sum_intensity = None
        n_files = 0

        for i, path in enumerate(filepaths):
            wl, inten = read_spectrum_file(path)

            if base_wl is None:
                # 첫 파일: 기준 파장 및 합 배열 초기화
                base_wl = wl
                sum_intensity = inten.astype(float)
            else:
                # 길이 체크
                if len(wl) != len(base_wl):
                    raise ValueError(
                        f"파일 간 데이터 길이가 다릅니다.\n"
                        f"기준 파일 길이: {len(base_wl)}, 이 파일 길이: {len(wl)}\n{path}"
                    )
                # 파장값이 같은지(허용 오차 안에서) 체크
                if not np.allclose(wl, base_wl, rtol=1e-6, atol=1e-6):
                    raise ValueError(
                        f"파일 간 파장 축이 다릅니다.\n"
                        f"문제 파일: {path}"
                    )

                sum_intensity += inten

            n_files += 1

        if n_files == 0:
            messagebox.showerror("Error", "선택된 파일이 없습니다.")
            return

        avg_intensity = sum_intensity / n_files

        # 2) 저장 파일 선택 (txt or xlsx)
        save_path = filedialog.asksaveasfilename(
            title="저장할 파일 이름을 선택하세요",
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("Excel file", "*.xlsx")]
        )

        if not save_path:
            return  # 저장 취소

        if save_path.lower().endswith(".txt"):
            # 탭으로 구분된 텍스트 저장
            with open(save_path, "w", encoding="utf-8") as f:
                f.write("Wavelength\tAverage_Intensity\n")
                for wl, val in zip(base_wl, avg_intensity):
                    f.write(f"{wl:.3f}\t{val:.6f}\n")

        elif save_path.lower().endswith(".xlsx"):
            if not HAS_PANDAS:
                messagebox.showerror(
                    "Error",
                    "pandas가 설치되어 있지 않아 Excel로 저장할 수 없습니다.\n"
                    "터미널에서 'pip install pandas openpyxl'을 실행한 뒤 다시 시도해주세요."
                )
                return
            df = pd.DataFrame({
                "Wavelength": base_wl,
                "Average_Intensity": avg_intensity
            })
            df.to_excel(save_path, index=False)
        else:
            messagebox.showerror("Error", "지원되지 않는 확장자입니다. .txt 또는 .xlsx를 사용하세요.")
            return

        messagebox.showinfo("완료", f"평균 스펙트럼을 저장했습니다.\n\n파일: {save_path}")

    except Exception as e:
        messagebox.showerror("Error", str(e))


def main():
    root = tk.Tk()
    root.title("Average Spectrum (2nd column)")
    root.geometry("400x150")

    label = tk.Label(
        root,
        text=(
            "여러 개의 스펙트럼 txt 파일을 선택하면\n"
            "두 번째 열(강도)을 평균 내어\n"
            "txt 또는 xlsx로 저장합니다."
        )
    )
    label.pack(pady=15)

    btn = tk.Button(root, text="Select files and make average", command=process_files)
    btn.pack(pady=10)

    root.mainloop()


if __name__ == "__main__":
    main()
