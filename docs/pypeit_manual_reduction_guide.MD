# Pypeit for SOAR tutorial
### Author: Jonathan Carney

We are going to be partially repoducing the reduction of https://fritz.science/source/ZTF24abmybnp.

This covers reduction with a modified version of Pypeit 1.16.0. See https://github.com/pypeit/PypeIt/issues/1850 for the modification.

## Step 0: Download data, activate python environment

*my python environment for pypeit is ```Jrusar```. It is recomended to have an environment specifically for pypeit reductions.

## Step 1: Set up

We begin with a fresh directory. In it we will copy paste a pre-existing sensitivity function ```sensfunc.par``` and a telluric correction file ```soar_tellurics.tell```. I tend to reuse the sensitivity function from the last observation that I reduced for the same SOAR setup. More on the sensitivity fucntion shortly. The default ```.tell``` file that igor and I have been using is just:

```
(Jrusar) jon@Jonathans-Laptop example_reduction % head soar_tellurics.tell 
# Auto-generated Telluric input file using PypeIt version: 1.16.0
# UTC 2024-09-04T15:06:16.632+00:00

# User-defined execution parameters
[telluric]
  objmodel = poly
  redshift = 0.0
  bal_wv_min_max = 10000., 11000.
```

Next we make $n+1$ subdirectories ```raw_standard``` and  ```raw_{target_n}``` for each of the $n$ targets we are reducing data from.
```
(Jrusar) jon@Jonathans-Laptop example_reduction % ls -l
total 24
drwxr-xr-x  25 jon  staff   800 Dec 11 14:25 raw_ZTF24abmybnp
drwxr-xr-x  19 jon  staff   608 Dec 11 14:25 raw_standard
-rw-r--r--@  1 jon  staff  1698 Dec 11 16:42 sensfunc.par
-rw-r--r--@  1 jon  staff  1698 Dec 11 14:26 sensfunc_ZTF24abmybnp.par
-rw-r--r--@  1 jon  staff   220 Dec 11 14:27 soar_tellurics.tell
```

Into each of these subdirectories we will move 
- Science spectra for that target
- Arcs taken before and/or after that target 
- Spectroscopic flats taken at the beginning of the night

The pipeline ignores bias and dark images so we can neglect them. For example:
```
(Jrusar) jon@Jonathans-Laptop example_reduction % ls -l raw_ZTF24abmybnp 
total 87984
-rw-r--r--  1 jon  staff  2102400 Dec 11 14:25 0164_GHTS_R_400m1_2x2_12-11-2024.fits.fz
-rw-r--r--  1 jon  staff  2105280 Dec 11 14:25 0165_GHTS_R_400m1_2x2_12-11-2024.fits.fz
-rw-r--r--  1 jon  staff  2105280 Dec 11 14:25 0166_GHTS_R_400m1_2x2_12-11-2024.fits.fz
-rw-r--r--  1 jon  staff  2105280 Dec 11 14:25 0167_GHTS_R_400m1_2x2_12-11-2024.fits.fz
-rw-r--r--  1 jon  staff  2105280 Dec 11 14:25 0168_GHTS_R_400m1_2x2_12-11-2024.fits.fz
-rw-r--r--  1 jon  staff  2105280 Dec 11 14:25 0169_GHTS_R_400m1_2x2_12-11-2024.fits.fz
-rw-r--r--  1 jon  staff  2108160 Dec 11 14:25 0170_GHTS_R_400m1_2x2_12-11-2024.fits.fz
-rw-r--r--  1 jon  staff  2105280 Dec 11 14:25 0171_GHTS_R_400m1_2x2_12-11-2024.fits.fz
-rw-r--r--  1 jon  staff  2105280 Dec 11 14:25 0172_GHTS_R_400m1_2x2_12-11-2024.fits.fz
-rw-r--r--  1 jon  staff  2108160 Dec 11 14:25 0173_GHTS_R_400m1_2x2_12-11-2024.fits.fz
-rw-r--r--  1 jon  staff  2108160 Dec 11 14:25 0174_GHTS_R_400m1_2x2_12-11-2024.fits.fz
-rw-r--r--  1 jon  staff  2108160 Dec 11 14:25 0175_GHTS_R_400m1_2x2_12-11-2024.fits.fz
-rw-r--r--  1 jon  staff  2108160 Dec 11 14:25 0176_GHTS_R_400m1_2x2_12-11-2024.fits.fz
-rw-r--r--  1 jon  staff  2108160 Dec 11 14:25 0177_GHTS_R_400m1_2x2_12-11-2024.fits.fz
-rw-r--r--  1 jon  staff  2108160 Dec 11 14:25 0178_GHTS_R_400m1_2x2_12-11-2024.fits.fz
-rw-r--r--  1 jon  staff  2113920 Dec 11 14:25 0336_ZTF24abmybnp_13-11-2024.fits.fz
-rw-r--r--  1 jon  staff  2079360 Dec 11 14:25 0337_ZTF24abmybnp_13-11-2024_comp.fits.fz
-rw-r--r--  1 jon  staff  1270080 Dec 11 14:25 0338_ZTF24abmybnp_13-11-2024.fits.fz
-rw-r--r--  1 jon  staff  1258560 Dec 11 14:25 0339_ZTF24abmybnp_13-11-2024.fits.fz
-rw-r--r--  1 jon  staff  1244160 Dec 11 14:25 0340_ZTF24abmybnp_13-11-2024.fits.fz
-rw-r--r--  1 jon  staff  1224000 Dec 11 14:25 0341_ZTF24abmybnp_13-11-2024.fits.fz
-rw-r--r--  1 jon  staff  2122560 Dec 11 14:25 0342_ZTF24abmybnp_13-11-2024_comp.fits.fz
-rw-r--r--  1 jon  staff  2108160 Dec 11 14:25 0343_ZTF24abmybnp_13-11-2024.fits.fz
```

