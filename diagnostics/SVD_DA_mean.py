#This should be run from DA directory:
#```python3 diagnostics/SVD_DA_mean.py

import numpy as np
import os, sys
#import pipeline
parent_dir = os.path.abspath(os.path.join(os.getcwd(), os.pardir))
sys.path.append(os.getcwd()) #to import pipeline
import pipeline

from pipeline.VarDA import SVD, VDAInit
from pipeline.settings import config
from pipeline import SplitData, GetData
from pipeline import DAPipeline
import torch

import operator
from functools import reduce
def prod(iterable):
    return reduce(operator.mul, iterable, 1)


def main():
    settings = config.Config()
    settings.THREE_DIM = True
    settings.set_X_fp(settings.INTERMEDIATE_FP + "X_3D_{}.npy".format(settings.FIELD_NAME))
    settings.set_n( (91, 85, 32))
    settings.DEBUG = False
    settings.NORMALIZE = True

    #LOAD U, s, W
    fp_base = settings.get_X_fp().split("/")[-1][1:]

    U = np.load(settings.INTERMEDIATE_FP  + "U" + fp_base)
    s = np.load(settings.INTERMEDIATE_FP  + "s" + fp_base)
    W = np.load(settings.INTERMEDIATE_FP  + "W" + fp_base)

    #Load data
    loader, splitter = GetData(), SplitData()
    X = loader.get_X(settings)
    train_X, test_X, u_c, X, mean, std = splitter.train_test_DA_split_maybe_normalize(X, settings)

    u_0 = np.zeros_like(u_c) #since normalize is True

    modes = [-1, 500, 100, 50, 30, 20, 10, 8, 6, 4, 3, 2, 1]

    obs_fracs = [0.0005, 0.001, 0.003]

    modes = [2]
    obs_fracs = [0.0005]


    L1 = torch.nn.L1Loss(reduction='sum')
    L2 = torch.nn.MSELoss(reduction="sum")


    datasets = {#"train": train_X,
               "test": test_X,
                "u_c": np.expand_dims(u_c, 0),
                "mean": np.expand_dims(mean, 0),
                "u_0": np.expand_dims(u_0, 0)}
    for name, data in datasets.items():

        for obs_frac in obs_fracs:
            settings.OBS_FRAC = obs_frac
            DA_pipeline = DAPipeline(settings)

            if len(data.shape) in [1, 3]:
                num_states = 1
            else:
                num_states = data.shape[0]

            for mode in modes:
                totals = {"percent_improvement": 0,
                        "ref_MAE_mean": 0,
                        "da_MAE_mean": 0,
                        "counts": 0}

                V_trunc = SVD.SVD_V_trunc(U, s, W, modes=mode)
                V_trunc_plus = SVD.SVD_V_trunc_plus(U, s, W, modes=mode)
                DA_data = DA_pipeline.data
                DA_data["V_trunc"] = V_trunc
                DA_data["V"] = None
                DA_data["w_0"] = V_trunc_plus @ u_0.flatten()
                DA_data["V_grad"] = None

                for idx in range(num_states):
                    if num_states == 1:
                        DA_data["u_c"] = data
                    else:
                        DA_data["u_c"] = data[idx]


                    DA_data = VDAInit.provide_u_c_update_data_full_space(DA_data, settings, DA_data["u_c"])
                    DA_results = DA_pipeline.DA_SVD()

                    ref_MAE_mean = DA_results["ref_MAE_mean"]
                    da_MAE_mean = DA_results["da_MAE_mean"]
                    counts = (DA_results["da_MAE"] < DA_results["ref_MAE"]).sum()

                    #add to dict results
                    totals["percent_improvement"] += DA_results["percent_improvement"]
                    totals["ref_MAE_mean"] += ref_MAE_mean
                    totals["da_MAE_mean"] += da_MAE_mean
                    totals["counts"] += counts

                    if idx % 10 == 0:
                        print("idx:", idx)
                        print_(totals, name, obs_frac, mode, idx + 1)
                print("------------")
                print_(totals, name, obs_frac, mode, num_states)
                print("------------")






def see_how_close(x1, x2, rtol = 0.1):
    assert x1.shape == x2.shape
    shape = x1.shape
    npoints = prod(shape)

    mean = (x1 + x2) / 2
    mean = np.where(mean <= 0., 1, mean)
    diff = x1 - x2

    relative = diff / mean
    num_above = relative > rtol
    num_above = num_above.sum()
    mean_rel = relative.mean()

    print("num_above", num_above, "/", npoints)
    print("mean_rel", mean_rel)

if __name__ == "__main__":
    main()