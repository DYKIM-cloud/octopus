import json
import pickle
import pandas as pd

'''
with open("{}".format("octopus_v7_1215\\sv\\20260120\\real\\0127core_2.pickle"), 'rb') as f: 
    model = pickle.load(f)


model.constraints = [['x[0] - x[1]', '4*x[1] - x[0] + 6/23']]
with open("3.pickle", "wb") as f:
    pickle.dump(model, f)
'''

with open("{}".format("0715_4.pickle"), 'rb') as f: 
    model = pickle.load(f)
peak_sample = 0
for i in range(0,len(model.res)):
    #print(model.res[i])
    print(model.res[i]['target'])
    #if model.res[i]['target'] >= -0.3:
    #    peak_sample =peak_sample+1
    #print(model.constraints)
print(peak_sample)