import logging
import os
from enum import Enum

import requests
from astropy.time import Time
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table
from rich import box

from astropy import units as u


logger = logging.getLogger(__name__)
console = Console()


class Constants:
    LCO_FRAME_URL = 'https://archive-api.lco.global/frames/'
    SOAR_TELESCOPE_ID = '4m0a'
    QUERY_LIMIT = 200
    OBSMODE_INSTRUMENTS = {
    'photometry': {'ghts_blue_imager', 'ghts_red_imager'},
    'spectroscopy': {'ghts_blue', 'ghts_red'} # only GHTS, no triplespec
    }
    REQUIRED_CCD_BINNING = "2x2"


class LCOClient:
    def __init__(self, api_token: str = None):
        self.api_token = api_token or os.getenv("LCO_TOKEN")
        if not self.api_token:
            raise ValueError("LCO API token is required. Pass it directly or set LCO_TOKEN.")

        self.base_url = "https://observe.lco.global/api"
        self.headers = {
            "Authorization": f"Token {self.api_token}",
            "Content-Type": "application/json",
        }

        self._authenticate()

        self.FRAME_FETCHERS = {
            'photometric_bias':   self._get_photometric_bias_frames,
            'photometric_flat':   self._get_photometric_flat_frames,
            'spectroscopic_bias': self._get_spectroscopic_bias_frames,
            'spectroscopic_flat': self._get_spectroscopic_flat_frames,
            # 'spectroscopic_arc':  self._get_spectroscopic_arc_frames,
        }


    def _authenticate(self):
        response = requests.get(
            "https://archive-api.lco.global/profile/",
            headers=self.headers,
        )
        if response.status_code != 200:
            raise ValueError(f"Authentication failed: {response.status_code} - {response.text}")

        username = response.json().get("username", "user")
        logger.info(f"Authenticated successfully as {username}")


    def _create_time_windows(self, start_time: str, end_time: str) -> list[tuple]:
        """
        Split a time range into 1-day windows for paginated queries.
        Times should be ISO format strings (e.g. '2024-01-01T00:00:00').
        """
        try:
            tstart_jd = Time(start_time, format="isot").jd
            tend_jd = Time(end_time, format="isot").jd
        except Exception as e:
            logger.error(f"Error parsing time strings: {e}")
            raise ValueError("Invalid time format. Please provide ISO format strings (e.g. '2024-01-01T00:00:00').")

        if tend_jd > Time.now().jd:
            logger.warning("End time is in the future. Adjusting to current time.")
            tend_jd = Time.now().jd

        logger.info(f"Creating 1-day time windows from {start_time} to {end_time}")

        time_windows = []
        current_jd = tstart_jd
        while current_jd < tend_jd:
            next_jd = min(current_jd + 1, tend_jd)
            time_windows.append((
                Time(current_jd, format="jd").isot,
                Time(next_jd, format="jd").isot,
            ))
            current_jd = next_jd

        return time_windows

    def get_frames(self, tstart: str, tstop: str) -> list[dict]:
        """
        Query the LCO archive for all SOAR frames in the given time range.
        Returns a list of frame metadata dicts.
        """
        time_windows = self._create_time_windows(tstart, tstop)
        all_frames = []

        with console.status(f"[bold grey]Querying SOAR archive from {tstart} to {tstop}") as status:
            for t0, t1 in time_windows:
                status.update(f"Querying {t0} to {t1}")

                params = {
                    'start': t0,
                    'end': t1,
                    'telescope_id': Constants.SOAR_TELESCOPE_ID,
                    'limit': Constants.QUERY_LIMIT,
                }

                current_url = Constants.LCO_FRAME_URL
                frames = []

                while current_url:
                    try:
                        response = requests.get(
                            current_url,
                            headers=self.headers,
                            params=params if current_url == Constants.LCO_FRAME_URL else None,
                            timeout=10,
                        )
                    except requests.exceptions.RequestException as e:
                        logger.error(f"Request error: {e}")
                        break

                    if response.status_code != 200:
                        logger.error(f"HTTP {response.status_code} while fetching frames: {response.text}")
                        break

                    data = response.json()
                    frames.extend(data.get("results", []))
                    current_url = data.get("next")

                all_frames.extend(frames)

        logger.info(f"Retrieved {len(all_frames)} frames for {tstart} to {tstop}.")
        return all_frames


    def _get_photometric_bias_frames(self, frames):
        try:
            return [
                frame for frame in frames
                if frame["instrument_id"].lower() in Constants.OBSMODE_INSTRUMENTS['photometry']
                and frame["proposal_id"] == "calibrate"
                and frame["configuration_type"].lower() == "bias"
            ]
        except KeyError as e:
            logger.error(f"KeyError while filtering photometric bias frames: {e}")
            return []

    def _get_photometric_flat_frames(self, frames):
        try:
            return [
                frame for frame in frames
                if frame["instrument_id"].lower() in Constants.OBSMODE_INSTRUMENTS['photometry']
                and frame["proposal_id"] == "calibrate"
                and frame["configuration_type"].lower() == "lampflat"
            ]
        except KeyError as e:
            logger.error(f"KeyError while filtering photometric flat frames: {e}")
            return []

    def _get_photometric_science_frames(self, frames):
        try:
            return [
                frame for frame in frames
                if frame["instrument_id"].lower() in Constants.OBSMODE_INSTRUMENTS['photometry']
                and frame["proposal_id"] != "calibrate"
                and frame["configuration_type"].lower() == "expose"
            ]
        except KeyError as e:
            logger.error(f"KeyError while filtering photometric science frames: {e}")
            return []

    def _get_standard_star_spectroscopic_frames(self, frames):
        try:
            return [
                frame for frame in frames
                if frame["configuration_type"].lower() == "spectrum"
                and frame["proposal_id"] == "calibrate"
                and frame["RLEVEL"] == 0
            ]
        except KeyError as e:
            logger.error(f"KeyError while filtering standard star spectroscopic frames: {e}")
            return []

    def _get_spectroscopic_arc_frames(self, frames):
        try:
            return [
                frame for frame in frames
                if frame["configuration_type"].lower() == "arc"
                and frame["RLEVEL"] == 0
            ]
        except KeyError as e:
            logger.error(f"KeyError while filtering spectroscopic arc frames: {e}")
            return []

    def _get_spectroscopic_bias_frames(self, frames):
        try:
            return [
                frame for frame in frames
                if frame["configuration_type"].lower() == "bias"
                and frame["RLEVEL"] == 0
                and Constants.REQUIRED_CCD_BINNING in frame["target_name"]
            ]
        except KeyError as e:
            logger.error(f"KeyError while filtering spectroscopic bias frames: {e}")
            return []

    def _get_spectroscopic_flat_frames(self, frames):
        try:
            return [
                frame for frame in frames
                if frame["configuration_type"].lower() == "lampflat"
                and frame["RLEVEL"] == 0
                and Constants.REQUIRED_CCD_BINNING in frame["filename"]
                and "slit" not in frame["filename"]
            ]
        except KeyError as e:
            logger.error(f"KeyError while filtering spectroscopic flat frames: {e}")
            return []

    def _get_spectroscopic_science_frames(self, frames):
        try:
            return [
                frame for frame in frames
                if frame["configuration_type"].lower() == "spectrum"
                and frame["RLEVEL"] == 0
                and frame["proposal_id"] != "calibrate"
            ]
        except KeyError as e:
            logger.error(f"KeyError while filtering spectroscopic science frames: {e}")
            return []

    def _get_lco_reduced_photometry_frames(self, frames):
        try:
            return [
                frame for frame in frames
                if frame["reduction_level"] != 0
                and frame["instrument_id"].lower() in Constants.OBSMODE_INSTRUMENTS['photometry']
            ]
        except KeyError as e:
            logger.error(f"KeyError while filtering LCO reduced photometry frames: {e}")
            return []

    def _get_lco_reduced_spectroscopy_frames(self, frames):
        try:
            return [
                frame for frame in frames
                if frame["reduction_level"] != 0
                and frame["instrument_id"].lower() in Constants.OBSMODE_INSTRUMENTS['spectroscopy']
            ]
        except KeyError as e:
            logger.error(f"KeyError while filtering LCO reduced spectroscopy frames: {e}")
            return []

    def _expand_time_range_until_frames_found(self, tstart, tstop, frame_type, max_days=7):

        if frame_type not in self.FRAME_FETCHERS:
            logger.error(f"Unknown frame_type '{frame_type}'")
            return []

        fetcher = self.FRAME_FETCHERS[frame_type]
        expansion = 1

        while expansion <= max_days:
            logger.info(f"Expanding time range by +/-{expansion} day(s) to search for {frame_type} frames.")
            t0 = (Time(tstart) - expansion * u.day).isot
            t1 = (Time(tstop)  + expansion * u.day).isot

            expanded_frames = self.get_frames(t0, t1)
            found_frames = fetcher(expanded_frames)

            if found_frames:
                logger.info(f"Found {len(found_frames)} {frame_type} frame(s) at +/-{expansion} day(s).")
                return found_frames

            expansion += 1

        logger.warning(f"No {frame_type} frames found within +/-{max_days} days of [{tstart}, {tstop}].")
        return []
            

    def _get_photometric_calibrations(self, frames, tstart, tstop):
        photometric_bias_frames = self._get_photometric_bias_frames(frames)
        photometric_flat_frames = self._get_photometric_flat_frames(frames)

        if not photometric_bias_frames:
            logger.warning("No photometric bias frames found in the given time range.")
            photometric_bias_frames = self._expand_time_range_until_frames_found(tstart, tstop, 'photometric_bias')

        if not photometric_flat_frames:
            logger.warning("No photometric flat frames found in the given time range.")
            photometric_flat_frames = self._expand_time_range_until_frames_found(tstart, tstop, 'photometric_flat')

        return photometric_bias_frames, photometric_flat_frames

    def _get_spectroscopic_calibrations(self, frames, tstart, tstop):
        spectroscopic_arc_frames = self._get_spectroscopic_arc_frames(frames)
        spectroscopic_bias_frames = self._get_spectroscopic_bias_frames(frames)
        spectroscopic_flat_frames = self._get_spectroscopic_flat_frames(frames)

        #FIXME: This is not needed until the mask slip issue is solved.
        # if not arc_frames:
        #     logger.warning("No spectroscopic arc frames found in the given time range.")
        #     spectroscopic_arc_frames = self._expand_time_range_until_frames_found(frames, tstart, tstop, 'spectroscopic_arc')

        if not spectroscopic_bias_frames:
            logger.warning("No spectroscopic bias frames found in the given time range.")
            spectroscopic_bias_frames = self._expand_time_range_until_frames_found(tstart, tstop, 'spectroscopic_bias')

        if not spectroscopic_flat_frames:
            logger.warning("No spectroscopic flat frames found in the given time range.")
            spectroscopic_flat_frames = self._expand_time_range_until_frames_found(tstart, tstop, 'spectroscopic_flat')

        return spectroscopic_bias_frames, spectroscopic_flat_frames, spectroscopic_arc_frames


    def get_science_frames(self, frames, mode):
        if mode == 'photometry':
            return self._get_photometric_science_frames(frames)
        elif mode == 'spectroscopy':
            return self._get_spectroscopic_science_frames(frames)
        else:
            logger.error(f"Unknown mode '{mode}' for getting science frames. Accepted modes are 'photometry' and 'spectroscopy'.")
            return []

    def get_calibration_frames(self, frames, mode, tstart, tstop):
        if mode == 'photometry':
            return self._get_photometric_calibrations(frames, tstart, tstop)
        elif mode == 'spectroscopy':
            return self._get_spectroscopic_calibrations(frames, tstart, tstop)
        else:
            logger.error(f"Unknown mode '{mode}' for getting calibration frames. Accepted modes are 'photometry' and 'spectroscopy'.")
            return []
        

    def get_lco_reduced_frames(self, frames, mode):
        if mode == 'photometry':
            return self._get_lco_reduced_photometry_frames(frames)
        elif mode == 'spectroscopy':
            return self._get_lco_reduced_spectroscopy_frames(frames)
        else:
            logger.error(f"Unknown mode '{mode}' for getting LCO reduced frames.")
            return []