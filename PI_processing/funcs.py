import numpy as np
import sys
import xarray as xr
import os
from mitgcm_python.utils import mask_land_ice, mask_3d, add_time_dim, z_to_xyz, apply_mask
from mitgcm_python.calculus import over_area
from mitgcm_python.file_io import read_binary
from directories_and_paths import *
from scipy.interpolate import interp2d

def read_timeseries(experiments, ensemble, var):
    """
    This function reads time series data from NetCDF files for a given set of experiments and ensemble members.

    Parameters:
    - experiments: List of experiment names.
    - ensemble: List of ensemble member numbers.
    - var: Variable name to read from the files.
    - output_path: Path to the directory containing the NetCDF files.

    Returns:
    - data: A nested dictionary containing the time series data. The outer keys correspond to experiments, 
    and the inner keys correspond to ensemble members. The values are lists of time series arrays extracted
    from the NetCDF files.
    """
    data = {exp: {ens: [] for ens in ensemble} for exp in experiments}
    max_len = 181*12
    
    for exp in experiments:
        for ens in ensemble:
            if exp == "LENS":
                if ens < 6:
                    filepath = f"{output_path}lens_timeseries/timeseries2101_experiment{ens}.nc"
                else:
                    path = f"{output_path}PAS_LENS00{ens}_noOBC/"
                    valid_file = [filename for filename in os.listdir(path) if filename.startswith("timeseries")]
                    if valid_file:
                        filepath = f"{path}{valid_file[0]}"
                    else:
                        continue  # Skip this ensemble member if no valid file found
            else:
                path = f"{output_path}{exp}_ens0{ens}_noOBC/"
                valid_file = [filename for filename in os.listdir(path) if filename.startswith("timeseries")]
                if valid_file:
                    filepath = f"{path}{valid_file[0]}"
                else:
                    continue  # Skip this ensemble member if no valid file found
            
            try:
                with xr.open_dataset(filepath) as data_member:
                    timeseries = data_member[var].values
                    if len(timeseries) < max_len:
                        timeseries = np.pad(timeseries, (0, max_len - len(timeseries)), constant_values=np.nan)
                    data[exp][ens].append(timeseries)
            except Exception as e:
                print(f"Error reading file: {filepath}, {e}")
    
    return data
    
    
def find_years(start_year, filepath):
    year_directories = [name for name in os.listdir(filepath)]
    valid_directories = [year for year in year_directories if year >= start_year]
    num_years = len(valid_directories)
    print(
        "Number of years detected:"
        + str(num_years)
        + " equivalent to the following years: "
    )
    print(valid_directories)
    return num_years

def moving_average(a, n=3):
    if n < 2:
        raise ValueError("Window size (n) must be at least 2 for a centered moving average.")
    
    data = np.empty_like(a, dtype=float)
    data.fill(np.nan)

    # Calculate the cumulative sum
    cumsum = np.cumsum(np.insert(a, 0, 0))

    # Calculate the centered moving average
    half_n = n // 2
    if n % 2 == 0:
        data[half_n-1:-half_n] = (cumsum[n:] - cumsum[:-n]) / n
    else:
        data[half_n:-half_n] = (cumsum[n:] - cumsum[:-n]) / n

    return data

def find_nearest(array, value):
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    return idx
    
def binary_coords(u_or_v):
    path = '/data/oceans_input/raw_input_data/CESM/LENS/daily/'
    path += u_or_v + "/"
    data = xr.open_dataset(path + "b.e11.B1850C5CN.f09_g16.005.cam.h1."+u_or_v+".04020101-04991231.nc", decode_times=False)
    lat = data.lat.values
    lon = data.lon.values
    return lat, lon

def global_to_amundsen(input_data, var, grid):
    
    [lat, lon] = binary_coords(var)
    dimensions = ('t','y','x')

    lat_index = [find_nearest(lat, grid.lat_1d[0]), find_nearest(lat, grid.lat_1d[-1])]
    lon_index = [find_nearest(lon, grid.lon_1d[0]+360), find_nearest(lon, grid.lon_1d[-1]+360)]
    
    y_lo_res = lat[lat_index[0]:lat_index[1]]
    x_lo_res = lon[lon_index[0]:lon_index[1]]

    filename_example = f"{lens_O_path}192001/MITgcm/output.nc"
    hi_res_data = xr.open_dataset(filename_example, decode_times = False)
    x_hi_res = hi_res_data.XC.values
    y_hi_res = hi_res_data.YC.values
    
    f = interp2d(x_lo_res, y_lo_res, input_data[lat_index[0]:lat_index[1], lon_index[0]:lon_index[1]], kind = 'linear')
    data = f(x_hi_res, y_hi_res)

    return data
       
