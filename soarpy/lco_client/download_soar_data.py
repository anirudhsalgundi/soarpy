#filters
#obs mode p,s
#p[cals, science[target]] if target, if not p[cals, science]
#s[cals, science[target], standard] if target, if not s[cals, science, standard]
# if bias and p, download p[cals[bias]]
# if flat and p, download p[cals[flat]]
# if bias and s, download s[cals[bias]]
# if flat and s, download s[cals[flat]]
# if arc and s, download s[cals[arc]]
# if science and p, download p[science[target]] if target, if not p[science]
# if science and s, download s[science[target]] if target, if not s[science]
# if science and p and target, download p[science[target]]
# if science and s and target, download s[science[target]]
# if standard and s, download s[standard]


#!/usr/bin/env python
"""CLI tool for downloading SOAR/Goodman frames from the LCO archive."""

import argparse
import os
import subprocess
import sys
from datetime import datetime

from soarpy import lco_client

from rich.table import Table
from rich.console import Console
from rich import box

console = Console()

# frame types that only exist in spectroscopy
SPECTROSCOPY_ONLY = {"arcs", "standard"}

# what --cals expands to per mode
CALS_EXPANSION = {
    "photometry":    {"bias", "flats"},
    "spectroscopy":  {"bias", "flats", "arcs"},
}

# what --all expands to per mode
ALL_EXPANSION = {
    "photometry":    {"bias", "flats", "science"},
    "spectroscopy":  {"bias", "flats", "arcs", "science", "standard"},
}

VALID_FRAME_TYPES = {"bias", "flats", "arcs", "science", "standard", "cals", "all"}


def parse_frame_types(raw: list[str]) -> set[str]:
    """Parse --frame_type values, supporting both space-separated and comma-separated."""
    frame_types = set()
    for item in raw:
        for part in item.split(","):
            part = part.strip().lower()
            if part:
                frame_types.add(part)
    return frame_types


def validate_args(frame_types: set[str], obs_modes: list[str]):
    """Validate frame_type and obs_mode combinations. Exit on invalid."""
    invalid = frame_types - VALID_FRAME_TYPES
    if invalid:
        console.print(f"[red]Invalid frame type(s): {', '.join(invalid)}[/red]")
        console.print(f"Valid options: {', '.join(sorted(VALID_FRAME_TYPES))}")
        sys.exit(1)

    # check spectroscopy-only types against obs_mode
    if obs_modes == ["photometry"]:
        bad = frame_types & SPECTROSCOPY_ONLY
        if bad:
            console.print(
                f"[red]Invalid combination: {', '.join(bad)} "
                f"only exist in spectroscopy, but --obs_mode is photometry.[/red]"
            )
            sys.exit(1)


def expand_frame_types(frame_types: set[str], mode: str) -> set[str]:
    """Expand 'cals' and 'all' into concrete frame types for a given mode."""
    expanded = set()
    for ft in frame_types:
        if ft == "cals":
            expanded |= CALS_EXPANSION[mode]
        elif ft == "all":
            expanded |= ALL_EXPANSION[mode]
        else:
            expanded.add(ft)
    return expanded


def resolve_frame_types_for_mode(frame_types: set[str], mode: str) -> set[str]:
    """Expand shortcuts and drop frame types that don't apply to this mode."""
    expanded = expand_frame_types(frame_types, mode)
    if mode == "photometry":
        expanded -= SPECTROSCOPY_ONLY
    return expanded


def make_output_dirs(base, obsmode, frame_type, target_name=None):
    """Build and create the output directory path."""
    if frame_type == "science" and target_name:
        path = os.path.join(base, obsmode, "science", target_name)
    elif frame_type == "science":
        path = os.path.join(base, obsmode, "science")
    elif frame_type == "standard":
        path = os.path.join(base, obsmode, "standard")
    else:
        path = os.path.join(base, obsmode, "cals", frame_type)
    os.makedirs(path, exist_ok=True)
    return path


