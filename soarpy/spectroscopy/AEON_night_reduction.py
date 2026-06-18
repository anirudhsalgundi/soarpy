# Authors: Jonathan Carney, Github Copilot

import os
import subprocess
from pathlib import Path
from astropy.io import fits
import argparse
from argparse import RawDescriptionHelpFormatter
import numpy as np
import matplotlib.pyplot as plt
from astropy.time import Time
import requests


def setup(verbose: bool = False):
    """
    Function to get a list of target names and a start/end date for LCO data if the user doesn't provide a file with that information.

    Args:   
        verbose (bool): Whether or not to print verbose output

    Input:
        start_date (str): Start date for LCO data
        end_date (str): End date for LCO data
        targets (list): List of target names
    
    Returns:
        targets (list): List of target
        start_date (str): Start date for LCO data
        end_date (str): End date for LCO data
    """
    #get dates for LCO data
    confirm_dates = False
    while confirm_dates == False:
        start_date = input("Enter the start date (YYYY-MM-DD): ")
        end_date = input("Enter the end date (YYYY-MM-DD): ")
        print(" ")
        confirmed_dates = input(f"Start date: {start_date}, End date: {end_date}. Confirm? (y/n): ")
        if confirmed_dates == "y":
            confirm_dates = True
            print(" ")
        else:
            continue

    #get target list for LCO data
    confirm_targets = False
    targets = []
    targets.append("Calib")
    while confirm_targets == False:
        while True:
            target = input("Enter target name (or 'done' to finish): ")
            if target == "done":
                break
            else:
                targets.append(target)
        print(" ")
        print("Target list: ")
        for target in targets:
            print(target)
        print(" ")
        confirmed_targets = input("Confirm target list? (y/n): ")
        if confirmed_targets == "y":
            confirm_targets = True
            print(" ")
        else:
            continue

    return targets, start_date, end_date


def download_and_and_orgnaize_lco_data(targets: list, 
                                       start_date: str,
                                       end_date: str,
                                       mode: str = "400m1",
                                       soar_dps_path: str = "~/Research/ATALab/software/soar-dps", 
                                       keep_all_standards: bool = True,
                                       verbose: bool = False):
    """
    Function to download LCO data (using Igor's soar-dps code) and organize it into subfolders for each target. Additionally make a finding directory.

    Args:
        targets (list): List of target names
        start_date (str): Start date for LCO data in YYYY-MM-DD format
        end_date (str): End date for LCO data in YYYY-MM-DD format
        mode (str): Mode of the Goodman camera (400m1 or 400m2)
        soar_dps_path (str): Path to the soar-dps software
        verbose (bool): Whether or not to print verbose output

    Returns:
        None
    """

    #check if soar_dps_path is valid
    soar_dps_path = Path(soar_dps_path).expanduser()
    if not soar_dps_path.is_dir():
        raise FileNotFoundError(f"soar_dps_path not found: {soar_dps_path}")

    #download LCO data if raw folder doesn't exist
    if not Path("raw").is_dir():
        subprocess.run(f"python3 {soar_dps_path}/download_data_lco.py --start-date {start_date} --end-date {end_date} --data-folder raw", shell=True, check=True)
        subprocess.run("rm raw/*cfzst*", shell=True, check=True) #remove LCO's pre-reduced files

    #make subfolders for each target and move images + 400m1/400m2 flats to each folder if they don't already exist
    for target in targets:
        if Path(f"raw_{target}").is_dir():
            print(f"raw_{target} folder already exists")
            continue
        else:
            try:
                subprocess.run(f"mkdir raw_{target}", shell=True, check=True)
                subprocess.run(f"mkdir reduced_{target}", shell=True, check=True)
                subprocess.run(f"cp raw/*{target}* raw_{target}", shell=True, check=True)
                subprocess.run(f"cp raw/*{mode}* raw_{target}", shell=True, check=True)
            except:
                print(f"Error: could not create subfolders for {target}")
                continue
            if verbose:
                print(f"Moved images and flats for {target} to raw_{target} folder")

        #remove target images if they are not in the correct mode
        for file in Path(f"raw_{target}").iterdir():
            hdulist = fits.open(file)
            if mode == "400m1":
                mode_bool = hdulist[1].header["WAVMODE"] == "400_M1"
            elif mode == "400m2":
                mode_bool = hdulist[1].header["WAVMODE"] == "400_M2"
            else:
                raise ValueError("Invalid mode, must be 400m1 or 400m2")
            hdulist.close()
            if not mode_bool:
                os.remove(file)

    #remove non 400m1/400m2 calib spectra, assume that these will always be sorted in soar_goodman_{color}_A
    for file in Path("raw_Calib").iterdir():
        hdulist = fits.open(file)
        if mode == "400m1":
            mode_bool = hdulist[1].header["WAVMODE"] == "400_M1"
        elif mode == "400m2":
            mode_bool = hdulist[1].header["WAVMODE"] == "400_M2"
        else:
            raise ValueError("Invalid mode, must be 400m1 or 400m2")
        hdulist.close()
        if not mode_bool:
            os.remove(file)

    #remove standard stars not matching the last date in the date range unless keep_all_standards is True
    if not keep_all_standards:
        if verbose:
            print(" ")
            print(f"Removing standard stars observations/arcs not observed on {end_date}.")
            print(" ")
        last_date = end_date
        for file in Path("raw_Calib").iterdir():
            #skip if OBJECT  = 'DFLAT' in header
            hdulist = fits.open(file)
            object_name = hdulist[1].header["OBJECT"]
            obs_date = hdulist[1].header["DATE-OBS"].split("T")[0]
            hdulist.close()
            if object_name == "DFLAT":
                continue
            if not obs_date == last_date:
                if verbose:
                    print(f"Removing {file.name} observed on {obs_date}")
                    print(" ")
                os.remove(file)

            

    #make a finding directory if it doesn't exist
    if not Path("finding").is_dir():
        subprocess.run("mkdir finding", shell=True, check=True)

        #copy one image from each target to the finding directory and unpack it from a .fz file tp a .fits file so we can look at it in ds9
        for target in targets:
            if target == "Calib":
                continue
            else:
                file_glob = Path(f"raw_{target}").glob("*fits.fz")
                for file in file_glob:
                    if f"{target}" in file.name and not ("comp" in file.name or "arc" in file.name):
                        subprocess.run(f"cp {file} finding/{target}_finding.fits.fz", shell=True, check=True)
                        subprocess.run(f"funpack finding/{target}_finding.fits.fz", shell=True, check=True)
                        os.remove(f"finding/{target}_finding.fits.fz")
                        break