We can confirm that all of these files correspond to the correct isntrument setup by running ```pypeit_obslog soar_goodman_{red/blue} -r {path to raw data}``` below is an example for the target.

```
(Jrusar) jon@Jonathans-Laptop example_reduction % pypeit_obslog soar_goodman_red -r raw_ZTF24abmybnp 
[INFO]    :: Building metadata for 23 files.
[INFO]    :: Adding metadata for 0164_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0165_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0166_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0167_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0168_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0169_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0170_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0171_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0172_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0173_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0174_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0175_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0176_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0177_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0178_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0336_ZTF24abmybnp_13-11-2024.fits.fz
[INFO]    :: Adding metadata for 0337_ZTF24abmybnp_13-11-2024_comp.fits.fz
[INFO]    :: Adding metadata for 0338_ZTF24abmybnp_13-11-2024.fits.fz
[INFO]    :: Adding metadata for 0339_ZTF24abmybnp_13-11-2024.fits.fz
[INFO]    :: Adding metadata for 0340_ZTF24abmybnp_13-11-2024.fits.fz
[INFO]    :: Adding metadata for 0341_ZTF24abmybnp_13-11-2024.fits.fz
[INFO]    :: Adding metadata for 0342_ZTF24abmybnp_13-11-2024_comp.fits.fz
[INFO]    :: Adding metadata for 0343_ZTF24abmybnp_13-11-2024.fits.fz
[INFO]    :: Typing files
[WARNING] :: Cannot determine if frames are of type align.
[WARNING] :: Cannot determine if frames are of type lampoffflats.
[WARNING] :: Cannot determine if frames are of type scattlight.
[WARNING] :: Cannot determine if frames are of type sky.
[INFO]    :: Typing completed!
[INFO]    :: Using metadata to determine unique configurations.
[INFO]    :: Unique configurations ignore frames with type: ['bias', 'dark']
[INFO]    :: Found 1 unique configuration(s).
[INFO]    :: Unique configurations ignore frames with type: ['bias', 'dark']
                                 filename |                 frametype |                 ra |                 dec |       target | dispname |        decker | binning |                mjd | airmass | exptime |   mode | dispangle | calib | comb_id | bkg_id
 0164_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace |  333.0980208333333 | -17.757653333333334 |        DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82020971065 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0 |      -1 |     -1
 0165_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace |  333.1690958333333 | -17.757730833333333 |        DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82041596065 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0 |      -1 |     -1
 0166_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace |  333.2449708333333 | -17.757817222222222 |        DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82062259259 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0 |      -1 |     -1
 0167_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace |  333.3160416666666 | -17.757898333333333 |        DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82082925926 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0 |      -1 |     -1
 0168_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace |  333.3912916666666 | -17.757981944444445 |        DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82103576389 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0 |      -1 |     -1
 0169_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace | 333.46654166666656 | -17.758068055555555 |        DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82124236111 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0 |      -1 |     -1
 0170_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace | 333.54200416666663 |  -17.75815083333333 |        DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82144900463 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0 |      -1 |     -1
 0171_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace |  333.6130708333333 | -17.758230833333332 |        DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82165528935 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0 |      -1 |     -1
 0172_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace | 333.68853333333334 |         -17.7583125 |        DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 | 60626.821861909724 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0 |      -1 |     -1
 0173_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace |  333.7639958333333 |  -17.75839638888889 |        DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |   60626.8220684375 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0 |      -1 |     -1
 0174_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace |  333.8394541666666 | -17.758480833333333 |        DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |       60626.822275 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0 |      -1 |     -1
 0175_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace | 333.91470416666664 | -17.758564166666666 |        DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82248150463 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0 |      -1 |     -1
 0176_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace | 333.99016666666665 | -17.758645277777777 |        DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82268775463 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0 |      -1 |     -1
 0177_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace | 334.06562499999995 |  -17.75873027777778 |        DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82289416667 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0 |      -1 |     -1
 0178_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace |  334.1410874999999 |  -17.75881111111111 |        DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82310065972 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0 |      -1 |     -1
     0336_ZTF24abmybnp_13-11-2024.fits.fz | pixelflat,illumflat,trace | 122.80211249999999 |  20.380323333333333 | ZTF24abmybnp | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60627.29941267361 |     2.0 |     3.0 | 400_M1 |    5.8003 |     0 |      -1 |     -1
0337_ZTF24abmybnp_13-11-2024_comp.fits.fz |                  arc,tilt | 122.95965416666665 |  20.383306666666666 | ZTF24abmybnp | 400_SYZY | 1.0_LONG_SLIT |     2,2 |   60627.2999428125 |     2.0 |     0.5 | 400_M1 |    5.8003 |     0 |      -1 |     -1
     0338_ZTF24abmybnp_13-11-2024.fits.fz |                   science | 122.79927083333332 |          20.3831275 | ZTF24abmybnp | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60627.30646590278 |    1.93 |   300.0 | 400_M1 |    5.8001 |     0 |       1 |     -1
     0339_ZTF24abmybnp_13-11-2024.fits.fz |                   science | 122.79930833333333 |  20.383105555555556 | ZTF24abmybnp | 400_SYZY | 1.0_LONG_SLIT |     2,2 | 60627.310063275465 |     1.9 |   300.0 | 400_M1 |       5.8 |     0 |       2 |     -1
     0340_ZTF24abmybnp_13-11-2024.fits.fz |                   science |        122.7993375 |            20.38308 | ZTF24abmybnp | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60627.31365993056 |    1.87 |   300.0 | 400_M1 |       5.8 |     0 |       3 |     -1
     0341_ZTF24abmybnp_13-11-2024.fits.fz |                   science |          122.79925 |  20.383123333333334 | ZTF24abmybnp | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60627.31726011574 |    1.84 |   300.0 | 400_M1 |    5.7999 |     0 |       4 |     -1
0342_ZTF24abmybnp_13-11-2024_comp.fits.fz |                  arc,tilt |         122.799275 |  20.383143055555557 | ZTF24abmybnp | 400_SYZY | 1.0_LONG_SLIT |     2,2 | 60627.322619872684 |     1.8 |     0.5 | 400_M1 |    5.7991 |     0 |      -1 |     -1
     0343_ZTF24abmybnp_13-11-2024.fits.fz | pixelflat,illumflat,trace |         122.799325 |          20.3830125 | ZTF24abmybnp | 400_SYZY | 1.0_LONG_SLIT |     2,2 | 60627.323807326386 |    1.79 |     3.0 | 400_M1 |    5.7995 |     0 |      -1 |     -1
```

