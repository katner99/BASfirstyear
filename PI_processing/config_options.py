import sys
import os
import numpy as np
import xarray as xr
from funcs import find_nearest
from mitgcm_python.grid import Grid
from directories_and_paths import *


grid = Grid(grid_filepath)
grid_file = xr.open_dataset(grid_filepath, decode_times=False)

depth_range = [find_nearest(grid_file.Z.values, -200),find_nearest(grid_file.Z.values, -700)]

lat_range_73 = find_nearest(grid_file.YC.values, -73)
lon_range_73 = [find_nearest(grid_file.XC.values, 252.8),find_nearest(grid_file.XC.values, 255)]

sv = 10**(-6)

lat_bin, lon_bin, time_bin = 192, 288, 365

days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