def run_pypeit_setup_on_all_targets(targets: list, 
                                    color: str = "red", 
                                    verbose: bool = False):
    """
    Run pypeit_setup on all targets to create the .pypeit files for each target then edit the .pypeit files to fix the frametype issue common with the AEON pipeline.
    
    Args:
        targets (list): List of target names
        color (str): Color of the Goodman camera (red or blue)
        verbose (bool): Whether or not to print verbose output

    Returns:
        None
    """
    # run pypeit_setup on all targets
    for target in targets:
        if verbose:
            print("")
            print("%"*175)
            print(f"Running pypeit_setup on {target}...")
            print("")
        subprocess.run(f"pypeit_setup -s soar_goodman_{color} -r raw_{target} -d reduced_{target} -c all", shell=True, check=True)

    # AEON has a habit of writing "None" as the frametype in the header so we must fix this if it occurs in the .pypeit file
    for target in targets:
        pypeit_file = f"reduced_{target}/soar_goodman_{color}_A/soar_goodman_{color}_A.pypeit"
        start = False
        stop = False

        with open(pypeit_file, "r") as f:
            lines = f.readlines()
        with open(pypeit_file, "w") as f:
            for line in lines:
                if "data read" in line:
                    start = True
                if "data end" in line:
                    stop = True
                if start and not stop:
                    if "None" in line:
                        line = line.replace("   None", "science")
                        line = line.replace("#", " ")
                f.write(line)


def run_pypeit_on_all_targets(targets: list, 
                              color: str = "red", 
                              verbose: bool = False):
    """
    Run pypeit on all targets to create the Science folder with the 1d and 2d spectra .fits files for all science images.

    Args:
        targets (list): List of target names
        color (str): Color of the Goodman camera (red or blue)

    Returns:
        None
    """
    # run pypeit on all targets
    for target in targets:
        if verbose:
            print("")
            print("%"*175)
            print(f"Running pypeit on {target}...")
            print("")
        subprocess.run(f"run_pypeit reduced_{target}/soar_goodman_{color}_A/soar_goodman_{color}_A.pypeit -r reduced_{target}", shell=True, check=True)


def create_sensfunc(sensfunc_file: str, 
                    mode: str = "400m1",
                    debug: bool = True, 
                    verbose: bool = False):
    """
    Create the sensfunc file for the 400_M1 grating using the reduced standard star data.

    Args:
        sensfunc_file (str): Path to the sensfunc file
        mode (str): Mode of the Goodman camera (400m1 or 400m2)
        debug (bool): Whether or not to debug the sensfunc creation (if True, pypeit will display a plot of the sensfunc)
        verbose (bool): Whether or not to print verbose output

    Returns:
        None
    """
    if verbose:
        print("")
        print("%"*175)
        if mode == "400m1":
            print(f"Creating sensfunc file for 400_M1...")
        elif mode == "400m2":
            print(f"Creating sensfunc file for 400_M2...")
        print("")
    
    #create sensfunc file
    if debug == False:
        if verbose:
            print("Not debugging sensfunc creation")
        subprocess.run(f"pypeit_sensfunc -s {sensfunc_file} -o {mode}_sens.fits reduced_Calib/Science/spec1d*.fits", shell=True, check=True)
        # subprocess.run(f"pypeit_sensfunc -s {sensfunc_file} -o 400m1_sens.fits reduced_Calib/Science/spec1d*.fits", shell=True, check=True)
    else:
        subprocess.run(f"pypeit_sensfunc -s {sensfunc_file} -o {mode}_sens.fits --debug reduced_Calib/Science/spec1d*.fits", shell=True, check=True)
        # subprocess.run(f"pypeit_sensfunc -s {sensfunc_file} -o 400m1_sens.fits --debug reduced_Calib/Science/spec1d*.fits", shell=True, check=True)


def run_pypeit_fluxing_on_all_targets(targets: list, 
                                      mode: str = "400m1",
                                      color: str = "red", 
                                      verbose: bool = False):
    """
    Run pypeit_flux_setup on all targets to create .tell, .coadd1d, and .flux files. Then edit the .pypeit file to fix the frametype issue with AEON, edit the .tell file to use "poly" 
    instead of "qso" for telluric fitting, and edit the .flux file to change the default paths and add the sensfunc file. Then run pypeit_flux_calib on all targets.

    Args:
        targets (list): List of target names
        mode (str): Mode of the Goodman camera (400m1 or 400m2)
        color (str): Color of the Goodman camera (red or blue)
        verbose (bool): Whether or not to print verbose output

    Returns:
        None
    """
    for target in targets:
        if target == "Calib":
            continue
        if verbose:
            print("")
            print("%"*175)
            print(f"Running pypeit_fluxing on {target}...")
            print("")

        #run flux setup to create .flux, .tell, and .coadd1d files
        subprocess.run(f"pypeit_flux_setup reduced_{target}/Science", shell=True, check=True)

        #this creates them in our main directory so we need to move them to the target directory
        subprocess.run(f"mv soar_goodman_{color}.flux reduced_{target}/soar_goodman_{color}.flux", shell=True, check=True)
        subprocess.run(f"mv soar_goodman_{color}.tell reduced_{target}/soar_goodman_{color}.tell", shell=True, check=True)
        subprocess.run(f"mv soar_goodman_{color}.coadd1d reduced_{target}/soar_goodman_{color}.coadd1d", shell=True, check=True)

        # by default pypeit uses "qso" instead of "poly" for telluric fitting, we need to change this in the .tell file
        tell_file = f"reduced_{target}/soar_goodman_{color}.tell"
        with open(tell_file, "r") as f:
            lines = f.readlines()
        with open(tell_file, "w") as f:
            for line in lines:
                if "qso" in line:
                    line = line.replace("qso", "poly")
                f.write(line)
        
        #the .flux file need to have it's default paths changed and needs to have the sensfunc file added for each image
        flux_file = f"reduced_{target}/soar_goodman_{color}.flux"
        with open(flux_file, "r") as f:
            lines = f.readlines()
        with open(flux_file, "w") as f:
            read_start = False
            read_end = False
            for line in lines:
                if "flux read" in line:
                    read_start = True
                if "flux end" in line:
                    read_end = True
                if read_start and not read_end:
                    #change the default paths
                    if "path" in line:
                        old_path = f"path reduced_{target}/Science"
                        new_path = f"path ./ \n path reduced_{target}/Science"
                        # line = line.replace("path reduced_{target}/Science", "path ./ \n path reduced_{target}/Science")
                        line = line.replace(old_path, new_path)

                    #add the sensfunc file
                    if "spec1d" in line:
                        if mode == "400m1":
                            line = line.replace("        \n", "400m1_sens.fits\n")
                        elif mode == "400m2":
                            line = line.replace("        \n", "400m2_sens.fits\n")
                        # line = line.replace("        \n", "400m1_sens.fits\n")
                f.write(line)
                    
        #run pypeit_flux_calib
        subprocess.run(f"pypeit_flux_calib reduced_{target}/soar_goodman_{color}.flux", shell=True, check=True)
        

