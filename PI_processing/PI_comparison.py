from funcs import read_variable, find_nearest
from plots import create_mask
from directories_and_paths import *
from mitgcm_python.grid import Grid

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib import ticker

import sys
import numpy as np
import xarray as xr

def comparison(graph_params, data, X, Y, color_scheme, land_mask, colors, mask, experiment, title, file_out, save=True, show=False, linearity=False, residual = None):
    total = len(data)
    
    fig, axs = plt.subplots(nrows=total, ncols=total, gridspec_kw={"hspace": 0.5, "wspace": 0.4}, figsize=graph_params["figsize"])

    axs = axs.flatten()
    print(type(data))
    print(np.shape(data))

    if linearity:
        position = total-1
        cs = axs[position].contourf(X, Y, residual, cmap=color_scheme, extend="both", levels=np.linspace(np.min(residual), -np.min(residual), graph_params["step"]), locator=ticker.LogLocator())
        axs[position].contourf(X, Y, land_mask, cmap=matplotlib.colors.ListedColormap(colors))
        axs[position].contour(X, Y, mask, 2, cmap="Greys", linestyles="dashed")
        fig.colorbar(cs, ax=axs[position], ticks=np.arange(int(np.min(residual)), int(-np.min(residual)), 0.5))
        axs[position].set_title("Residual", fontsize=graph_params["font_size"], weight="bold")
    
    for i in range(total):

        # MAIN GRAPH
        diagonal = (total+1)*i

        cs = axs[diagonal].contourf(X, Y, data[i], cmap=color_scheme, extend="both", levels=np.linspace(graph_params["low_val"], graph_params["high_val"], graph_params["step"]))
        axs[diagonal].contourf(X, Y, land_mask, cmap=matplotlib.colors.ListedColormap(colors))
        axs[diagonal].contour(X, Y, mask, 2, cmap="Greys", linestyles="dashed")
        fig.colorbar(cs, ax=axs[diagonal])
        # , ticks=np.arange(graph_params["low_val"], graph_params["high_val"], 0.5)
        axs[diagonal].set_title(experiment[i], fontsize=graph_params["font_size"], weight="bold")

        # ANOMALY
        for j in range(i+1, total):
            anomaly = (total*j)+i
            cs = axs[anomaly].contourf(X, Y, data[j] - data[i], cmap=color_scheme, extend="both", levels=np.linspace(graph_params["low_val_anom"], graph_params["high_val_anom"], graph_params["step"]))
            axs[anomaly].contourf(X, Y, land_mask, cmap=matplotlib.colors.ListedColormap(colors))
            axs[anomaly].contour(X, Y, mask, 2, cmap="Greys", linestyles="dashed")
            fig.colorbar(cs, ax=axs[anomaly])
            # , ticks=graph_params["ticks_anom"]
            axs[anomaly].set_title(experiment[j]+" - "+experiment[i], fontsize=graph_params["font_size"])
            axs[anomaly].set_ylabel("Latitude", fontsize=graph_params["font_size"])

        # discarded graphs
        for k in range(i):
            axs[i + (total*k)].axis("off")
        
    fig.suptitle(title, fontsize=16)

    # save figure
    if save == True:
        fig.savefig(file_out)

    # show figure
    if show == True:
        plt.show()
       

def main():
    """
    Main function that reads the command line arguments, checks them for validity,
    loads the input data and calls the appropriate plotting function.
    """
        
    # set up the variables you need
    var = "SIfwfrz"
    save = True
    show = True
    
    # load up the file paths for the monster, needed 4
    filepaths = [output_path + ens + "_ensemble_mean_2090.nc" for ens in ["CTRL", "LENS", "WIND", "THERM"]]
    # check if the input files exist
    for filepath in filepaths:
        try:
            open(filepath)
        except FileNotFoundError:
            sys.exit(f"Stopped - Could not find input file {filepath}")

    experiment = ["pre-industrial", "high-emissions", "wind forcing", "thermodynamic f."]

    # load up the input data
    input_data = [xr.open_dataset(filepath) for filepath in filepaths]

    # read in the general variables (these should be the same between the ensembles
    [lat, lon, ice_mask_temp, depth] = [input_data[0][param].values for param in ["YC", "XC", "maskC", "Depth"]]
    ice_mask = ice_mask_temp[0,:,:]

    grid = Grid(grid_filepath)

    # temperature
    if var == "THETA":
        depth_range = [find_nearest(input_data[0]["Z"].values, -200), find_nearest(input_data[0]["Z"].values, -700)]
        data = [read_variable(input, var, grid, depth_range) for input in input_data]
        color_scheme = "coolwarm"

    # sea ice tickness
    elif var in ["SIheff", "oceFWflx", "SIfwmelt", "SIfwfrz", "EXFvwind", "oceQnet"]:
        data = [read_variable(input, var, grid) for input in input_data]
        #color_scheme = "YlGnBu_r"
        color_scheme = "seismic"

    # salinity
    elif var == "SALT":
        data = [read_variable(input, var, grid) for input in input_data]
        color_scheme = "PRGn_r"

    # set mask
    [land_mask, mask, colors] = create_mask(depth, ice_mask)

    # set up the grid
    [X, Y] = np.meshgrid(lon, lat)

    # graph parameters 1.333112e-05 -1.0214189e-06
    graph_params = {
        "figsize": (18, 12),
        "font_size": 12,
        "low_val": -1.0214189e-06,
        "high_val": 0.1333112e-05,
        "step": 15,
        "low_val_anom": -1,
        "high_val_anom": 1,
        "ticks_anom": np.arange(-2, 2.5, 0.5)
    }

    title = "THETA 2090s"
    file_out = "mega_comparison"+var+"_2090.png"

    print(np.shape(data[1]))

    residual = data[0]+data[1]-data[2]-data[3]

    print(np.max(residual), np.min(residual))

    comparison(graph_params, data, X, Y, color_scheme, land_mask, colors, mask, experiment, title, file_out, save, show)

       
            
if __name__ == '__main__':
    main() # run the program

