import pickle
import os, sys
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../")))
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../../")))
import Algorithm
from scipy.optimize import minimize

def func_max(self, x):
        return -self.ac(x.reshape(1, -1), gp=self.gp, y_max=self.y_max)
def maximizer(self, x_try):
        res = minimize(self.func_max,
                       x_try.reshape(1, -1),
                       bounds=self.bounds,
                       method="L-BFGS-B")
        #res.fun[0] = -1 * res.fun[0]
        res.fun = -1 * res.fun
        return res

df_result = pickle.load(open('20250218_235713_0_6_obj.pickle','rb'))

print(df_result.res)