import json
import matplotlib.pyplot as plt
import numpy as np
import tkinter as tk
from tkinter import filedialog


file_path = filedialog.askopenfilename(title="파일 선택", filetypes=(("Json Files", "*.json"),))
if file_path:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
#result_dict = data["result"]['PL_GetPl']['Data']
result_dict = data["result"]['UV_GetAbs']['Data']
print(result_dict['Property'])
plt.plot(result_dict['Wavelength'],result_dict['RawSpectrum'])
plt.show()