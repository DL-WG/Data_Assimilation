"""Helper functions"""
import torch
import numpy as np
import random
import vtktools
import pipeline.config

import vtk.util.numpy_support as nps
import vtk
import os

def set_seeds(seed = None):
    "Fix all seeds"
    if seed == None:
        seed = os.environ.get("SEED")
        if seed == None:
            raise NameError("SEED environment variable not set. Do this manually or initialize a Config class")
    seed = int(seed)
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    torch.cuda.manual_seed(seed)
    if torch.cuda.is_available():
        torch.backends.cudnn.deterministic = True

class DataLoader():
    """Class to load data from files in preparation for Data Assimilation or AE training"""
    def __init__(self):
        pass

    def get_X(self, settings):
        if settings.FORCE_GEN_X or not os.path.exists(settings.X_FP):
            fps = self.get_sorted_fps_U(settings.DATA_FP)
            X = self.create_X_from_fps(fps, settings.FIELD_NAME)
            if settings.SAVE:
                np.save(settings.X_FP, X, allow_pickle=True)
        else:
            X = np.load(settings.X_FP,  allow_pickle=True)

        return X

    @staticmethod
    def get_sorted_fps_U(data_dir):
        """Creates and returns list of .vtu filepaths sorted according
        to timestamp in name.
        Input files in data_dir must be of the
        form <XXXX>LSBU_<TIMESTEP INDEX>.vtu"""

        fps = os.listdir(data_dir)

        #extract index of timestep from file name
        idx_fps = []
        for fp in fps:
            _, file_number = fp.split("LSBU_")
            #file_number is of form '<IDX>.vtu'
            idx = int(file_number.replace(".vtu", ""))
            idx_fps.append(idx)

        #sort by timestep
        assert len(idx_fps) == len(fps)
        zipped_pairs = zip(idx_fps, fps)
        fps_sorted = [x for _, x in sorted(zipped_pairs)]

        #add absolute path
        fps_sorted = [data_dir + x for x in fps_sorted]

        return fps_sorted

    @staticmethod
    def create_X_from_fps(fps, field_name, field_type  = "scalar"):
        """Creates a numpy array of values of scalar field_name
        Input list must be sorted"""
        M = len(fps) #number timesteps

        for idx, fp in enumerate(fps):
            # create array of tracer
            ug = vtktools.vtu(fp)
            if field_type == "scalar":
                vector = ug.GetScalarField(field_name)
            elif field_type == "vector":
                vector = ug.GetVectorField(field_name)
            else:
                raise ValueError("field_name must be in {\'scalar\', \'vector\'}")
            #print("Length of vector:", vector.shape)

            vec_len, = vector.shape
            if idx == 0:
                #fix length of vectors and initialize the output array:
                n = vec_len
                output = np.zeros((M, n))
            else:
                #enforce all vectors are of the same length
                assert vec_len == n, "All input .vtu files must be of the same length."


            output[idx] = vector

        return output.T #return (n x M)