def average_over_depth(grid, data, mask, depth_range):
    dz = z_to_xyz(grid.dz, grid)[depth_range[0]:depth_range[1],: ,:]
    dz = add_time_dim(dz, data.shape[0])
    hfac = grid.hfac[depth_range[0]:depth_range[1], :, :]
    hfac = add_time_dim(hfac, data.shape[0])
    return np.sum(data*dz*hfac*mask, axis=-3)/np.sum(dz*hfac*mask, axis=-3)

def read_variable(input_data, var, grid, depth_range = None):
    # Number of days in each month
    days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

    if var in ["THETA", "SALT"]:
        data = mask_3d(input_data[var].values, grid, time_dependent=True)
        data_cut = data[:, depth_range[0]:depth_range[1], :, :]
        mask_cut = np.invert(data.mask).astype(float)[:, depth_range[0]:depth_range[1], :, :]
        return np.average(average_over_depth(grid, data_cut, mask_cut, depth_range), axis = 0, weights=days_in_month)

    #elif var == "SALT":
    #    data = mask_3d(input_data.SALT.values, grid, time_dependent=True)
    #    mask = np.invert(data.mask).astype(float)
    #    return np.average(data[:,0,:,:]*mask, axis = 0, weights=days_in_month)
    if var == "SHIfwFlx":
        return np.sum(input_data[var].values, axis = 0)
    else:
        hfac = grid.hfac[0,:,:]
        hfac = add_time_dim(hfac, input_data.time.values.shape[0])
        data = np.ma.masked_where(hfac == 0, input_data[var].values[..., :, :])
        return np.average(data, axis = 0, weights=days_in_month)
#return data[0,:,:]
       

def create_profile(input_data, var, grid, lat_range, lon_range, time = 12, timeseries = True):
    # Check if input_data contains 12 years of data
    if len(input_data.time.values) != 12:
        print('Error: input_data must contain {} years of data'.format(time))
        fillarray = np.full((12, 50), np.nan)
        return fillarray
    
    else:
        # Number of days in each month
        days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    
        # apply mask and cut over the area defined
        data = mask_3d(input_data[var].values, grid, time_dependent=True)
        data = apply_mask(data, (grid.get_hfac(gtype='t')==0) & (input_data.Depth.values >= 1500), time_dependent=True, depth_dependent=True)
        data_cut = data[:, :, lat_range[0]:lat_range[1], lon_range[0]:lon_range[1]]
        mask_cut = np.invert(data[:, :, :, :].mask).astype(float)[:, :, lat_range[0]:lat_range[1], lon_range[0]:lon_range[1]]
        dA = grid.dA
        dV = add_time_dim(dA, data.shape[1])
        dV = add_time_dim(dV, data.shape[0])    
        dV_cut = dV[:, :, lat_range[0]:lat_range[1],lon_range[0]:lon_range[1]]
    
        # calculate and return average, either a timeseries or average over the year
        if timeseries:
            return np.sum(data_cut*dV_cut*mask_cut, axis=(-2,-1))/np.sum(dV_cut*mask_cut, axis=(-2,-1))
        else:
            return np.average(np.sum(data_cut*dV_cut*mask_cut, axis=(-2,-1))/np.sum(dV_cut*mask_cut, axis=(-2,-1)), axis = 0, weights=days_in_month)
        
    
def interpolate_currents(V, zon_or_mer):
    V_interp = np.empty(np.shape(V))
    if zon_or_mer == "zonal":
        V_interp[...,:-1] = 0.5*(V[...,:-1] + V[...,1:]) 
        V_interp[...,-1] = V[...,-1]
    elif zon_or_mer == "meridional":
        V_interp[...,:-1,:] = 0.5*(V[...,:-1,:] + V[...,1:,:])
        V_interp[...,-1,:] = V[...,-1,:]
    return V_interp

# function to create timeseries over a given area slice (lat_range, lon_range)
def make_timeseries(var, input_data, grid, lat_range=None, lon_range=None, depth_range=None, time=12): 
    # Check if depth_range is set for THETA variable
    if var == 'THETA' and depth_range is None: 
        print('Error: depth_range must be set for THETA variable')
        sys.exit()

    # Prepare the data and grid for volume average
    if var == "THETA":
        data = mask_3d(input_data.THETA.values, grid, time_dependent=True)
        data_cut = data[:12, depth_range[0]:depth_range[1], lat_range[0]:lat_range[1], lon_range[0]:lon_range[1]]
        dV = grid.dV
        dV = add_time_dim(dV, data.shape[0])
        dV_cut = dV[:12, depth_range[0]:depth_range[1], lat_range[0]:lat_range[1], lon_range[0]:lon_range[1]]
        mask_cut = np.invert(data.mask).astype(float)[:12, depth_range[0]:depth_range[1], lat_range[0]:lat_range[1], lon_range[0]:lon_range[1]]
        return np.sum(data_cut * dV_cut * mask_cut, axis=(-3,-2,-1)) / np.sum(dV_cut * mask_cut, axis=(-3,-2,-1))
    
    # Prepare the data and grid for 2D average

    elif var == "SALT":
        data = mask_3d(input_data[var].values, grid, time_dependent=True)
        data_cut = data[:12, 0, lat_range[0]:lat_range[1], lon_range[0]:lon_range[1]]
        mask_cut = np.invert(data[:12, 0, :, :].mask).astype(float)[:12, lat_range[0]:lat_range[1], lon_range[0]:lon_range[1]]
        dA = grid.dA
        dA = add_time_dim(dA, data.shape[0])
        dA_cut = dA[:12, lat_range[0]:lat_range[1],lon_range[0]:lon_range[1]]
        return np.sum(data_cut*dA_cut*mask_cut, axis=(-2,-1))/np.sum(dA_cut*mask_cut, axis=(-2,-1))
        
    else:
        hfac = grid.hfac[0,:,:]
        hfac = add_time_dim(hfac, input_data.time.values.shape[0])
        data = np.ma.masked_where(hfac == 0, input_data.SIheff.values)
        dA = grid.dA
        dA = add_time_dim(dA, data.shape[0])
        return np.nanmax(data[:12,...], axis=(-2, -1))
        #return np.sum(data_cut*dA_cut*mask_cut, axis=(-2,-1))/np.sum(dA_cut*mask_cut, axis=(-2,-1))