def pypeit_coaddition_on_all_targets(targets: list, 
                                     color: str = "red", 
                                     manually_select_traces: bool = True, 
                                     trace_spatial_lower_limit: int = 490, 
                                     trace_spatial_higher_limit: int = 510, 
                                     verbose: bool = False):
    """
    Display the traces detected in the coadd1d file for each target and have the user select a spatial target to coadd. Then create a new coadd1d file with only the selected traces and run pypeit_coadd_1dspec on it.

    Args:
        targets (list): List of target names
        color (str): Color of the Goodman camera (red or blue)
        manually_select_traces (bool): Whether or not to manually select the traces to coadd, if False the traces will be selected automatically based on the trace_spatial_lower_limit and trace_spatial_higher_limit
        trace_spatial_lower_limit (int): Lower limit of the spatial range to coadd all traces within
        trace_spatial_higher_limit (int): Higher limit of the spatial range to coadd all traces within
        verbose (bool): Whether or not to print verbose output

    Input:
        spatial_target (str): The spatial target to coadd
        spatial_buffer (str): The spatial buffer

    Returns:
        None
    """
    for target in targets:
        if target == "Calib": #skip the calib target
            continue
        if verbose:
            print("")
            print("%"*175)
            print(f"Running pypeit_coaddition on {target}...")
            print("")

        #check that the coadd1d file exists
        coadd1d_file = f"reduced_{target}/soar_goodman_{color}.coadd1d"
        if not Path(coadd1d_file).is_file():
            print(f"Error: {coadd1d_file} not found")
            continue

        #get a list of all detected traces from the coadd1d file
        with open(coadd1d_file, "r") as f:
            lines = f.readlines()
        traces = []
        coadd1d_read = False
        coadd1d_end = False
        for line in lines:
            if "coadd1d read" in line:
                coadd1d_read = True
            if "coadd1d end" in line:
                coadd1d_end = True
            if coadd1d_read and not coadd1d_end:
                if "spec1d" in line:
                    traces.append(line.strip())
            
        #print the traces
        print("%"*175)
        print(f"Traces dettected for {target}:")
        for trace in traces:
            print(trace)

        if manually_select_traces:
            #have the user select a spatial target, make them confirm the selection
            while True:
                spatial_target = input("Enter the spatial target (or 'all' for all traces): ")
                spatial_buffer = input("Enter the spatial buffer: ")
                print(" ")
                print(f"spatial_target: {spatial_target}, spatial_buffer: {spatial_buffer}")
                print(" ")
                confirm = input("Confirm selection? (y/n): ")
                if confirm == "y":
                    break
                else:
                    continue            

            #create a new coadd file with only the selected traces
            new_coadd1d_file = f"reduced_{target}/{target}_coadd1d_SPAT{spatial_target}_BUFFER{spatial_buffer}.coadd1d"

        else:
            #create a new coadd file with only the selected traces
            new_coadd1d_file = f"reduced_{target}/{target}_coadd1d_SPAT{trace_spatial_lower_limit}-{trace_spatial_higher_limit}.coadd1d"

        with open(coadd1d_file, "r") as f:
            lines = f.readlines()
        with open(new_coadd1d_file, "w") as f:
            coadd1d_read = False
            coadd1d_end = False
            for line in lines:
                write_line = True

                #change output name
                if "YOUR_OUTPUT_FILE_NAME" in line:
                    line = line.replace("YOUR_OUTPUT_FILE_NAME", f"{target}_coadd.fits")

                #remove line if the spatial target is not within target+-buffer
                if "coadd1d read" in line:
                    coadd1d_read = True
                if "coadd1d end" in line:
                    coadd1d_end = True

                #manual selection of traces
                if manually_select_traces:
                    if not spatial_target == "all" and coadd1d_read and not coadd1d_end:
                        if "spec1d" in line:
                            split_line = line.split(" | SPAT")
                            spatial =  float(split_line[1].split("-")[0])
                            if not (float(spatial_target) - float(spatial_buffer) <= spatial <= float(spatial_target) + float(spatial_buffer)):
                                write_line = False
                    elif spatial_target == "all" and coadd1d_read and not coadd1d_end:
                        if "spec1d" in line:
                            write_line = True

                #auto selection of traces
                else:
                    if coadd1d_read and not coadd1d_end:
                        if "spec1d" in line:
                            split_line = line.split(" | SPAT")
                            spatial =  float(split_line[1].split("-")[0])
                            if not (trace_spatial_lower_limit <= spatial <= trace_spatial_higher_limit):
                                write_line = False

                if write_line:
                    f.write(line)

        #show the user the traces that will be coadded
        print("%"*175)
        print(f"Traces to be coadded for {target}:")
        with open(new_coadd1d_file, "r") as f:
            lines = f.readlines()
        for line in lines:
            if "spec1d" in line:
                print(line.strip())

        #run pypeit_coaddition
        if manually_select_traces:
            subprocess.run(f"pypeit_coadd_1dspec reduced_{target}/{target}_coadd1d_SPAT{spatial_target}_BUFFER{spatial_buffer}.coadd1d", shell=True, check=True)
        else:
            subprocess.run(f"pypeit_coadd_1dspec reduced_{target}/{target}_coadd1d_SPAT{trace_spatial_lower_limit}-{trace_spatial_higher_limit}.coadd1d", shell=True, check=True)
        subprocess.run(f"mv {target}_coadd.fits reduced_{target}/{target}_coadd.fits", shell=True, check=True)