We now creat $n+1$ files ```reduced_{target n/standard}``` and in each run ```pypeit_setup -s soar_goodman_{red/blue} -r {path to raw data} -c all

```(Jrusar) jon@Jonathans-Laptop example_reduction % mkdir reduced_ZTF24abmybnp
(Jrusar) jon@Jonathans-Laptop example_reduction % mkdir reduced_standard
(Jrusar) jon@Jonathans-Laptop example_reduction % cd reduced_ZTF24abmybnp 
(Jrusar) jon@Jonathans-Laptop reduced_ZTF24abmybnp % pypeit_setup -s soar_goodman_red -r ../raw_ZTF24abmybnp -c all
[INFO]    :: Building metadata for 23 files.
[INFO]    :: Adding metadata for 0164_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0165_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0166_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0167_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0168_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0169_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0170_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0171_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0172_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0173_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0174_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0175_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0176_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0177_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0178_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0336_ZTF24abmybnp_13-11-2024.fits.fz
[INFO]    :: Adding metadata for 0337_ZTF24abmybnp_13-11-2024_comp.fits.fz
[INFO]    :: Adding metadata for 0338_ZTF24abmybnp_13-11-2024.fits.fz
[INFO]    :: Adding metadata for 0339_ZTF24abmybnp_13-11-2024.fits.fz
[INFO]    :: Adding metadata for 0340_ZTF24abmybnp_13-11-2024.fits.fz
[INFO]    :: Adding metadata for 0341_ZTF24abmybnp_13-11-2024.fits.fz
[INFO]    :: Adding metadata for 0342_ZTF24abmybnp_13-11-2024_comp.fits.fz
[INFO]    :: Adding metadata for 0343_ZTF24abmybnp_13-11-2024.fits.fz
[INFO]    :: Typing files
[WARNING] :: Cannot determine if frames are of type align.
[WARNING] :: Cannot determine if frames are of type lampoffflats.
[WARNING] :: Cannot determine if frames are of type scattlight.
[WARNING] :: Cannot determine if frames are of type sky.
[INFO]    :: Typing completed!
[INFO]    :: Using metadata to determine unique configurations.
[INFO]    :: Unique configurations ignore frames with type: ['bias', 'dark']
[INFO]    :: Found 1 unique configuration(s).
[INFO]    :: Unique configurations ignore frames with type: ['bias', 'dark']
[INFO]    :: PypeIt file successfully vetted.
[INFO]    :: PypeIt input file written to: /Users/jon/Research/ATALab/observing/SOAR/tutorial/example_reduction/reduced_ZTF24abmybnp/soar_goodman_red_A/soar_goodman_red_A.pypeit
[INFO]    :: Calibration association file written to: /Users/jon/Research/ATALab/observing/SOAR/tutorial/example_reduction/reduced_ZTF24abmybnp/soar_goodman_red_A/soar_goodman_red_A.calib
(Jrusar) jon@Jonathans-Laptop reduced_ZTF24abmybnp % cd ..
(Jrusar) jon@Jonathans-Laptop example_reduction % cd reduced_standard 
(Jrusar) jon@Jonathans-Laptop reduced_standard % pypeit_setup -s soar_goodman_red -r ../raw_standard -c all
[INFO]    :: Building metadata for 17 files.
[INFO]    :: Adding metadata for 0164_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0165_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0166_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0167_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0168_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0169_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0170_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0171_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0172_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0173_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0174_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0175_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0176_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0177_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0178_GHTS_R_400m1_2x2_12-11-2024.fits.fz
[INFO]    :: Adding metadata for 0284_Calibration-Star_13-11-2024.fits.fz
[INFO]    :: Adding metadata for 0285_Calibration-Star_13-11-2024_comp.fits.fz
[INFO]    :: Typing files
[WARNING] :: Cannot determine if frames are of type align.
[WARNING] :: Cannot determine if frames are of type lampoffflats.
[WARNING] :: Cannot determine if frames are of type scattlight.
[WARNING] :: Cannot determine if frames are of type sky.
[INFO]    :: Typing completed!
[INFO]    :: Using metadata to determine unique configurations.
[INFO]    :: Unique configurations ignore frames with type: ['bias', 'dark']
[INFO]    :: Found 1 unique configuration(s).
[INFO]    :: Unique configurations ignore frames with type: ['bias', 'dark']
[INFO]    :: PypeIt file successfully vetted.
[INFO]    :: PypeIt input file written to: /Users/jon/Research/ATALab/observing/SOAR/tutorial/example_reduction/reduced_standard/soar_goodman_red_A/soar_goodman_red_A.pypeit
[INFO]    :: Calibration association file written to: /Users/jon/Research/ATALab/observing/SOAR/tutorial/example_reduction/reduced_standard/soar_goodman_red_A/soar_goodman_red_A.calib
```

We now go into each new ```soar_goodman_red_A``` directory and edit the ```.pypeit``` file if needed. Sometimes SOAR does not have a the science files lsited as science files they need to be un-commented out and have the "frametype" edited from ```None``` to ```science```. This will be visible in ```pypeit_obslog```. The file should look like the following:

```
# Auto-generated PypeIt input file using PypeIt version: 1.16.0
# UTC 2024-12-11T22:05:14.841+00:00

