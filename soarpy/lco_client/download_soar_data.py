import logging
import os
import subprocess
import argparse
from datetime import datetime
from enum import Enum

import requests
from astropy.time import Time
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table
from rich import box
from rich import print as rprint


class ReductionLevel(Enum):
    RAW = "raw"
    REDUCED = "reduced"
    ALL = "all"

OBS_MODES = {
    'photometry': {'ghts_blue_imager', 'ghts_red_imager'},
    'spectroscopy': {'ghts_blue', 'ghts_red', 'triplespec'}
}
DEFAULT_INSTRUMENTS = list(OBS_MODES["photometry"] | OBS_MODES["spectroscopy"] - {"triplespec"})

FRAME_TYPES = {
    'calibration': {'bias', 'lampflat', 'arc'},
    'science': {'expose', 'spectrum'}
}

LCO_FRAME_URL = 'https://archive-api.lco.global/frames/'

SOAR_TELESCOPE_ID = '4m0a'
QUERY_LIMIT = 200

DATA_DOWNLOAD_DIR = os.path.expanduser(f"~/Downloads/soar_download_{datetime.now().strftime('%y%m%dT%H%M%S')}")
PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(PACKAGE_ROOT, "logs")


os.makedirs(LOG_DIR, exist_ok=True)

log_filename = os.path.join(LOG_DIR, f"soar_data_download_{datetime.now().strftime('%y%m%dT%H%M%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    handlers=[
        RichHandler(rich_tracebacks=True, markup=True, show_time=False, show_path=False),
        logging.FileHandler(log_filename),
    ]
)

logger = logging.getLogger(__name__)
console = Console()


def format_elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    else:
        hours = seconds / 3600
        return f"{hours:.2f} hours"


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download SOAR data from the LCO archive.")

    # time range (required)
    parser.add_argument("--tstart", type=str, required=True, 
                        help="Start time in ISO format (e.g. 2026-05-01)")
    parser.add_argument("--tend", type=str, required=True, 
                        help="End time in ISO format (e.g. 2026-05-22)")

    # filters (all optional)
    parser.add_argument("--frame_types", type=str, nargs="+", 
                        choices=["bias", "arc", "lampflat", "expose", "spectrum"],
                        help="Frame types to download. Multiple values allowed. If nothing is specified, everything will be downloaded. You can use multiple frametyoes as: --frame_types bias arc lampflat")
    parser.add_argument("--instruments", type=str, nargs="+",
                    choices=["ghts_blue", "ghts_red", "ghts_blue_imager", "ghts_red_imager", "triplespec"],
                    default=DEFAULT_INSTRUMENTS,
                    help="Instruments to filter on. Default: all GHTS instruments except triplespec.")
    parser.add_argument("--obs_modes", type=str, nargs="+", 
                        choices=["photometry", "spectroscopy"],
                        help="Observation modes to filter on. Expands to the relevant instruments. Multiple values allowed. If not specified, will include all observation modes. You can use multiple obs modes as: --obs_modes photometry spectroscopy")
    parser.add_argument("--gratings", type=str, nargs="+", 
                        choices=["400_M1", "400_M2"],
                        help="Gratings to filter on. Multiple values allowed. If not specified, will include all gratings. You can use multiple gratings as: --gratings 400_M1 400_M2")
    parser.add_argument("--target_name", type=str, nargs="+",
                        help="Target names to filter on. Multiple values allowed. If not specified, will include all targets. You can use multiple target names as: --target_names 'grb170817a' 'grb676767'")
    parser.add_argument("--reduction_level", type=str, 
                        choices=["raw", "reduced", "all"], default="reduced",
                        help="Filter by reduction level. Default: reduced. Use 'raw' to get only raw frames, 'reduced' to get only LCO reduced frames, and 'all' to get everything.")

    # output
    parser.add_argument("--output_dir", type=str, default=DATA_DOWNLOAD_DIR,
                        help=f"Directory to save downloaded data. Default: {DATA_DOWNLOAD_DIR}")

    # download behaviour
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--structured", action="store_true",
                            help="Download into date/target/frame_type/grating structure.")
    mode_group.add_argument("--unstructured", action="store_true",
                            help="Download all files into a flat directory.")
    mode_group.add_argument("--query_only", action="store_true",
                            help="Only query and classify frames, do not download.")

    return parser