def run_pypeit_tellfit_on_all_targets(targets: list, 
                                      color: str = "red", 
                                      verbose: bool = False):
    """
    Run pypeit_tellfit on all targets to create tellmodel and tellcorr files.

    Args:
        targets (list): List of target names
        color (str): Color of the Goodman camera (red or blue)
        verbose (bool): Whether or not to print verbose output

    Returns:
        None
    """
    for target in targets:
        if target == "Calib": #skip the calib target
            continue
        if verbose:
            print("")
            print("%"*175)
            print(f"Running pypeit_tellfit on {target}...")
            print("")

        #run pypeit_tellfit
        subprocess.run(f"pypeit_tellfit reduced_{target}/{target}_coadd.fits -t reduced_{target}/soar_goodman_{color}.tell", shell=True, check=True)
        subprocess.run(f"mv {target}_coadd_tellmodel.fits reduced_{target}/{target}_coadd_tellmodel.fits", shell=True, check=True)
        subprocess.run(f"mv {target}_coadd_tellcorr.fits reduced_{target}/{target}_coadd_tellcorr.fits", shell=True, check=True)


def create_ascii_file_for_spectrum(target: str, 
                                   spec1d_file: str, 
                                   cut_wavelength_low: float = None, 
                                   cut_wavelength_high: float = None, 
                                   display_spectrum: bool = False, 
                                   verbose: bool = False):
    """
    This function creates an ascii file for the spectrum in the spec1d file. It also displays the spectrum if display is True. This was mroe or less stolen from Igor Andreoni's soar-dps code.
    
    Args:
        target (str): Target name
        spec1d_file (str): Path to the spec1d file
        cut_wavelength_low (float): Lower limit of the wavelength range to cut, default is None
        cut_wavelength_high (float): Higher limit of the wavelength range to cut, default is None
        display (bool): Whether or not to display the spectrum, default is False
        verbose (bool): Whether or not to print verbose output, default is False

    Returns:
        mjd (float): MJD of the observation
    """
    #check if spec1d_file exists
    spec1d_file = Path(spec1d_file).expanduser()
    if not spec1d_file.is_file():
        raise FileNotFoundError(f"spec1d_file not found: {spec1d_file}")
    
    #open the spec1d file
    spectrum = fits.open(spec1d_file)[1].data
    header = fits.open(spec1d_file)[0].header

    #get the MJD from the header
    try:
        mjd = header["MJD"]
    except KeyError:
        try:
            mjd = Time(header["DATE-OBS"]).mjd
        except KeyError:
            try:
                mjd = Time(header["DATE"]).mjd
            except KeyError:
                raise KeyError("Cannot find the date of the observations?")
                mjd = None
            
    #get the wavelength, flux, and flux error from the spectrum
    wavelength = [spectrum[i][1] for i in np.arange(len(spectrum))]
    flux = [spectrum[i][2] for i in np.arange(len(spectrum))]
    flux_error = [spectrum[i][3] for i in np.arange(len(spectrum))]

    #cut the wavelength range if specified
    if cut_wavelength_low is not None and cut_wavelength_high is not None:
        flux = [flux[i] for i in np.arange(len(wavelength)) if (wavelength[i] > cut_wavelength_low and wavelength[i] < cut_wavelength_high)]
        flux_error = [flux_error[i] for i in np.arange(len(wavelength)) if (wavelength[i] > cut_wavelength_low and wavelength[i] < cut_wavelength_high)]
        wavelength = [wavelength[i] for i in np.arange(len(wavelength)) if (wavelength[i] > cut_wavelength_low and wavelength[i] < cut_wavelength_high)]

    #display the spectrum if specified
    if display_spectrum:
        plt.errorbar(wavelength, flux, yerr=flux_error, color="grey", alpha=0.3)
        plt.plot(wavelength, flux, color="blue")
        plt.xlabel("Wavelength (Angstroms)")
        plt.ylabel("Flux (10^{-17} erg/s/cm^2/Angstrom)") #the units of fluxed pypeit outputs https://pypeit.readthedocs.io/en/latest/coadd1d.html
        plt.title(f"{target}, SOAR GHTS Spectrum, MJD: {mjd}")
        plt.show()

    #print the ascii file info if verbose
    if verbose:
        print("%"*175)
        print(" ")
        print(f"Creating ascii file for {target}")
        print(f"MJD: {mjd}")
        print(f"Wavelength range: {wavelength[0]} - {wavelength[-1]}")

    #write the ascii file
    ascii_file = spec1d_file.with_suffix(".ascii")
    if verbose:
        print(f"Writing ascii file to {ascii_file}")
        print(" ")
    with open(ascii_file, "w") as f:
        for i in np.arange(len(wavelength)):
            f.write(f"{wavelength[i]} {flux[i]} {flux_error[i]}\n")

    return mjd