# User-defined execution parameters
[rdx]
    spectrograph = soar_goodman_red

# Setup
setup read
Setup A:
  binning: 2,2
  decker: 1.0_LONG_SLIT
  dispangle: 5.8001
  dispname: 400_SYZY
  mode: 400_M1
setup end

# Data block
data read
 path /Users/jon/Research/ATALab/observing/SOAR/tutorial/example_reduction/raw_standard
                                     filename |                 frametype |                 ra |                 dec |   target | dispname |        decker | binning |                mjd | airmass | exptime |   mode | dispangle | calib
0285_Calibration-Star_13-11-2024_comp.fits.fz |                  arc,tilt | 349.99344999999994 |  -5.166756944444445 | Feige110 | 400_SYZY | 1.0_LONG_SLIT |     2,2 | 60627.008673449076 |    1.11 |     0.5 | 400_M1 |    5.8002 |     0
     0164_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace |  333.0980208333333 | -17.757653333333334 |    DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82020971065 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0
     0165_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace |  333.1690958333333 | -17.757730833333333 |    DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82041596065 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0
     0166_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace |  333.2449708333333 | -17.757817222222222 |    DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82062259259 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0
     0167_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace |  333.3160416666666 | -17.757898333333333 |    DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82082925926 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0
     0168_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace |  333.3912916666666 | -17.757981944444445 |    DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82103576389 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0
     0169_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace | 333.46654166666656 | -17.758068055555555 |    DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82124236111 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0
     0170_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace | 333.54200416666663 |  -17.75815083333333 |    DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82144900463 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0
     0171_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace |  333.6130708333333 | -17.758230833333332 |    DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82165528935 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0
     0172_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace | 333.68853333333334 |         -17.7583125 |    DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 | 60626.821861909724 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0
     0173_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace |  333.7639958333333 |  -17.75839638888889 |    DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |   60626.8220684375 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0
     0174_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace |  333.8394541666666 | -17.758480833333333 |    DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |       60626.822275 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0
     0175_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace | 333.91470416666664 | -17.758564166666666 |    DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82248150463 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0
     0176_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace | 333.99016666666665 | -17.758645277777777 |    DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82268775463 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0
     0177_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace | 334.06562499999995 |  -17.75873027777778 |    DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82289416667 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0
     0178_GHTS_R_400m1_2x2_12-11-2024.fits.fz | pixelflat,illumflat,trace |  334.1410874999999 |  -17.75881111111111 |    DFLAT | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60626.82310065972 |    1.66 |     7.0 | 400_M1 |    5.8001 |     0
     0284_Calibration-Star_13-11-2024.fits.fz |                   science | 349.99344999999994 |  -5.166759444444445 | Feige110 | 400_SYZY | 1.0_LONG_SLIT |     2,2 |  60627.00680011574 |    1.11 |  120.85 | 400_M1 |    5.8001 |     0
