import torch
from torch import nn
from pipeline.nn.conv import FactorizedConv


class ResBlockSlim(nn.Module):

    def __init__(self, activation_fn, in_channels, out_channels):
        super(ResBlockSlim, self).__init__()
        self.act_fn = activation_fn

        self.conv1x1 = nn.Conv3d(in_channels, out_channels, kernel_size=(1, 1, 1), stride=(1,1,1))
        conv_kwargs1 = {"in_channels": out_channels,
                        "out_channels": out_channels,
                        "kernel_size": (3, 3, 3),
                        "stride": (1,1,1),
                        "padding": (1,1,1)}
        conv_kwargs2 = conv_kwargs1.copy()
        conv_kwargs2["out_channels"] = in_channels
        self.conv1 = FactorizedConv(self.act_fn, **conv_kwargs1)
        self.conv2 = FactorizedConv(self.act_fn, **conv_kwargs2)


    def forward(self, x):
        h = self.act_fn(self.conv1x1(x))
        h = self.act_fn(self.conv1(h))
        h = self.conv2(h)
        return h + x

class DRU(nn.Module):

    """Dense Residual Unit as described in: CNN-Optimized Image
    Compression with Uncertainty based Resource Allocation.

    These blocks can be used as a method of upsampling
    - they double the input size (in all directions) by s.f. 2 """


    def __init__(self, activation_fn, channel, downsample_div=4):
        super(DRU, self).__init__()
        self.act_fn = activation_fn
        channel_down = (channel // downsample_div) if (channel // downsample_div > 0) else 1
        self.conv1x1 = nn.Conv3d(channel, channel_down, kernel_size=(1, 1, 1), stride=(1,1,1))
        self.conv2 = nn.Conv3d(channel_down, channel_down, kernel_size=(3, 3, 3), stride=(1,1,1), padding=(1,1,1))
        self.conv3 = nn.Conv3d(channel_down, channel, kernel_size=(3, 3, 3), stride=(1,1,1), padding=(1,1,1))

    def forward(self, x):
        h = self.act_fn(self.conv1x1(x))
        h = self.act_fn(self.conv2(h))
        h = self.conv3(h)
        h = h + x
        return torch.cat([h, x])