def write_all_targets_to_ascii(targets: list, 
                               cut_wavelength_low: float = None, 
                               cut_wavelength_high: float = None, 
                               display_spectrum: bool = False, verbose: bool = False):
    """
    Write all targets to an ascii file using Igor's write_ascii_soar_spec.py code from soar-dps.

    Args:
        targets (list): List of target names
        cut_wavelength_low (float): Lower limit of the wavelength range to cut, default is None
        cut_wavelength_high (float): Higher limit of the wavelength range to cut, default is None
        verbose (bool): Whether or not to print verbose output

    Returns:
        None
    """
    #create results directory if it doesn't exist
    if not Path("results").is_dir():
        subprocess.run("mkdir results", shell=True, check=True)

    #create mjd list .txt file in results directory
    longest_target_name = max([len(target) for target in targets])
    with open("results/mjd_list.txt", "w") as f:
        #consistent spacing for target names
        f.write("target" + " "*(longest_target_name - 6) + " | MJD\n")
        f.write("-"*longest_target_name + "-|------------------\n")

    #write all targets to an ascii file 
    mjd_list = []
    for target in targets:
        if target == "Calib":
            mjd_list.append("N/A")
            continue
        
        #create the ascii file
        mjd = create_ascii_file_for_spectrum(target, f"reduced_{target}/{target}_coadd_tellcorr.fits", cut_wavelength_low=cut_wavelength_low, cut_wavelength_high=cut_wavelength_high, display_spectrum=display_spectrum, verbose=verbose)
        mjd_list.append(mjd)

        #write the mjd to the mjd list file
        with open("results/mjd_list.txt", "a") as f:
            f.write(f"{target}" + " "*(longest_target_name - len(target)) + f" | {mjd}\n")

        #copy the ascii file to the results directory
        subprocess.run(f"cp reduced_{target}/{target}_coadd_tellcorr.ascii results/{target}_coadd_tellcorr.ascii", shell=True, check=True)

    if verbose:
        print(" ")
        print("%"*175)
        print(" ")
        print("All targets written to ascii files in results directory")
        print(" ")
        print("MJD list written to results/mjd_list.txt:")
        print(" ")
        print("target" + " "*(longest_target_name - 6) + " | MJD")
        for target, mjd in zip(targets, mjd_list):
            if target == "Calib":
                continue
            print(f"{target}" + " "*(longest_target_name - len(target)) + f" | {mjd}")
        print(" ")


def cleanup(targets: list, 
            mode: str = "400m1",
            verbose: bool = False):
    """
    Cleanup the raw and reduced directories.

    Args:
        targets (list): List of target names
        mode (str): Mode of the Goodman camera (400m1 or 400m2)
        verbose (bool): Whether or not to print verbose output

    Returns:
        None
    """
    #remove raw directory of LCO data if it exists
    if Path("raw").is_dir():
        subprocess.run("rm -r raw", shell=True, check=True)

    #remove raw and reduced directories for all targets
    for target in targets:
        if Path(f"raw_{target}").is_dir():
            subprocess.run(f"rm -r raw_{target}", shell=True, check=True)
        if Path(f"reduced_{target}").is_dir():
            subprocess.run(f"rm -r reduced_{target}", shell=True, check=True)

    #remove the finding directory if it exists
    if Path("finding").is_dir():
        subprocess.run("rm -r finding", shell=True, check=True)

    #remove other odds and ends
    if mode == "400m1":
        try: subprocess.run("rm 400m1*", shell=True, check=True)
        except: pass
    elif mode == "400m2":
        try: subprocess.run("rm 400m2*", shell=True, check=True)
        except: pass
    try: subprocess.run("rm coadd1d.par", shell=True, check=True)
    except: pass
    try: subprocess.run("rm fluxing.par", shell=True, check=True)
    except: pass
    try: subprocess.run("rm telluric.par", shell=True, check=True)
    except: pass

    if verbose:
        print(" ")
        print("%"*175)
        print(" ")
        print("Data cleanup complete")
        print(" ")


def snid_setup(targets: list,
               verbose: bool, 
               snid_desktop_path: str,
               folder_name: str
               ):
    """
    Create a directory on the user's desktop where the docker environment SNID runs in can see it then copy all coadd_tellcorr.fits files to it.

    Args:
        targets (list): List of target names
        verbose (bool): Whether or not to print verbose output
        snid_desktop_path (str): Path to where the SNID folder will be created under the desktop
        folder_name (str): Name of the folder to create under the snid_desktop_path

    Returns:
        None
    """ 
    #create a subfolder in the snid_desktop_path if it does note exist
    snid_path = Path(snid_desktop_path).expanduser() / folder_name
    if not snid_path.is_dir():
        subprocess.run(f"mkdir -p {snid_path}", shell=True, check=True)
        if verbose:
            print(f"Created SNID setup directory at {snid_path}")

    #copy all coadd_tellcorr.fits files to the snid_path, if they exist save them with an incremented vlaue
    if verbose:
        print("")
        print(f"Copying coadd_tellcorr.ascii files to {snid_path}...")
    for target in targets:
        if target == "Calib":
            continue

        spec1d_file = Path(f"reduced_{target}/{target}_coadd_tellcorr.ascii")

        #check that that .ascii file already exists
        if not spec1d_file.is_file():
            if verbose:
                print(f"Error: {spec1d_file} not found, skipping {target}")
            continue

        #check if the file already exists in the snid_path, if it does increment the filename
        dest_file = snid_path / f"{target}_coadd_tellcorr.ascii"
        increment = 0
        while dest_file.is_file():
            dest_file = snid_path / f"{target}_coadd_tellcorr_v{increment}.ascii"
            increment += 1

        #copy the file
        subprocess.run(f"cp {spec1d_file} {dest_file}", shell=True, check=True)
        if verbose:
            print(f"Copied {spec1d_file} to {dest_file}")