data end
```
Once the ```.pypeit``` file is ready run pypeit with ```(Jrusar) jon@Jonathans-Laptop reduced_standard % run_pypeit soar_goodman_red_A/soar_goodman_red_A.pypeit```

This will create a 1dspec .fits file, a 1dspec .txt file, and a 2dspec .fits file for each science image
```
(Jrusar) jon@Jonathans-Laptop reduced_standard % ls -l Science 
total 145048
-rw-r--r--@ 1 jon  staff    388800 Dec 12 11:53 spec1d_0284_Calibration-Star_13-11-2024-Feige110_red_20241113T000947.530.fits
-rw-r--r--@ 1 jon  staff       210 Dec 12 11:53 spec1d_0284_Calibration-Star_13-11-2024-Feige110_red_20241113T000947.530.txt
-rw-r--r--@ 1 jon  staff  73869120 Dec 12 11:53 spec2d_0284_Calibration-Star_13-11-2024-Feige110_red_20241113T000947.530.fits
```

## Step 3: Sensitivity Function

Now we need to create a sensitivty file in order to do flux claibration. In order to do so we begin with our pre-existing parameter file. In this case we begin with the following:

```
(Jrusar) jon@Jonathans-Laptop example_reduction % head -n 100 sensfunc.par 
[sensfunc]
    flatfile = None
    extrap_blu = 0.1
    extrap_red = 0.1
    samp_fact = 1.5
    multi_spec_det = None
    algorithm = UVIS
    polyorder = 5
    star_type = None
    star_mag = None
    star_ra = None
    star_dec = None
    mask_hydrogen_lines = True
    mask_helium_lines = True
    hydrogen_mask_wid = 27.0
    [[UVIS]]
        std_file = None
        std_obj_id = None
        sensfunc = None
        extinct_correct = True
        extinct_file = closest
        telluric_correct = False
        telluric = False
        polycorrect = False
        polyfunc = False
        nresln = 15
        resolution = 800.0
        trans_thresh = 0.9
    [[IR]]
        telgridfile = None
        sn_clip = 30.0
        resln_guess = None
        resln_frac_bounds = (0.6, 1.4)
        pix_shift_bounds = (-5.0, 5.0)
        delta_coeff_bounds = (-20.0, 20.0)
        minmax_coeff_bounds = (-5.0, 5.0)
        maxiter = 2
        tell_npca = 5
        teltype = pca
        sticky = True
        lower = 3.0
        upper = 3.0
        seed = 777
        tol = 0.001
        popsize = 30
        recombination = 0.7
        polish = True
        disp = False
        objmodel = None
        redshift = 0.0
        delta_redshift = 0.1
        pca_file = qso_pca_1200_3100.fits
        npca = 8
        bal_wv_min_max = None
        bounds_norm = (0.1, 3.0)
        tell_norm_thresh = 0.9
        only_orders = None
        pca_lower = 1220.0
        pca_upper = 3100.0
        star_type = None
        star_mag = None
        star_ra = None
        star_dec = None
        func = legendre
        model = exp
        polyorder = 3
        fit_wv_min_max = None
        mask_lyman_a = True%                                                                                                                                                                                      
    ```

Navigate to the reduction directory for the first target then run the command ```pypeit_sensfunc -s {path to sensfunction .par file} -o {output .fts file defining sensitivity function} --debug {path to a standard star 1dspec .fits file}```. The ```--debug``` flag will generate the following plots.

```
(Jrusar) jon@Jonathans-Laptop reduced_ZTF24abmybnp % pypeit_sensfunc -s ../sensfunc.par -o 400m1_sens.fits --debug ../reduced_standard/Science/spec1d_0284_Calibration-Star_13-11-2024-Feige110_red_20241113T000947.530.fits 
```

b spline fit             |  Flux Comparison
:-------------------------:|:-------------------------:
![](bspline_fit.png)  |  ![](flux_comparison.png)

In this case our sensitivty function looks good (we don't expect SOAR goodman redcam to work well below 3800 Angstroms). But if we for some reason had a poor fit (the refence flux and the observed flux not lining up) we would play with the parameters of our sensitivty function in our ```.par``` file. A partial list of variables with explanations can be found [here](https://pypeit.readthedocs.io/en/staged/pypeit_par.html#sensfuncpar-keywords).

Once we have created this sensitivity fiel we can reuse it for all of our other targets.

## Step 4: Fluxing

Now in each of our target reduction directories we run ```pypeit_flux_setup {path to pypeit produced Science iamges}```

```
(Jrusar) jon@Jonathans-Laptop reduced_ZTF24abmybnp % pypeit_flux_setup Science 
[INFO]    :: Flux input file written to: soar_goodman_red.flux
[INFO]    :: Coadd1D input file written to: soar_goodman_red.coadd1d
[INFO]    :: Telluric input file written to: soar_goodman_red.tell
```

This creates 2 fiels we will use, a .flux file and a .coadd1d file.

We now open the flux file which will look soemthign like the following:
```
(Jrusar) jon@Jonathans-Laptop reduced_ZTF24abmybnp % head -n 25 soar_goodman_red.flux
# Auto-generated Flux input file using PypeIt version: 1.16.0
# UTC 2024-12-13T18:59:48.683+00:00