def mask(input_data, grid, time_dependent=True):
    hfac = grid.hfac[0,:,:]
    hfac = add_time_dim(hfac==0, 12)
    data = np.ma.masked_where(hfac, input_data)
    return data

def append_years(n_years, start_year, filepath, grid, depth_range = None):
    theta_cont_shelf = []
    theta_pig = []
    theta_abbot = [] 
    theta_shelf_edge = []
    theta_dotson = []
    salt_cont_shelf = []
    seaice = []

    #run through the years
    for i in range(n_years):
        # read file of that year
        fileyear=str(start_year+i)
        print(fileyear)
        input_file = f"{filepath}{fileyear}01/MITgcm/output.nc"
        
        # check that the year exists
        try:
            input_data = xr.open_dataset(input_file, decode_times=False)
        except FileNotFoundError:
            sys.exit(f"Stopped - Could not find directory {input_file}")
           
        [lat, lon] = [input_data[param].values for param in ["YC", "XC"]]

        # create timeseries continental shelf (72 - 76S / 250 - 260)
        lon_range = [find_nearest(lon, 250), find_nearest(lon, 260)]
        lat_range = [find_nearest(lat, -76), find_nearest(lat, -72)]
        theta_cont_shelf_temp = make_timeseries("THETA", input_data, grid, lat_range, lon_range, depth_range)
        theta_cont_shelf=np.ma.append(theta_cont_shelf, theta_cont_shelf_temp)
        
        # salinity over continental shelf
        salt_temp = make_timeseries("SALT", input_data, grid, lat_range, lon_range)
        salt_cont_shelf=np.ma.append(salt_cont_shelf, salt_temp)
        
        # sea ice
        seaice_temp = make_timeseries("SIheff", input_data, grid)
        seaice=np.ma.append(seaice, seaice_temp)
        
        # pine island glacier (74 - 75.5S/ 255 - 262)
        lat_range = [find_nearest(lat, -75.5), find_nearest(lat, -74)]
        lon_range = [find_nearest(lon, 255), find_nearest(lon, 262)]
        theta_pig_temp =  make_timeseries("THETA", input_data, grid, lat_range, lon_range, depth_range)
        theta_pig=np.ma.append(theta_pig, theta_pig_temp)
        
        # shelf edge (70.5 - 72.5S/ 240 - 260) 
        lat_range = [find_nearest(lat, -72.5), find_nearest(lat, -70.5)]
        lon_range = [find_nearest(lon, 240), find_nearest(lon, 260)]
        theta_shelf_edge_temp =  make_timeseries("THETA", input_data, grid, lat_range, lon_range, depth_range)
        theta_shelf_edge=np.ma.append(theta_shelf_edge, theta_shelf_edge_temp)
        
        # abbot ice shelf (71 - 73.5 / 258 - 270)
        lat_range = [find_nearest(lat, -73.5), find_nearest(lat, -71)]
        lon_range = [find_nearest(lon, 258), find_nearest(lon, 270)]
        theta_abbot_temp =  make_timeseries("THETA", input_data, grid, lat_range, lon_range, depth_range) 
        theta_abbot=np.ma.append(theta_abbot, theta_abbot_temp)
        
        # dotson ice shelf (73 - 75.5 / 250 - 249)
        lat_range = [find_nearest(lat, -75.5), find_nearest(lat, -73)]
        lon_range = [find_nearest(lon, 240), find_nearest(lon, 249)]
        theta_dotson_temp =  make_timeseries("THETA", input_data, grid, lat_range, lon_range, depth_range)
        theta_dotson=np.ma.append(theta_dotson, theta_dotson_temp)

    return theta_cont_shelf, theta_pig, theta_abbot, theta_dotson, theta_shelf_edge, salt_cont_shelf, seaice