class FluidityUtils():
    """Class to hold Fluidity helper functions.
    In theory this should be part of
    vtktools.py but I have kept it seperate to avoid confusion
    as to which is my work """

    def __init__(self):
        pass


    def get_3D_grid(self, fp, field_name, npoints=None, factor_inc=2.5,
                newshape = None, save_newgrid_fp = None, ret_torch=False):
        """Returns numpy array or torch tensor of the vtu file input
        Accepts:
            :fp - str. filepath to .vtu file
            :field_name - str. name of field to extract. e.g. "pressure"
            :npoints - when newshape=None, this is the total number of points in output.
                If None, the number is (approximately) the (input number * factor_inc)
            :factor_inc - Factor by which to increase (or decrease) the number of points (when newshape=None)
            :newshape - tuple of 3 ints which gives new shape of output. Overides npoints and factor_inc
            :save_newgrid_fp - str. if not None, the restructured vtu grid will be
                saved at this location relative to the working directory

            :ret_torch - if True, returns a torch tensor. Otherwise returns a numpy array."""
        ug = vtktools.vtu(fp)

        if newshape == None:
            points = ug.ugrid.GetPoints()

            if npoints == None:
                npoints = factor_inc * points.GetNumberOfPoints()

            bounds = points.GetBounds()
            ax, bx, ay, by, az, bz = bounds

            #ranges
            x_ran, y_ran, z_ran = bx - ax, by - ay, bz - az

            spacing = (x_ran * y_ran * z_ran / npoints)**(1.0 / 3.0)

            nx = int(round(x_ran / spacing))
            ny = int(round(y_ran / spacing))
            nz = int(round(z_ran / spacing))

            newshape = (nx, ny, nz)
        else:
            (nx, ny, nz) = newshape


        struct_grid = ug.StructuredPointProbe(nx, ny, nz)

        if save_newgrid_fp:
            self.save_structured_vtu(save_newgrid_fp, struct_grid)

        pointdata = struct_grid.GetPointData()
        vtkdata = pointdata.GetScalars(field_name)
        np_data = nps.vtk_to_numpy(vtkdata)

        #Fortran order reshape (i.e first index changes fastest):
        result = np.reshape(np_data, newshape, order='F')
        if ret_torch:
            result = torch.Tensor(result)

        return result

    def save_structured_vtu(self, filename, struc_grid):
        from evtk.hl import pointsToVTK

        filename = filename.replace(".vtu", "")
        xs, ys, zs = self.__get_grid_locations(struc_grid)
        data = self.__get_grid_data(struc_grid)

        pointsToVTK(filename, xs, ys, zs, data)


    @staticmethod
    def save_vtu_file(arr, name, filename, sample_fp=None):
        """Saves an unstructured VTU file - NOTE TODO - should be using deep copy method in vtktools.py -> VtuDiff()"""
        if sample_fp == None:
            sample_fp = vda.get_sorted_fps_U(self.settings.DATA_FP)[0]

        ug = vtktools.vtu(sample_fp) #use sample fp to initialize positions on grid

        ug.AddScalarField('name', arr)
        ug.Write(filename)

    @staticmethod
    def __get_grid_locations(grid):
        npoints = grid.GetNumberOfPoints()
        xs = np.zeros(npoints)
        ys = np.zeros(npoints)
        zs = np.zeros(npoints)

        for i in range(npoints):
            loc = grid.GetPoint(i)
            xs[i], ys[i], zs[i] = loc
        return xs, ys, zs

    def __get_grid_data(self, grid):
        """Gets data and returns as dictionary (i.e. in form necessary for EVTK) """
        npoints = grid.GetNumberOfPoints()
        pointdata=grid.GetPointData()

        data = {}
        for name in self.__get_field_names(grid):
            vtkdata = pointdata.GetScalars(name)
            np_arr = nps.vtk_to_numpy(vtkdata)
            if len(np_arr.shape) == 1: #i.e. exclude vector fields
                data[name] = np_arr

        return data

    @staticmethod
    def __get_field_names(grid):
        vtkdata=grid.GetPointData()
        return [vtkdata.GetArrayName(i) for i in range(vtkdata.GetNumberOfArrays())]



class ML_utils():
    """Class to hold ML helper functions"""

    def __init__(self):
        pass

    @staticmethod
    def training_loop_AE(model, optimizer, loss_fn, train_loader, test_loader,
            num_epoch, device=None, print_every=1, test_every=5):
        """Runs a torch AE model training loop.
        NOTE: Ensure that the loss_fn is in mode "sum"
        """
        set_seeds()
        train_losses = []
        test_losses = []
        if device == None:
            device = get_device()
        for epoch in range(num_epoch):
            train_loss = 0
            model.to(device)

            for batch_idx, data in enumerate(train_loader):
                model.train()
                x, = data
                x = x.to(device)
                optimizer.zero_grad()
                y = model(x)

                loss = loss_fn(y, x)
                loss.backward()
                train_loss += loss.item()
                optimizer.step()
            train_losses.append((epoch, train_loss / len(train_loader.dataset)))
            if epoch % print_every == 0 or epoch in [0, num_epoch - 1]:
                print('epoch [{}/{}], loss:{:.4f}'.format(epoch + 1, num_epoch, train_loss / len(train_loader.dataset)))
            if epoch % test_every == 0 or epoch == num_epoch - 1:
                model.eval()
                test_loss = 0
                for batch_idx, data in enumerate(test_loader):
                    x_test, = data
                    x_test = x_test.to(device)
                    y_test = model(x_test)
                    loss = loss_fn(y_test, x_test)
                    test_loss += loss.item()
                print('epoch [{}/{}], validation loss:{:.4f}'.format(epoch + 1, num_epoch, test_loss / len(test_loader.dataset)))
                test_losses.append((epoch, test_loss/len(test_loader.dataset)))
        return train_losses, test_losses

    @staticmethod
    def load_AE(ModelClass, path, **kwargs):
        """Loads an encoder and decoder"""
        model = ModelClass(**kwargs)
        model.load_state_dict(torch.load(path))
        encoder = model.encode
        decoder = model.decode

        return encoder, decoder

    @staticmethod
    def get_device(use_gpu=True, device_idx=0):
        """get torch device type"""
        if use_gpu:
            device = torch.device("cuda:" + str(device_idx) if torch.cuda.is_available() else "cpu")
        else:
            device = torch.device("cpu")
        return device

    @staticmethod
    def jacobian_slow_torch(inputs, outputs):
        """Computes a jacobian of two torch tensor.
        Uses a loop so linear complexity in dimension of output"""
        dims = len(inputs.shape)
        return torch.transpose(torch.stack([torch.autograd.grad([outputs[:, i].sum()], inputs, retain_graph=True, create_graph=True)[0]
                            for i in range(outputs.size(1))], dim=-1), \
                            dims - 1, dims)