# User-defined execution parameters
[fluxcalib]
  extinct_correct = False  # Set to True if your SENSFUNC derived with the UVIS algorithm
# Please add your SENSFUNC file name below before running pypeit_flux_calib

# Data block 
flux read
 path Science
                                                                     filename | sensfile
spec1d_0341_ZTF24abmybnp_13-11-2024-ZTF24abmybnp_red_20241113T073651.274.fits |         
spec1d_0340_ZTF24abmybnp_13-11-2024-ZTF24abmybnp_red_20241113T073140.218.fits |         
spec1d_0339_ZTF24abmybnp_13-11-2024-ZTF24abmybnp_red_20241113T072629.467.fits |         
spec1d_0338_ZTF24abmybnp_13-11-2024-ZTF24abmybnp_red_20241113T072118.654.fits |         
flux end
```

And make the following edits:
- add the current directory and any other needed directories to the path
- add the name of the sensitvity file we created in step 3 to the right column of the table

```
(Jrusar) jon@Jonathans-Laptop reduced_ZTF24abmybnp % head -n 24 soar_goodman_red.flux 
# Auto-generated Flux input file using PypeIt version: 1.16.0
# UTC 2024-12-13T18:59:48.683+00:00

# User-defined execution parameters
[fluxcalib]
  extinct_correct = False  # Set to True if your SENSFUNC derived with the UVIS algorithm