def download_frames(frames, dest):
    """Download a list of frames to dest, skipping files that already exist."""
    for frame in frames:
        url = frame["url"]
        filename = frame.get("filename")
        filepath = os.path.join(dest, filename)

        if os.path.exists(filepath):
            console.print(f"[dim]Skipping (exists): {filename}[/dim]")
            continue

        try:
            subprocess.run(
                ["curl", "-sS", "-o", filepath, url],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            console.print(f"[red]Failed to download {filename}: {e}[/red]")


def print_download_table(download_plan: list[dict], query_only: bool = False):
    """Print a Rich table summarizing the download plan."""
    title = "SOAR Download Query" if query_only else "SOAR Download Plan"
    table = Table(title=title, box=box.ROUNDED, show_header=True, header_style="bold cyan")

    table.add_column("Frame Type",   style="green",   justify="center")
    table.add_column("Target Name(s)", style="yellow", justify="center")
    table.add_column("Obs Mode",     style="magenta", justify="center")
    table.add_column("# Frames",     style="white",   justify="right")

    # group by frame_type, then by obsmode
    from collections import OrderedDict
    grouped = OrderedDict()
    for entry in download_plan:
        ft = entry["frame_type"]
        ft = "standard\n(arc + science)" if ft == "standard" else ft
        mode = entry["obsmode"]
        key = (ft, mode)
        if key not in grouped:
            grouped[key] = {"targets": [], "count": 0}
        if entry["target_name"] != "-":
            grouped[key]["targets"].append(entry["target_name"])
        grouped[key]["count"] += entry["count"]

    prev_ft = None
    for (ft, mode), info in grouped.items():
        if prev_ft is not None and ft != prev_ft:
            table.add_section()

        if info["targets"]:
            # 2 targets per line
            pairs = [info["targets"][i:i+2] for i in range(0, len(info["targets"]), 2)]
            targets = "\n".join(", ".join(pair) for pair in pairs)
        else:
            targets = "-"

        table.add_row(ft, targets, mode, str(info["count"]))
        prev_ft = ft

    console.print(table)

    total = sum(e["count"] for e in download_plan)
    console.print(f"[bold]Total frames:[/bold] {total}")

    if query_only:
        console.print("[yellow]Query-only mode — no files downloaded.[/yellow]")

def fetch_frames_by_type(client, frames, mode, frame_type, tstart, tstop, target_name=None):
    """
    Given a mode and a concrete frame type, return the matching frames.
    Handles the calibration expansion fallback via get_calibration_frames.
    """
    if frame_type == "bias":
        result = client.get_calibration_frames(frames, mode, tstart, tstop)
        return result[0]  # bias is always first

    elif frame_type == "flats":
        result = client.get_calibration_frames(frames, mode, tstart, tstop)
        return result[1]  # flats is always second

    elif frame_type == "arcs":
        # spectroscopy only, arcs is third element
        result = client.get_calibration_frames(frames, mode, tstart, tstop)
        return result[2]

    elif frame_type == "science":
        science = client.get_science_frames(frames, mode)
        if mode == "spectroscopy":
            arcs = client._get_spectroscopic_arc_frames(frames)
        if target_name:
            science = [f for f in science if f.get("target_name") == target_name]
        return science

    #FIXME: for now, standard, will put in both the science and arcs
    elif frame_type == "standard":
        return client._get_standard_star_spectroscopic_frames(frames)

    return []


def run(args):
    client = lco_client.LCOClient()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"soar_download_{timestamp}"

    # determine obs modes
    obs_modes = [args.obs_mode] if args.obs_mode else ["photometry", "spectroscopy"]

    # parse and validate
    frame_types = parse_frame_types(args.frame_type)
    validate_args(frame_types, obs_modes)

    # fetch all frames for the time range once
    frames = client.get_frames(args.tstart, args.tstop)

    download_plan = []

    for mode in obs_modes:
        resolved = resolve_frame_types_for_mode(frame_types, mode)

        for ft in sorted(resolved):
            if ft in ("science", "standard"):
                science = fetch_frames_by_type(client, frames, mode, ft, args.tstart, args.tstop, args.target_name)

                if args.target_name:
                    download_plan.append({"obsmode": mode, "frame_type": ft, "target_name": args.target_name, "count": len(science)})
                    if not args.query_only and science:
                        dest = base if args.unstructured else make_output_dirs(base, mode, ft, args.target_name)
                        download_frames(science, dest)
                else:
                    targets = {}
                    for f in science:
                        tname = f.get("target_name", "unknown")
                        targets.setdefault(tname, []).append(f)

                    for tname, tframes in sorted(targets.items()):
                        download_plan.append({"obsmode": mode, "frame_type": ft, "target_name": tname, "count": len(tframes)})
                        if not args.query_only and tframes:
                            dest = base if args.unstructured else make_output_dirs(base, mode, ft, tname)
                            download_frames(tframes, dest)

            else:
                matched = fetch_frames_by_type(client, frames, mode, ft, args.tstart, args.tstop)
                download_plan.append({"obsmode": mode, "frame_type": ft, "target_name": "-", "count": len(matched)})
                if not args.query_only and matched:
                    dest = base if args.unstructured else make_output_dirs(base, mode, ft)
                    download_frames(matched, dest)

    print_download_table(download_plan, query_only=args.query_only)


def main():
    parser = argparse.ArgumentParser(
        description="Download SOAR/Goodman frames from the LCO archive.",
        epilog=(
            "Examples:\n"
            "  %(prog)s --tstart 2024-06-01T00:00:00 --tstop 2024-06-02T00:00:00 --frame_type cals\n"
            "  %(prog)s --tstart 2024-06-01T00:00:00 --tstop 2024-06-02T00:00:00 --frame_type science --target_name SN2024abc\n"
            "  %(prog)s --tstart 2024-06-01T00:00:00 --tstop 2024-06-02T00:00:00 --frame_type science,cals --obs_mode photometry\n"
            "  %(prog)s --tstart 2024-06-01T00:00:00 --tstop 2024-06-02T00:00:00 --frame_type all --query_only\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--tstart", required=True,
                        help="Start time (ISO format, e.g. 2024-01-01T00:00:00)")
    parser.add_argument("--tstop", required=True,
                        help="Stop time (ISO format, e.g. 2024-01-02T00:00:00)")
    parser.add_argument("--obs_mode", choices=["photometry", "spectroscopy"],
                        help="Restrict to one observing mode (default: both)")
    parser.add_argument("--frame_type", nargs="+", required=True,
                        help="Frame types to download: bias, flats, arcs, science, standard, cals, all "
                             "(comma-separated or space-separated, e.g. --frame_type bias,flats)")
    parser.add_argument("--target_name", type=str,
                        help="Filter science frames to a specific target")
    parser.add_argument("--query_only", action="store_true",
                        help="Print the download table without downloading anything")
    parser.add_argument("--unstructured", action="store_true",
                    help="Download all files into a flat directory (no subdirectories)")

    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()