def run_snid(snid_desktop_path: str,
             snid_docker_path: str,
             folder_name: str,
             verbose: bool):
    """
    Run SNID in the docker environment with access to the spectra in the snid_desktop_path/folder_name directory.

    Args:
        snid_desktop_path (str): Path to where the SNID folder is created under the desktop
        snid_docker_path (str): Path to the SNID docker environment
        folder_name (str): Name of the folder created under the snid_desktop_path
        verbose (bool): Whether or not to print verbose output

    Returns:
        None
    """ 
    snid_path = Path(snid_desktop_path).expanduser() / folder_name
    snid_docker_path = Path(snid_docker_path).expanduser()

    if not snid_path.is_dir():
        print(f"Error: SNID setup directory {snid_path} not found, cannot run SNID")
        return
    if not snid_docker_path.is_dir():
        print(f"Error: SNID docker directory {snid_docker_path} not found, cannot run SNID")
        return
    
    if verbose:
        print("%"*175)
        print("")
        print(f"Running SNID on spectra in {snid_path}.")
        print("Within the Docker environment files will be located in desktop/{folder_name}/")
        print("")
        print("Use the command 'snid <filename>' to run SNID on a specific spectrum.")
        print("Use the command 'exit' to exit the Docker environment when finished.")
        print("")

    subprocess.run(f"bash {snid_docker_path}/run_snid.sh", shell=True, check=True)


def get_fritz_ids():
    """
    Interactive selection of Fritz/SkyPortal user IDs for spectrum upload.

    Returns:
        pi_id (int): Principal Investigator user ID
        reducer_ids (list): List of Reducer user IDs
        observer_ids (list): List of Observer user IDs
    """
    user_id_dict = {
        "1": 14,
        "2": 1445,
        "3": 1329,
        "4": 1383,
        "5": 1001, #change later
        "6": 1002 #change later
    }
    user_name_dict = {
        "14": "Igor",
        "1445": "Jon",
        "1329": "Akash",
        "1383": "Jim",
        "1001": "Anirudh", #change later
        "1002": "Kira" #change later
    }

    while True:
        print("Please enter the following information for the spectrum upload:")
        print("")
        print("PI: (1) Igor, (2) Jon, (3) Akash, (4) Jim, (5) Anirudh, (6) Kira")
        pi_input = input("Enter the number corresponding to the PI:")
        if pi_input in user_id_dict.keys():
            pi_id = user_id_dict[pi_input]
            pi_name = user_name_dict[str(user_id_dict[pi_input])]
            print(f"PI selected: {pi_name}")

        print("Reducer: (1) Igor, (2) Jon, (3) Akash, (4) Jim, (5) Anirudh, (6) Kira")
        reducer_input = input("Enter the number corresponding to the Reducers separated by commas (e.g., 1,3 for Igor and Akash):")
        reducer_ids = []
        reducer_names = []
        for rid in reducer_input.split(","):
            rid = rid.strip()
            if rid in user_id_dict.keys():
                reducer_ids.append(user_id_dict[rid])
                reducer_names.append(user_name_dict[str(user_id_dict[rid])])
        print(f"Reducers selected: {', '.join(reducer_names)}")

        print("Observer: (1) Igor, (2) Jon, (3) Akash, (4) Jim, (5) Anirudh, (6) Kira")
        observer_input = input("Enter the number corresponding to the Observers separated by commas (e.g., 1,3 for Igor and Akash):")
        observer_ids = []
        observer_names = []
        for oid in observer_input.split(","):
            oid = oid.strip()
            if oid in user_id_dict.keys():
                observer_ids.append(user_id_dict[oid])
                observer_names.append(user_name_dict[str(user_id_dict[oid])])
        print(f"Observers selected: {', '.join(observer_names)}")
        print("")
        print("Is the following information correct? (y/n)")
        print(f"PI: {pi_name}")
        print(f"Reducers: {', '.join(reducer_names)}")
        print(f"Observers: {', '.join(observer_names)}")
        confirm = input()
        if confirm.lower() == "y":
            break
    return pi_id, reducer_ids, observer_ids


def get_group_ids():
    """
    Interactive selection of group IDs for spectrum upload to Fritz/SkyPortal.

    Returns:
        group_ids (list): List of group IDs for spectrum upload
    """
    group_id_dict = {
        "1": 1856,
        "2": 80,
        "3": 1
    }
    group_name_dict = {
        "1856": "ATALAB",
        "80": "Nuclear Transients",
        "1": "sitewide group"
    }

    while True:
        print("Please enter the following information for the spectrum upload:")
        print("")
        print("Group IDs: (1) ATALAB, (2) Nuclear Transients, (3) sitewide group")
        group_input = input("Enter the number corresponding to the Group IDs separated by commas (e.g., 1,3 for ATALAB and sitewide group):")
        group_ids = []
        group_names = []
        for gid in group_input.split(","):
            gid = gid.strip()
            if gid in group_id_dict.keys():
                group_ids.append(group_id_dict[gid])
                group_names.append(group_name_dict[str(group_id_dict[gid])])
        print("Is the following information correct? (y/n)")
        print(f"Group IDs: {', '.join(group_names)}")
        confirm = input()
        if confirm.lower() == "y":
            break
    return group_ids


def upload_spectrum_to_skyportal(
    target_name: str,
    ascii_file: str,
    fritz_token: str, 
    mjd: float,
    skyportal_url: str = "https://fritz.science/api/spectra",
    verbose: bool = False,
    pi_id: int = None,
    reducer_ids: list = None,
    observer_ids: list = None,
    group_ids: list = None
):
    """
    Write me!
    """
    if pi_id is None or reducer_ids is None or observer_ids is None:
        pi_id, reducer_ids, observer_ids = get_fritz_ids()
    if group_ids is None:
        group_ids = get_group_ids()

    # Read the spectrum
    wavelength, flux, flux_err = np.loadtxt(ascii_file, unpack=True)

    # Convert MJD to ISO format
    iso_time = Time(mjd, format='mjd').isot
    
    payload = {
       "wavelengths": wavelength.tolist(),
        "fluxes": flux.tolist(),
        "errors": flux_err.tolist(),
        "obj_id": target_name,
        "observed_at": f"{iso_time}",
        "pi": [pi_id],
        "external_pi": None,
        "reduced_by": reducer_ids,
        "external_reducer": None,
        "observed_by": observer_ids,
        "external_observer": None,
        "type": "source",
        "instrument_id": 1108, #GHTS ID
        "group_ids": group_ids #1856 = ATALAB, 80=Nuclear Transients, 1=sitewide group
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"token {fritz_token}"
    }
    
    if verbose:
        print(f"Uploading spectrum for {target_name} to {skyportal_url}...")
    
    response = requests.post(
        skyportal_url,
        json=payload,
        headers=headers
    )
    
    if response.status_code == 200:
        if verbose:
            print(f"Successfully uploaded spectrum for {target_name}")
        return True
    else:
        print(f"Error uploading spectrum for {target_name}: {response.json()}")
        return False


