#!/usr/bin/env python3
"""Render publication-quality figures from the checked-in analysis JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

PAPER = "#f6f3e9"
INK = "#183f36"
MUTED = "#64736b"
GRID = "#deded1"
DEMOCRATIC = "#3978a8"
REPUBLICAN = "#d96f59"
OTHER = "#9585a7"
GOLD = "#b58c3c"


def configure() -> None:
    plt.rcParams.update({
        "figure.facecolor": PAPER, "axes.facecolor": PAPER, "savefig.facecolor": PAPER,
        "text.color": INK, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
        "axes.edgecolor": GRID, "font.family": "DejaVu Sans", "font.size": 11,
        "axes.titleweight": "bold", "axes.spines.top": False, "axes.spines.right": False,
        "axes.spines.left": False, "axes.spines.bottom": False, "svg.fonttype": "none",
    })


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def refresh_date(detail: dict) -> str:
    dates = [value["fetched_at"][:10] for value in detail["provenance"]["sources"].values()]
    return max(dates)


def finish(figure, output: Path, name: str, svg: bool) -> None:
    figure.savefig(output / f"{name}.png", dpi=180)
    if svg:
        path = output / f"{name}.svg"
        figure.savefig(path)
        path.write_text("\n".join(line.rstrip() for line in path.read_text(encoding="utf-8").splitlines()) + "\n",
                        encoding="utf-8", newline="\n")
    plt.close(figure)
    print(f"Rendered {output / (name + '.png')}")


def history(index: dict, latest: dict, output: Path, svg: bool) -> None:
    rows = index["congresses"]
    years = np.array([row["start_year"] for row in rows])
    figure, axes = plt.subplots(2, 1, figsize=(14, 8.6), sharex=True)
    figure.subplots_adjust(left=.085, right=.965, top=.76, bottom=.22, hspace=.32)
    figure.text(.085, .935, "E I G E N P O L I T I C S   /   H I S T O R I C A L  A T L A S",
                fontsize=10, weight="bold", color=MUTED)
    figure.text(.085, .875, "The Senate's spectral history", fontsize=29, fontfamily="DejaVu Serif")
    figure.text(.085, .83, f"{len(rows)} Congresses  ·  {years[0]}–{latest['last_vote_date'][:4]}"
                "  ·  Networks derived from recorded roll-call votes", fontsize=12, color=MUTED)
    series = [
        ("fiedler_value", INK, "Normalized Laplacian Fiedler value  λ₂", "Lower values indicate a stronger graph bottleneck."),
        ("sweep_conductance", GOLD, "Fiedler-sweep conductance", "Best cut in one spectral ordering; an upper bound on the true minimum."),
    ]
    for axis, (key, color, label, note) in zip(axes, series):
        values = np.array([row[key] for row in rows])
        axis.plot(years, values, color=color, linewidth=2, zorder=3)
        axis.scatter(years, values, s=8, color=color, alpha=.65, zorder=4)
        axis.scatter([years[-1]], [values[-1]], s=62, color=REPUBLICAN, zorder=5,
                     edgecolor=PAPER, linewidth=1.6)
        axis.set_ylim(bottom=0, top=max(values) * 1.18)
        axis.set_xlim(years[0] - 2, years[-1] + 7)
        axis.grid(axis="y", color=GRID, linewidth=.8, zorder=0)
        axis.tick_params(length=0, pad=8)
        axis.set_title(label, loc="left", fontsize=12, pad=13)
        axis.text(1, 1.075, f"Latest  {values[-1]:.3f}", transform=axis.transAxes,
                  ha="right", fontsize=12, color=color, weight="bold")
        axis.text(.01, .08, note, transform=axis.transAxes, fontsize=9, color=MUTED,
                  bbox={"facecolor": PAPER, "edgecolor": "none", "alpha": .9})
        for year in (1861, 1995):
            axis.axvline(year, color=MUTED, alpha=.3, linestyle=(0, (3, 4)), linewidth=.9)
    axes[0].text(1863, axes[0].get_ylim()[1] * .86, "37th Congress\n1861–1863", color=MUTED, fontsize=9)
    axes[0].text(1993, axes[0].get_ylim()[1] * .86, "104th Congress\n1995–1997", color=MUTED, fontsize=9, ha="right")
    axes[1].set_xticks([1789, 1825, 1861, 1900, 1935, 1979, 2025])
    axes[1].set_xlabel("Congress start year", labelpad=12)
    figure.text(.085, .085, "METHOD  Pearson similarity (r + 1) / 2; no self-loops; nonparticipation encoded as 0."
                "\nSOURCE  Voteview · voteview.com/data"
                f"  |  Fetched {refresh_date(latest)}  |  Latest recorded vote {latest['last_vote_date']}",
                fontsize=9, linespacing=1.65, color=MUTED)
    figure.text(.965, .085, f"Methodology v{index['methodology_version']}\nCorrected research implementation",
                ha="right", fontsize=9, linespacing=1.65, color=MUTED)
    finish(figure, output, "spectral-history", svg)


def comparison(left: dict, right: dict, output: Path, svg: bool, bounds: dict) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(14, 8.6), sharex=True, sharey=True)
    figure.subplots_adjust(left=.085, right=.965, top=.74, bottom=.29, wspace=.14)
    figure.text(.085, .935, "E I G E N P O L I T I C S   /   A L I G N E D  S P E C T R A L  G E O M E T R Y",
                fontsize=10, weight="bold", color=MUTED)
    figure.text(.085, .875, "Two Senates, one aligned spectral frame", fontsize=26, fontfamily="DejaVu Serif")
    figure.text(.085, .83, "Each dot represents one included senator. Color identifies recorded party affiliation.",
                fontsize=12, color=MUTED)
    xlim, ylim = bounds["x"], bounds["y"]
    for axis, detail in zip(axes, (left, right)):
        axis.axhline(0, color=GRID, linewidth=1)
        axis.axvline(0, color=GRID, linewidth=1)
        for node in detail["nodes"]:
            color = DEMOCRATIC if node["party_code"] == 100 else REPUBLICAN if node["party_code"] == 200 else OTHER
            axis.scatter(node["aligned_x"], node["aligned_y"], s=43, color=color, alpha=.8, edgecolor=PAPER, linewidth=.6, zorder=3)
        axis.set_title(f"{detail['congress']}th Congress  ·  {detail['start_year']}–{detail['end_year']}",
                       loc="left", pad=28, fontsize=15, fontfamily="DejaVu Serif")
        axis.text(0, 1.025, f"{detail['members']} senators  /  {detail['rollcalls']:,} roll calls"
                  f"  /  λ₂ {detail['fiedler_value']:.3f}", transform=axis.transAxes, fontsize=10, color=MUTED)
        axis.set_xlim(*xlim)
        axis.set_ylim(*ylim)
        axis.set_xlabel("Aligned spectral axis 1", labelpad=10)
        axis.tick_params(length=0, pad=7, labelsize=9)
        axis.grid(color=GRID, linewidth=.5, alpha=.55)
    axes[0].set_ylabel("Aligned spectral axis 2", labelpad=10)
    handles = [Line2D([], [], color=color, marker="o", linestyle="none", markersize=7, label=label)
               for color, label in [(DEMOCRATIC, "Democratic"), (REPUBLICAN, "Republican"), (OTHER, "Other / Independent")]]
    figure.legend(handles=handles, loc="lower left", bbox_to_anchor=(.079, .188),
                  ncol=3, frameon=False, fontsize=10, columnspacing=2)
    linked = left["alignment"]["segment_id"] == right["alignment"]["segment_id"]
    alignment_note = ("Shared senators link consecutive Congresses by rigid Procrustes; no rescaling."
                      if linked else "These Congresses are in separate alignment segments; coordinates are not linked.")
    quality = right["alignment"]
    fit_note = (f"Latest link: {quality['anchor_count']} anchors; relative residual {quality['relative_residual']:.3f}"
                f" ({quality['quality']})." if quality["relative_residual"] is not None else quality["reason"])
    figure.text(.085, .145, f"ALIGNMENT  {alignment_note}\n"
                f"Relative structure, not absolute policy movement. {fit_note}",
                fontsize=9.3, color=INK, linespacing=1.7)
    figure.text(.085, .065, "SOURCE  Voteview · voteview.com/data"
                f"  |  Fetched {refresh_date(right)}  |  Latest recorded vote {right['last_vote_date']}"
                f"\nMETHOD  Zero-diagonal Pearson-similarity graph; symmetric normalized Laplacian; methodology v{right['methodology_version']}.",
                fontsize=9, color=MUTED, linespacing=1.65)
    finish(figure, output, "spectral-comparison", svg)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--data-dir", type=Path, default=root / "site/data")
    command.add_argument("--output", type=Path, default=root / "docs/images")
    command.add_argument("--compare", nargs=2, type=int, default=[96, 119], metavar=("EARLIER", "LATER"))
    command.add_argument("--svg", action="store_true", help="Also save editable vector SVG files.")
    args = command.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    configure()
    index = read_json(args.data_dir / "index.json")
    latest = read_json(args.data_dir / index["congresses"][-1]["data_file"])
    history(index, latest, args.output, args.svg)
    selected = [read_json(args.data_dir / "congresses" / f"{number}.json") for number in args.compare]
    comparison(*selected, args.output, args.svg, index["aligned_axis_bounds"])


if __name__ == "__main__":
    main()
