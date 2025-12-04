#!/usr/bin/env python3
"""
Generate GrADS-friendly 'set rgb' lines from matplotlib colormaps.

Usage as a module:
    from grads_colours import make_grads_rgb_from_cmap, make_grads_rgb_from_colors

Usage as a script:
    # From a matplotlib colormap name
    python grads_colours.py --n 10 --cmap RdBu_r

    # From explicit colours
    python grads_colours.py --n 15 --colors blue white red --start 50

    # With a PNG preview of the colourbar (labels every 2nd colour index)
    python grads_colours.py --n 55 --cmap RdBu_r --start 71 \
        --png rdBu_55_71-125.png --tick-step 2
"""

import argparse
from typing import List, Sequence

import matplotlib
from matplotlib import cm
from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm
from matplotlib.cm import ScalarMappable


def _colormap_to_grads_lines(cmap, n: int, start_index: int = 16) -> List[str]:
    """
    Sample `n` colours from a matplotlib colormap and return GrADS 'set rgb' lines.
    """
    # Force quantised colormap with n discrete levels
    if getattr(cmap, "N", None) != n:
        cmap = cmap.__class__.from_list(
            getattr(cmap, "name", "tmp"),
            [cmap(i / (n - 1)) for i in range(n)],
            N=n,
        )

    lines = []
    for i in range(n):
        r, g, b, *_ = cmap(i)  # ignore alpha if present
        R, G, B = (int(round(255 * x)) for x in (r, g, b))
        idx = start_index + i
        lines.append(f"set rgb {idx} {R:3d} {G:3d} {B:3d}")
    return lines


def make_grads_rgb_from_cmap(
    n: int,
    cmap_name: str = "viridis",
    start_index: int = 16,
) -> List[str]:
    """
    Create GrADS 'set rgb' lines from a matplotlib built-in colormap.

    Parameters
    ----------
    n : int
        Number of discrete colours to generate.
    cmap_name : str
        Name of the matplotlib colormap (e.g. 'RdBu_r', 'viridis', 'coolwarm').
    start_index : int
        First GrADS colour index to use (0–255). GrADS often uses 0–15 internally,
        so 16 is a common safe starting point.

    Returns
    -------
    List[str]
        Lines like 'set rgb 16 255 255 255'.
    """
    cmap = cm.get_cmap(cmap_name, n)
    return _colormap_to_grads_lines(cmap, n, start_index=start_index)


def make_grads_rgb_from_colors(
    n: int,
    colors: Sequence[str],
    start_index: int = 16,
    name: str = "custom",
) -> List[str]:
    """
    Create GrADS 'set rgb' lines from a list of colours spanning the range.

    Parameters
    ----------
    n : int
        Number of discrete colours to generate.
    colors : sequence of str
        Colours understood by matplotlib (e.g. 'blue', '#ffffff', '0.2', etc.).
        They are used as control points in a LinearSegmentedColormap.
    start_index : int
        First GrADS colour index to use.
    name : str
        Name of the generated colormap (only for identification).

    Returns
    -------
    List[str]
        Lines like 'set rgb 37 255 224 208'.
    """
    cmap = LinearSegmentedColormap.from_list(name, list(colors), N=n)
    return _colormap_to_grads_lines(cmap, n, start_index=start_index)


def _save_colourbar_png(
    cmap,
    n: int,
    start_index: int,
    filename: str,
    tick_step: int = 1,
    figsize=(6.0, 0.6),
) -> None:
    """
    Save a discrete horizontal colourbar as a PNG.

    Tick labels are the GrADS colour indices (start_index ... start_index + n - 1).
    tick_step controls labelling density (e.g. 2 = every other index).
    """
    import numpy as np
    import matplotlib.pyplot as plt

    # Ensure we have a discrete colormap consistent with _colormap_to_grads_lines
    if getattr(cmap, "N", None) != n:
        cmap = cmap.__class__.from_list(
            getattr(cmap, "name", "tmp"),
            [cmap(i / (n - 1)) for i in range(n)],
            N=n,
        )

    # n discrete bands: [0, 1, ..., n]
    boundaries = np.linspace(0, n, n + 1)
    norm = BoundaryNorm(boundaries, n)

    # Tick positions at band centres and labels as GrADS indices
    all_positions = np.arange(n) + 0.5
    all_labels = [str(start_index + i) for i in range(n)]

    positions = all_positions[::max(tick_step, 1)]
    labels = all_labels[::max(tick_step, 1)]

    fig, ax = plt.subplots(figsize=figsize)
    fig.subplots_adjust(bottom=0.5, top=0.95, left=0.05, right=0.99)

    cb = fig.colorbar(
        ScalarMappable(norm=norm, cmap=cmap),
        cax=ax,
        orientation="horizontal",
        boundaries=boundaries,
        ticks=positions,
    )
    cb.ax.set_xticklabels(labels)
    cb.ax.tick_params(axis="x", labelsize=6, length=2)
    cb.outline.set_visible(False)

    ax.set_title(
        f"GrADS colour indices {start_index}–{start_index + n - 1}",
        fontsize=8,
        pad=2,
    )

    fig.savefig(filename, dpi=150, bbox_inches="tight")
    plt.close(fig)