# Please add your SENSFUNC file name below before running pypeit_flux_calib

# Data block 
flux read
 path ./
 path Science
                                                                     filename | sensfile
spec1d_0341_ZTF24abmybnp_13-11-2024-ZTF24abmybnp_red_20241113T073651.274.fits | 400m1_sens.fits 
spec1d_0340_ZTF24abmybnp_13-11-2024-ZTF24abmybnp_red_20241113T073140.218.fits | 400m1_sens.fits
spec1d_0339_ZTF24abmybnp_13-11-2024-ZTF24abmybnp_red_20241113T072629.467.fits | 400m1_sens.fits
spec1d_0338_ZTF24abmybnp_13-11-2024-ZTF24abmybnp_red_20241113T072118.654.fits | 400m1_sens.fits
flux end
```

Then for each target run ```pypeit_flux_calib soar_goodman_{red/blue}.flux```

```
(Jrusar) jon@Jonathans-Laptop reduced_ZTF24abmybnp % pypeit_flux_calib soar_goodman_red.flux 
```

## Step 5: Coaddition

Next we'll look at the .coadd1d file created by ```pypeit_flux_setup``` in step 4. In it there will be a list of each target found for a given file. Below is an example.

```
(Jrusar) jon@Jonathans-Laptop reduced_ZTF24abmybnp % head -n 30 soar_goodman_red.coadd1d 
# Auto-generated Coadd1D input file using PypeIt version: 1.16.0
# UTC 2024-12-13T18:59:48.686+00:00

# User-defined execution parameters
[coadd1d]
  coaddfile = YOUR_OUTPUT_FILE_NAME  # Please set your output file name
  wave_method = linear  # creates a uniformly space grid in lambda
# This file includes all extracted objects. You need to figure out which object you want to 
# coadd before running pypeit_coadd_1dspec!!!

# Data block 
coadd1d read
 path Science
                                                                     filename |                  obj_id
spec1d_0341_ZTF24abmybnp_13-11-2024-ZTF24abmybnp_red_20241113T073651.274.fits | SPAT0498-SLIT0493-DET01
spec1d_0340_ZTF24abmybnp_13-11-2024-ZTF24abmybnp_red_20241113T073140.218.fits | SPAT0498-SLIT0493-DET01
spec1d_0339_ZTF24abmybnp_13-11-2024-ZTF24abmybnp_red_20241113T072629.467.fits | SPAT0498-SLIT0493-DET01
spec1d_0338_ZTF24abmybnp_13-11-2024-ZTF24abmybnp_red_20241113T072118.654.fits | SPAT0498-SLIT0493-DET01
coadd1d end
```

We can also see a list of sources that pypeit found in the slit by running ```pypeit_show_1dspec {path the spec1d.fits} --list```

```
(Jrusar) jon@Jonathans-Laptop reduced_ZTF24abmybnp % pypeit_show_1dspec Science/spec1d_0341_ZTF24abmybnp_13-11-2024-ZTF24abmybnp_red_20241113T073651.274.fits --list
Showing object names for input file...
EXT0000001 = SPAT0498-SLIT0493-DET01
```

In this example pypeit only found one sourcei n each image. If it were to find multiple we would need to remove all object ids that were not our source. Thsi is where DS9 can be very helpful as the object id is correpsonds to pixel positions along the slit.

We edit the .coadd1d file as follows:
- put in the desired output filename. I usually do {Fritz target name}_coadd.fits
- add any relevant paths other than Science, I always add ./ as it can error otherwise.
- remove all non-target object ids

```
(Jrusar) jon@Jonathans-Laptop reduced_ZTF24abmybnp % head -n 30 soar_goodman_red.coadd1d                                                                            
# Auto-generated Coadd1D input file using PypeIt version: 1.16.0
# UTC 2024-12-13T18:59:48.686+00:00

