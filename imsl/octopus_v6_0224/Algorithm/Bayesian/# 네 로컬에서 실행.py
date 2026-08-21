# 네 로컬에서 실행
import pickle
import json

with open("20250602_142922_4_obj.pickle", "rb") as f:
    data = pickle.load(f)

print(data.res)