def handshake(lco_token=None) -> tuple[str, dict[str, str]]:
    """
    Authenticate with the LCO API using the LCO_TOKEN
    environment variable.
    """

    # if there is no lco toekn provided as an argument, check the environment variable
    if lco_token is None:
        logger.info("LCO_TOKEN not provided as argument, checking environment variable")
        lco_token = os.getenv("LCO_TOKEN")
        if lco_token:
            logger.info("Found LCO_TOKEN environment variable")
        else:
            logger.error("LCO_TOKEN not found in environment variables. Please set it or provide it as an argument.")
            raise ValueError("LCO_TOKEN not found, authentication failed.")
    else:
        logger.info("Using LCO_TOKEN from argument")
        lco_token = lco_token

    # Set up the headers for authentication
    headers = {
        "Authorization": f"Token {lco_token}"
    }

    # putting this block in try except to catch if the error is due to bad internet.
    try:
        response = requests.get(
            "https://archive-api.lco.global/profile/",
            headers=headers,
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Error during authentication: {e}")
        raise

    #FIXME: this block below is a lil redundant as its looking for a response.status code for error. At this point, I am nit too sure if the response.status code will give an bad internet error. Keeping this for now, and need to look into this a bit later. 
    if response.status_code != 200:
        logger.error(f"Authentication failed with status code {response.status_code}")
        raise ValueError("Authentication failed, check your LCO_TOKEN")

    # get the data as json
    data = response.json()

    # get the username from the data, if it exists
    username = data.get("username", "user")
    logger.info(f"Authenticated successfully as {username}")

    return lco_token, headers


def create_time_windows(tstart: str, 
                        tend: str) -> list[tuple[str, str]]:

    """
    If the requested time window is larger than one day, there will be a lot of files to query. So this function will create sclies of 1 JD between tstart and tend.

    Edge case: if tstop - tend is not exactly an integer multiple of 1JD, then it will make tstart + 1 JD as long as it is less than tstop, and then the last window will be from the last tstart + 1 JD to tstop.

    I am working in JD, as its easier (1 JD = 1 day).
    """

    #conver the time strings to JD
    tstart_jd = Time(tstart, format="isot").jd
    tend_jd = Time(tend, format="isot").jd

    time_windows = []

    # define a variable current_jd, that we can use as a counter for while loop.
    current_jd = tstart_jd
    logger.info(f"Creating 1 day time windows from {tstart} to {tend}")

    # sanity check for the end date. 
    if tend_jd > Time.now().jd:
        logger.warning("End date is in the future. Adjusting to current time.")
        tend_jd = Time.now().jd

    # create time slices, and convert them back to isot format for the query.
    while current_jd < tend_jd:
        
        next_jd = min(current_jd + 1, tend_jd)
        
        t0_isot = Time(current_jd, format="jd").isot
        t1_isot = Time(next_jd, format="jd").isot

        # append to the main array that will be the function retuen
        time_windows.append((t0_isot, t1_isot))
        
        current_jd = next_jd

    return time_windows


def get_frames(tstart: str,
                tstop: str, 
                headers) -> list[dict]: # return a list of ddict of frame metadata.

    # getting the frames for the given time window is the easiest broad filter we can apply to our query. Since at this stage, we are just querying, it doesnt matter. We can apply more specific filters while downloading.

    #FIXME: Still thinking if its a good idea to dump the response to a temp json locally as a query output. There is no immediate need for this. So I am not doing it as of now. 

    # slice the time windows
    time_windows = create_time_windows(tstart, tstop)

    # top level list that will be retuened by the function
    all_frames = []

    # fancy logging animation for the query process in terminal.
    with console.status(f"[bold grey]Querying SOAR Archive from {tstart} to {tstop}") as status:
        for t0, t1 in time_windows:
            status.update(f"Querying {t0} to {t1}")
            
            # payload for the query.
            params = {
                'start': t0,
                'end': t1,
                'telescope_id': SOAR_TELESCOPE_ID,
                'limit': QUERY_LIMIT,
            }

            # define the url, then use pagination to go through all the results in a loop.
            current_url = LCO_FRAME_URL

            # temp list to store this loops result.
            frames = []
            while current_url:

                # same logic as for authentication, putting this in try except to catch bad internet error.
                try:
                    response = requests.get(
                        current_url,
                        headers=headers,
                        params=params if current_url == LCO_FRAME_URL else None,
                        timeout=10,
                    )

                # break for both cases, internet or bad response.
                except requests.exceptions.RequestException as e:
                    logger.error(f"Error during API request: {e}")
                    break


                if response.status_code != 200:
                    logger.error(f"Error code {response.status_code} while fetching frames: {response.text}")
                    break

                
                last_data = response.json()
                frames.extend(last_data.get("results", []))
                current_url = last_data.get("next")

            
            all_frames.extend(frames)
    logger.info(f"Retrieved {len(all_frames)} frames for window {tstart} to {tstop}.")
    return all_frames


def filter_frames(
                all_frames: list[dict],
                frame_types: list[str] | None = None,
                instruments: list[str] | None = None,
                gratings: list[str] | None = None,
                target_names: list[str] | None = None,
                reduction_level: str = ReductionLevel.ALL.value,
            ) -> list[dict]:
    """
    Filter the flat list of frames by any combination of criteria.
    Unspecified filters pass everything through.
    Within a filter, values are OR'd. Across filters, they are AND'd.
    """

    frames = all_frames

    # filter by frame type (bias, arc, lampflat, expose, spectrum)
    if frame_types is not None:
        wanted = {ft.lower() for ft in frame_types}
        frames = [f for f in frames if f.get("OBSTYPE", "").lower() in wanted]

    # filter by instrument (ghts_blue, ghts_red)
    if instruments is not None:
        wanted = {inst.lower() for inst in instruments}
        frames = [f for f in frames if f.get("INSTRUME", "").lower() in wanted]

    # filter by target name (OBJECT field)
    if target_names is not None:
        wanted = {t.lower() for t in target_names}
        frames = [f for f in frames if f.get("OBJECT", "").lower() in wanted]

    # filter by reduction level
    if reduction_level == ReductionLevel.RAW.value:
        frames = [f for f in frames if "cfzst" not in f.get("filename", "").lower()]
    elif reduction_level == ReductionLevel.REDUCED.value:
        frames = [f for f in frames if "cfzst" in f.get("filename", "").lower()]

    logger.info(f"Filtered {len(all_frames)} frames down to {len(frames)}.")
    return frames


def classify_frames(frames: list[dict]) -> dict:
    """
    Nest filtered frames into:
        date -> target -> frame_type -> grating -> [frames]

    Standard stars are identified by PROPID='calibrate' and 'calibration-star'
    in the filename, and tagged as std_{OBJECT} at the target level.
    """

    classified = {}

    for frame in frames:

        # date in YYMMDD format from DAY_OBS
        date_raw = frame.get("DAY_OBS", "unknown_date")
        try:
            date = datetime.strptime(date_raw, "%Y-%m-%d").strftime("%y%m%d")
        except (ValueError, TypeError):
            logger.warning(f"Frame has invalid DAY_OBS '{date_raw}', tagging as 'unknown_date'.")
            date = "unknown_date"

        # target: flag standard stars using PROPID or filename
        target = frame.get("OBJECT", "unknown_target")
        is_standard = (
            frame.get("PROPID", "").lower() == "calibrate" and
            "calibration-star" in frame.get("filename", "").lower()
        )
        if is_standard:
            target = f"std_{target}"

        # frame type from OBSTYPE
        frame_type = frame.get("OBSTYPE", "unknown_type").lower()

        #FIXME: its not actually finding the grating with this key. needs more testing.
        grating = frame.get("primary_optical_element", "unknown_grating").upper()


        instrument = frame.get("INSTRUME", "unknown").upper()
        if instrument.lower() in OBS_MODES["photometry"]:
            obs_mode = "photometry"
        elif instrument.lower() in OBS_MODES["spectroscopy"]:
            obs_mode = "spectroscopy"
        else:
            obs_mode = "unknown"

        # build the nested dict
        classified.setdefault(obs_mode, {}) \
                .setdefault(date, {}) \
                .setdefault(target, {}) \
                .setdefault(frame_type, {}) \
                .setdefault(instrument, []) \
                .append(frame)

    return classified

def print_summary_table(classified_frames: dict) -> None:
    """
    Print a rich table summarizing the classified frames.
    Columns: Date | Target | Frame Type | Instrument | Count
    """
    table = Table(
        title="\nSummary of available data based on your query\n",
        header_style="bold magenta",
        box=box.ROUNDED,
        show_lines=False,
    )

    table.add_column("Date")
    table.add_column("Target")
    table.add_column("Frame Type")
    table.add_column("Instrument")
    table.add_column("Count", justify="center")

    total = 0
    for obs_mode, dates in classified_frames.items():
        date_items = list(dates.items())
        for di, (date, targets) in enumerate(date_items):
            target_items = list(targets.items())
            for ti, (target, frame_types) in enumerate(target_items):
                ft_items = list(frame_types.items())
                for fti, (frame_type, instruments) in enumerate(ft_items):
                    inst_items = list(instruments.items())
                    for ii, (instrument, frames) in enumerate(inst_items):
                        count = len(frames)
                        total += count

                        is_last_in_date = (
                            ti == len(target_items) - 1 and
                            fti == len(ft_items) - 1 and
                            ii == len(inst_items) - 1
                        )

                        table.add_row(
                            date if (ti == 0 and fti == 0 and ii == 0) else "",
                            target if (fti == 0 and ii == 0) else "",
                            frame_type if ii == 0 else "",
                            instrument,
                            str(count),
                            end_section=is_last_in_date,
                        )

                is_last_target = ti == len(target_items) - 1
                if not is_last_target:
                    table.add_row("", "", "", "", "")

    # total row
    table.add_row("", "", "", "[bold]Total[/bold]", f"[bold]{total}[/bold]")

    console.print(table)
    logger.info(f"Total frames: {total}")
    return None


def download_frames(classified_frames: dict, output_dir: str, structured: bool = False) -> None:
    """
    Download frames from the classified dict.
    If structured: output_dir/obs_mode/date/target/frame_type/instrument/
    If unstructured: output_dir/obs_mode/
    """

    if not classified_frames:
        logger.warning("No frames to download.")
        return None


    os.makedirs(output_dir, exist_ok=True)

    total_frames = sum(
                        len(frames)
                        for dates in classified_frames.values()
                        for targets in dates.values()
                        for frame_types in targets.values()
                        for instruments in frame_types.values()
                        for frames in instruments.values()
                    )

    download_count = 0
    skip_count = 0

    for obs_mode, dates in classified_frames.items():
        for date, targets in dates.items():
            for target, frame_types in targets.items():
                for frame_type, instruments in frame_types.items():
                    for instrument, frames in instruments.items():

                        if structured:
                            dir_path = os.path.join(output_dir, obs_mode, date, target, frame_type, instrument)
                        else:
                            dir_path = os.path.join(output_dir, obs_mode)

                        os.makedirs(dir_path, exist_ok=True)

                        for n, frame in enumerate(frames):
                            url = frame["url"]
                            filename = frame["filename"]
                            out_path = os.path.join(dir_path, filename)

                            if os.path.exists(out_path):
                                logger.warning(f"File {filename} already exists, skipping.")
                                skip_count += 1
                                continue

                            download_count += 1
                            logger.info(f"Downloading [{download_count}/{total_frames}] {filename} -> {out_path}")
                            try:
                                subprocess.run(
                                    ["curl", "-L", "--progress-bar", url, "-o", out_path],
                                    check=True,
                                )
                            except subprocess.CalledProcessError as e:
                                logger.error(f"Error downloading {filename}: {e}")
                                download_count -= 1  # roll back if it failed
                                if os.path.exists(out_path):
                                    os.remove(out_path)

    logger.info(f"Download complete: {download_count} downloaded, {skip_count} skipped.")
    return None



def main():
    t0 = datetime.now()
    parser = argument_parser()
    args = parser.parse_args()

    # authenticate
    _, headers = handshake()

    # query everything
    all_frames = get_frames(args.tstart, args.tend, headers)
    if not all_frames:
        logger.warning("No frames returned from the query.")
        return None

    # expand --obs_modes into instruments and merge with --instruments
    instruments = args.instruments
    if args.obs_modes is not None:
        expanded = set(instruments or [])
        for mode in args.obs_modes:
            expanded.update(OBS_MODES[mode])
        instruments = list(expanded)

    # filter first
    filtered = filter_frames(
        all_frames,
        frame_types=args.frame_types,
        instruments=instruments,
        target_names=args.target_name,
        reduction_level=args.reduction_level,
    )
    if not filtered:
        logger.warning("No frames after filtering.")
        return None

    # classify and show table based on filtered frames
    classified_filtered = classify_frames(filtered)
    print_summary_table(classified_filtered)

    # stop here if query only
    if args.query_only:
        logger.info("Query only mode, skipping download.")
        return None

    if not args.structured and not args.unstructured:
        logger.warning("No download mode specified. Use --structured or --unstructured.")
        return None

    download_frames(classified_filtered, args.output_dir, structured=args.structured)

    tend = datetime.now()
    elapsed = (tend - t0).total_seconds()
    logger.info(f"Total elapsed time: {format_elapsed(elapsed)}")

    return None


if __name__ == "__main__":
    main()