# User-defined execution parameters
[coadd1d]
  coaddfile = ZTF24abmybnp_coadd.fits  # Please set your output file name
  wave_method = linear  # creates a uniformly space grid in lambda
# This file includes all extracted objects. You need to figure out which object you want to 
# coadd before running pypeit_coadd_1dspec!!!

# Data block 
coadd1d read
 path ./
 path Science
                                                                     filename |                  obj_id
spec1d_0341_ZTF24abmybnp_13-11-2024-ZTF24abmybnp_red_20241113T073651.274.fits | SPAT0498-SLIT0493-DET01
spec1d_0340_ZTF24abmybnp_13-11-2024-ZTF24abmybnp_red_20241113T073140.218.fits | SPAT0498-SLIT0493-DET01
spec1d_0339_ZTF24abmybnp_13-11-2024-ZTF24abmybnp_red_20241113T072629.467.fits | SPAT0498-SLIT0493-DET01
spec1d_0338_ZTF24abmybnp_13-11-2024-ZTF24abmybnp_red_20241113T072118.654.fits | SPAT0498-SLIT0493-DET01
coadd1d end
```

Now run ```pypeit_coadd_1dspec {.coadd1d file}
```
(Jrusar) jon@Jonathans-Laptop reduced_ZTF24abmybnp % pypeit_coadd_1dspec soar_goodman_red.coadd1d
'''

We now have a coadded file.

## Step 6: Telluric correction

We began with a pre defined .tell file and produced one in step 4. The only difference is the object model that is used. We use ```poly``` in place of the default ```qso```. You may prefer to jsut edit the automatically produced .tell file.

```
(Jrusar) jon@Jonathans-Laptop reduced_ZTF24abmybnp % head -n 25 ../soar_tellurics.tell 
# Auto-generated Telluric input file using PypeIt version: 1.16.0
# UTC 2024-09-04T15:06:16.632+00:00

# User-defined execution parameters
[telluric]
  objmodel = poly
  redshift = 0.0
  bal_wv_min_max = 10000., 11000.

(Jrusar) jon@Jonathans-Laptop reduced_ZTF24abmybnp % head -n 25 soar_goodman_red.tell 
# Auto-generated Telluric input file using PypeIt version: 1.16.0
# UTC 2024-12-13T18:59:48.687+00:00

# User-defined execution parameters
[telluric]
  objmodel = qso
  redshift = 0.0
  bal_wv_min_max = 10000., 11000.
  ```

Now we just need to apply telluric corrections with ```pypeit_tellfit {path to coadd file} -t {.tell file}

```
(Jrusar) jon@Jonathans-Laptop reduced_ZTF24abmybnp % pypeit_tellfit ZTF24abmybnp_coadd.fits -t ../soar_tellurics.tell 
```

## Step 7: Make into an .ascii file for Fritz

Lastly we use Igor's script from SOAR DPS to write as .ascii file of the spectrum with the command ```python3 {path to write_ascii_soar_spec.py} {coadd file name}``` optionally we can include the flags ```-cwl``` and ```cwu``` to change the upper and lower wavelength cutoffs repectively. The daults are 3800 and 7200 respectively. Theis will also print the MJD which is needed for the Fritz upload and display the fully reduced spectrum with errors.

```
(Jrusar) jon@Jonathans-Laptop reduced_ZTF24abmybnp % python3 ~/Research/ATALab/software/soar-dps/write_ascii_soar_spec.py ZTF24abmybnp_coadd.fits 
Working on ZTF24abmybnp_coadd.fits
MJD = 60627.31726011574
```

![](reduced_spectrum.png)