def upload_to_fritz(
    targets: list,
    fritz_token: str = os.getenv("FRITZ_TOKEN"),
    verbose: bool = False
        
):
    """ write me """

    print(f"Using fritz token : {fritz_token}")

    #prompt user for default Fritz/SkyPortal IDs
    default_pi_id, default_reducer_ids, default_observer_ids = get_fritz_ids()
    default_group_ids = get_group_ids()

    for target in targets:
        #skip calib target
        if target == "Calib":
            continue

        #check that the .ascii file exists
        ascii_file = Path(f"results/{target}_coadd_tellcorr.ascii")
        if not ascii_file.is_file():
            if verbose:
                print(f"Error: {ascii_file} not found, skipping {target}")
            continue

        #get the mjd from the results/mjd_list.txt file
        with open("results/mjd_list.txt", "r") as f:
            lines = f.readlines()
        mjd = None
        for line in lines:
            if line.startswith(target):
                mjd = float(line.split("|")[1].strip())
                break
        if mjd is None:
            if verbose:
                print(f"Error: MJD for {target} not found in results/mjd_list.txt, skipping {target}")
            continue

        #prompt user for Fritz/SkyPortal IDs for this target
        print(f"Uploading spectrum for {target}:")
        print("Use default Fritz/SkyPortal IDs for PI, Observers, Reducers? (y/n)")
        use_default = input().strip().lower()
        if use_default == "y":
            pi_id, reducer_ids, observer_ids  = default_pi_id, default_reducer_ids, default_observer_ids
        else:
            pi_id, reducer_ids, observer_ids = get_fritz_ids()
        print("Use default Group IDs? (y/n)")
        use_default = input().strip().lower()
        if use_default == "y":
            group_ids = default_group_ids
        else:        
            group_ids = get_group_ids()

        #upload the spectrum
        upload_spectrum_to_skyportal(
            target_name=target,
            ascii_file=str(ascii_file),
            fritz_token=fritz_token,
            mjd=mjd,
            verbose=verbose,
            pi_id=pi_id,
            reducer_ids=reducer_ids,
            observer_ids=observer_ids,
            group_ids=group_ids
        )