def save_colourbar_with_values(
    cmap,
    values,
    filename,
    tick_step=1,
    figsize=(6, 0.7),
):
    """
    Save a discrete colourbar where tick labels appear exactly at the user-
    provided boundary values (e.g., temperature clevs).
    """
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm
    from matplotlib.cm import ScalarMappable

    boundaries = np.array(values, dtype=float)
    n = len(boundaries) - 1  # number of intervals

    norm = BoundaryNorm(boundaries, cmap.N)

    # tick positions *at boundaries* (not midpoints)
    tick_positions = boundaries[::tick_step]
    tick_labels = [f"{v:g}" for v in tick_positions]

    fig, ax = plt.subplots(figsize=figsize)
    fig.subplots_adjust(bottom=0.45, left=0.03, right=0.97, top=0.9)

    cb = fig.colorbar(
        ScalarMappable(norm=norm, cmap=cmap),
        cax=ax,
        orientation="horizontal",
        boundaries=boundaries,
        ticks=tick_positions,
    )

    cb.ax.set_xticklabels(tick_labels, fontsize=6)
    cb.outline.set_visible(False)

    ax.set_title("Temperature (°C)", fontsize=8, pad=2)

    fig.savefig(filename, dpi=150, bbox_inches="tight")
    plt.close(fig)


def save_colourbar_from_colors(
    n: int,
    colors: Sequence[str],
    start_index: int,
    filename: str,
    tick_step: int = 1,
    name: str = "custom",
    figsize=(6.0, 0.6),
) -> None:
    """
    Convenience wrapper: build a colormap from `colors` and save a discrete
    horizontal colourbar as a PNG.

    Parameters
    ----------
    n : int
        Number of discrete colours (same as used for GrADS).
    colors : sequence of str
        Control-point colours (same as make_grads_rgb_from_colors).
    start_index : int
        GrADS colour index for the first colour.
    filename : str
        Output PNG path.
    tick_step : int, optional
        Label every Nth colour index on the colourbar (default: 1).
    name : str, optional
        Name of the colormap.
    figsize : tuple, optional
        Figure size passed to matplotlib.
    """
    cmap = LinearSegmentedColormap.from_list(name, list(colors), N=n)
    _save_colourbar_png(
        cmap=cmap,
        n=n,
        start_index=start_index,
        filename=filename,
        tick_step=tick_step,
        figsize=figsize,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate GrADS 'set rgb' lines from matplotlib colormaps."
    )
    parser.add_argument(
        "--n",
        type=int,
        required=True,
        help="Number of colours to generate.",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=16,
        help="Starting GrADS colour index (default: 16).",
    )
    parser.add_argument(
        "--png",
        type=str,
        default=None,
        help="Optional: path to save a PNG preview of the colourbar.",
    )
    parser.add_argument(
        "--tick-step",
        type=int,
        default=1,
        help="Label every Nth colour index on the PNG colourbar (default: 1).",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--cmap",
        type=str,
        help="Matplotlib colormap name (e.g. 'RdBu_r', 'viridis', 'coolwarm').",
    )
    group.add_argument(
        "--colors",
        nargs="+",
        help="List of colour names or hex codes (e.g. --colors blue white red).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # Build colormap and RGB lines
    if args.cmap:
        cmap = cm.get_cmap(args.cmap, args.n)
        lines = _colormap_to_grads_lines(cmap, args.n, start_index=args.start)
    else:
        cmap = LinearSegmentedColormap.from_list("custom", list(args.colors), N=args.n)
        lines = _colormap_to_grads_lines(cmap, args.n, start_index=args.start)

    # Print GrADS 'set rgb' lines
    for line in lines:
        print(line)

    # Optional PNG preview
    if args.png:
        _save_colourbar_png(
            cmap=cmap,
            n=args.n,
            start_index=args.start,
            filename=args.png,
            tick_step=args.tick_step,
        )


if __name__ == "__main__":
    # Use a non-interactive backend to avoid any display issues when run as a script.
    matplotlib.use("Agg", force=True)
    main()
