import json
import pickle
import sys
import pandas as pd

sys.path.insert(0, ".")
from Algorithm.Bayesian.BOdiscreteTest import ASLdiscreteBayesianOptimization as BO

PICKLE_PATH = "0415.pickle"

with open(PICKLE_PATH, 'rb') as f:
    model = pickle.load(f)
print(len(model.res))

# model.prange를 그대로 사용해서 비정규화 (하드코딩된 min/max 대신 pickle 스스로가 기억하는 범위 사용)
for i in range(len(model.res)):
    a = model.res[i]
    target = a['target']
    norm_params = a['params']

    real_params = {}
    for key, (lo, hi, step) in model.prange.items():
        real_params[key] = norm_params[key] * (hi - lo) + lo

    # Ratio/TotalFlowrate 파라미터라면, 참고용으로 실제 In/P Injectionrate도 함께 보여줌
    hw_params = BO.toHardwareParams(real_params)

    print(f"{i} {real_params}  ->  In/P: "
          f"In={hw_params.get('AddSolution=In_Injectionrate')}, "
          f"P={hw_params.get('AddSolution=P_Injectionrate')}, "
          f"Loss: {target}")


'''
with open("results_param.txt", "w", encoding="utf-8") as out:
    for i in range(len(model.res)):
        a = model.res[i]
        e = a['params']['AddSolution=A_Injectionrate']
        d = a['params']['AddSolution=InP_Injectionrate']
        c = a['params']['Heat=Temperature']
        b = a['params']['preHeat=Temperature']

        # scale
        b = b * 20 + 40
        c = c * 50 + 200
        d = d * 1150 + 100
        e = e * 1150 + 100

        # requested f
        f = 24000*60 // (d + e)

        # write one line per result
        out.write(f"In:P={int(d)}:{int(e)};{int(b)}C;{int(c)}C {int(b)},{int(c)} {int(f)}\n")

        # (선택) 화면에도 확인용 출력
        # print(f'{i} preheat: {b}, heat: {c}, In: {d}, P: {e}, f: {f}')

#print(model.res)
'''
'''
loss_dict = []
for i in range(len(model.res)-1):
    #print(model.res[i])
    loss_dict.append(model.res[i])

with open("summary.json", "w") as f:
    json.dump(loss_dict, f, indent=4)
'''
