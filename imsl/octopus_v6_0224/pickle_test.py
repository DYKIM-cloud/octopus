import json
import pickle
import pandas as pd


with open("{}".format("0415.pickle"), 'rb') as f: 
        model = pickle.load(f)
print(len(model.res))

for i in range(len(model.res)):
    a = model.res[i]
    f= a['target']
    e=a['params']['AddSolution=P_Injectionrate']
    d=a['params']['AddSolution=In_Injectionrate']
    c=a['params']['Heat=Temperature']
    b=a['params']['preHeat=Temperature']
    b= b*20+40
    c= c*50+200
    d=d*1150+100
    e=e*1150+100
    print(f'{i} preheat: {b}, heat: {c}, In: {d}, P: {e}, Loss: {f}')


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