"""Run training for AE"""
import torch
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader
import numpy as np
import pickle

import pipeline.config
from pipeline.AutoEncoders import VanillaAE
import pipeline.utils

settings = pipeline.config.Config

MODEL_FP = "models/AE"
RESULTS_FP = "results/"
BATCH = 128


def main():
    #data
    X = np.load(settings.X_FP)
    n, M = X.shape
    hist_idx = int(M * settings.HIST_FRAC)
    hist_X = X[:, : hist_idx]
    test_X = X[:, hist_idx : -3] #leave final three elements for DA

    #Dataloaders
    train_dataset = TensorDataset(torch.Tensor(hist_X.T))
    train_loader = DataLoader(train_dataset, BATCH, shuffle=True)
    test_dataset = TensorDataset(torch.Tensor(test_X.T))
    test_loader = DataLoader(test_dataset, test_X.shape[1])

    print("train_size = ", len(train_loader.dataset))
    print("test_size = ", len(test_loader.dataset))


    #training hyperparams
    num_epoch = 120
    device = utils.ML_utils.get_device()
    latent_dims = [1, 2, 4, 10, 20, 40, 75, 100, 150, 200]
    #AE hyperparams
    input_size = n
    layers = [1000, 200]

    for latent_size in latent_dims:
        model_fp = "{}_dim{}_epoch{}.pth".format(MODEL_FP, latent_size, num_epoch)
        results_fp_train = "{}dim{}_epoch{}_train.txt".format(RESULTS_FP, latent_size, num_epoch)
        results_fp_test = "{}dim{}_epoch{}_test.txt".format(RESULTS_FP, latent_size, num_epoch)

        loss_fn = torch.nn.L1Loss(reduction='sum')
        model = VanillaAE(input_size, latent_size, layers)
        optimizer = optim.Adam(model.parameters())


        print(model)
        train_losses, test_losses = utils.ML_utils.training_loop_AE(model, optimizer, loss_fn, train_loader, test_loader,
            num_epoch, device, print_every=1, test_every=5)
        with open(results_fp_train, 'wb') as fp:
            pickle.dump(train_losses, fp)
        with open(results_fp_test, 'wb') as fp:
            pickle.dump(test_losses, fp)
        torch.save(model.state_dict(), model_fp)

if __name__ == "__main__":
    main()