#create CLI
if __name__ == "__main__":
    #description of the script
    parser = argparse.ArgumentParser(description="Semi automated reduction of SOAR GHTS data taken in 400m1 or 400m2 mode via the AEON queue. This script will download data and "
                                     "run the neccessary pypeit reduction steps, requiring minimal user input.\n \n Users must be in a pypeit friendly python environment "
                                     "and have their LCO token exported. Users must provide a sensitivity function .par file in the standard pypeit format. \n "
                                     "Users will need to either input start/end dates and target names via the commandline interface or provide a file with this "
                                     "information. This file should be formatted as follows: \n start_date in YYYY-MM-DD format \n end_date in YYYY-MM-DD format \n target1 "
                                     "\n target2 \n ... \n targetN"
                                       " \n \n Users will "
                                     "be prompted: \n 1. (if a target.txt file is not provided) For "
                                     "start/end dates and target names \n 2. (if --debug is True) To approve the sensfunc by closing both pypeit "
                                     "guis \n 3. (if --manual_trace_selection is True) To confirm the allowed range of target pixel positions on the slit for coaddition (target_position +/- buffer). A finding directory with DS9 friendly images is automatically created to help with this task.",
                                     formatter_class=RawDescriptionHelpFormatter)

    #add arguments
    parser.add_argument("-t", "--targets_file", help="List of targets to reduce and the dates to query lco for", type=str, default=None)
    parser.add_argument("-s", "--sensfunc", help="Path to the sensfunc file", type=str, default="sensfunc.par")
    parser.add_argument("-c", "--color", help="Color of the Goodman camera (red or blue), default is red", type=str, default="red")
    parser.add_argument("-m", "--mode", help="Mode of the Goodman camera (400m1 or 400m2), default is 400m1", type=str, default="400m1")
    parser.add_argument("-v", "--verbose", help="Print verbose output", action="store_true")
    parser.add_argument("-stop", "--stop_after", help="Stop after a specific step in the reduction process. Options are 'setup', 'sensfunc', 'fluxing', 'coaddition', 'snid'", type=str, default=None)
    parser.add_argument("-skip", "--skip_to", help="Skip to a specific step in the reduction process. Options are 'sensfunc', 'fluxing', 'coaddition', 'snid', 'fritz", type=str, default=None)
    parser.add_argument("-dps", "--soar_dps_path", help="Path to the soar-dps software used to download data from LCO", type=str, default="~/Research/ATALab/software/soar-dps")    
    parser.add_argument("-d", "--debug", help="Manually debug the pypeit sensfunction", action="store_true")
    parser.add_argument("-manual", "--manual_trace_selection", help="Manually select the traces to coadd", action="store_true")
    parser.add_argument("-cpl", "--cut_pix_low", help="Low end of spatial range to coadd all traces within, default is 490", type=int, default=490)
    parser.add_argument("-cph", "--cut_pix_high", help="High end of spatial range to coadd all traces within, default is 510", type=int, default=510)
    parser.add_argument("-cwl", "--cut_wavelength_low", help="Low end of wavelength range to cut, default is 3800 for 400m1 and 5000 for 400m2", type=float, default=None)
    parser.add_argument("-cwh", "--cut_wavelength_high", help="High end of wavelength range to cut, default is 7040 for 400m1 and 9000 for 400m2", type=float, default=None)
    parser.add_argument("-plot", "--display_spectrum", help="Display the final spectrum for each target when creating its .ascii file, default is False", action="store_true")
    parser.add_argument("-clean", "--cleanup", help="Cleanup the raw and reduced directories, keeping only the sensfunc.par file, the original target list, and the results directory, default is False", action="store_true")
    parser.add_argument("-k", "--keep_all_standards", help="Keep all standard star data and not just those matching the end date, default is True", action="store_false")
    parser.add_argument("-snidset", "--snid_setup", help="Copy reduced spectra to a directory accessable to SNID's docker container, default is False", action="store_true")
    parser.add_argument("-snid", "--snid_run", help="Run SNID on the reduced spectra in the SNID setup directory, default is False", action="store_true")
    parser.add_argument("-desktop", "--snid_desktop_path", help="Path to the desktop directory where the SNID setup directory will be created, default is ~/Desktop/snid", type=str, default="~/Desktop/snid")
    parser.add_argument("-sdpath", "--snid_docker_path", help="Path to the docker environment where SNID is installed, default is /Users/jon/Research/ATALab/software/snid/snid_docker", type=str, default="/Users/jon/Research/ATALab/software/snid/snid_docker")
    parser.add_argument("-fritz", "--fritz_upload", help="Upload reduced spectra to Fritz, default is False", action="store_true")

    args = parser.parse_args()

    #handle cut wavelength defaults
    if args.cut_wavelength_low is None:
        if args.mode == "400m1":
            args.cut_wavelength_low = 3800
        elif args.mode == "400m2":
            args.cut_wavelength_low = 5000
    if args.cut_wavelength_high is None:
        if args.mode == "400m1":
            args.cut_wavelength_high = 7040
        elif args.mode == "400m2":
            args.cut_wavelength_high = 9000

    #detect if the user provided a file with the targets and dates and if not run the setup function
    if args.targets_file:
        with open(args.targets_file, "r") as f:
            targets = f.readlines()
            targets = [target.strip() for target in targets]
        start_date = targets[0]
        end_date = targets[1]
        targets = targets[2:]
        targets.insert(0, "Calib")
    else:
        targets, start_date, end_date = setup(verbose=args.verbose)

    #setup block of the reduction process: download and orgnaize data, run pypeit_setup on all targets, edit the .pypeit files and then run_pyepit on all targets. Thsi block takes the longest.
    if not (args.skip_to == "sensfunc" or args.skip_to == "fluxing" or args.skip_to == "coaddition" or args.skip_to == "snid" or args.skip_to == "fritz"):
        download_and_and_orgnaize_lco_data(targets, start_date, end_date, mode=args.mode, soar_dps_path=args.soar_dps_path, verbose=args.verbose, keep_all_standards=args.keep_all_standards)
        run_pypeit_setup_on_all_targets(targets, color=args.color, verbose=args.verbose)
        run_pypeit_on_all_targets(targets, color=args.color, verbose=args.verbose)

    if args.stop_after == "setup":
        print("Stopping after setup")
        exit()

    #sensfunc block of the reduction process, user can optionally review the sensfunc (recommended)
    if not (args.skip_to == "coaddition" or args.skip_to == "fluxing" or args.skip_to == "snid" or args.skip_to == "fritz"):
        create_sensfunc(args.sensfunc, mode=args.mode, debug=args.debug, verbose=args.verbose)

    if args.stop_after == "sensfunc":
        print("Stopping after sensfunc")
        exit()

    #fluxing block of the reduction process
    if not (args.skip_to == "coaddition" or args.skip_to == "snid" or args.skip_to == "fritz"):
        run_pypeit_fluxing_on_all_targets(targets, mode=args.mode, color=args.color, verbose=args.verbose)

    if args.stop_after == "fluxing":
        print("Stopping after fluxing")
        exit()
    
    if not(args.skip_to == "snid" or args.skip_to == "fritz"):
        #coaddition block of the reduction process: coadd selected traces (user input) and run pypeit_coadd_1dspec, apply telluric correction, and write to ascii
        pypeit_coaddition_on_all_targets(targets, color=args.color, manually_select_traces=args.manual_trace_selection, trace_spatial_lower_limit=args.cut_pix_low, trace_spatial_higher_limit=args.cut_pix_high, verbose=args.verbose)
        run_pypeit_tellfit_on_all_targets(targets, color=args.color, verbose=args.verbose)
        write_all_targets_to_ascii(targets, cut_wavelength_low=args.cut_wavelength_low, cut_wavelength_high=args.cut_wavelength_high, display_spectrum=args.display_spectrum, verbose=args.verbose)
        if args.cleanup:
            cleanup(targets, mode=args.mode, verbose=args.verbose)

    if args.stop_after == "coaddition":
        print("Stopping after coaddition and cleanup")
        exit()

    if args.snid_setup or args.snid_run:
        if start_date is not None:
            folder_name = f"{start_date}_SOAR_GHTS_reductions"
        else:
            #combine all target names
            folder_name = "SOAR_GHTS_reductions_" + "_".join(targets[1:])
        snid_setup(snid_desktop_path=args.snid_desktop_path, targets=targets, verbose=args.verbose, folder_name=folder_name)

    if args.snid_run:
        run_snid(snid_desktop_path=args.snid_desktop_path, snid_docker_path=args.snid_docker_path, folder_name=folder_name, verbose=args.verbose)

    if args.fritz_upload:
        upload_to_fritz(targets, verbose=args.verbose)

    print("%"*175)
    print("That's all folks!")

#To add
# - STACK IMAGES FIRST
# - can I easily save the flux residual image from the sensfunc step for later debugging?
# - add background width to the coaddition step
# - autmatically run snid on all targets and save the results to a .txt file without having to interact with SNID?
# - organize the cli stuff nad improve readability throughout the code
# - rmeove dependency on SOAR DPS
# - add a bunch of try excepts to prevent failure on one target from ending whole run

# SOLVED (with laziness)
# -  SOLVED add 400m1 + 400m2 support on a single target run twice with the same target list
# - SOLVED add a way to rerun on a single target after download? (just make a new target list with one target)