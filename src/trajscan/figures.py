"""Figures for the write-up (static PNG, light mode).

Both figures are magnitude heatmaps: one sequential hue (blue, light -> dark),
2px surface gaps between cells, values labelled in text ink, and "n/a" cells
shown as hatched neutral gray with a label, so absence is never color-only.
"""

import matplotlib

matplotlib.use("Agg")

from pathlib import Path  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
NEUTRAL = "#f0efec"
# Reference sequential blue ramp, steps 100 -> 700.
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
SEQUENTIAL = LinearSegmentedColormap.from_list("seq_blue", BLUE_RAMP)


def _heatmap(
    ax: plt.Axes,
    values: np.ndarray,
    labels: list[list[str]],
    row_names: list[str],
    col_names: list[str],
    vmax: float,
) -> None:
    masked = np.ma.masked_invalid(values)
    ax.pcolormesh(masked, cmap=SEQUENTIAL, vmin=0, vmax=vmax, edgecolors=SURFACE, linewidth=2)
    for (r, c), value in np.ndenumerate(values):
        if np.isnan(value):
            ax.add_patch(
                plt.Rectangle(
                    (c, r),
                    1,
                    1,
                    facecolor=NEUTRAL,
                    hatch="///",
                    edgecolor="#c9c8c3",
                    linewidth=0,
                )
            )
            ax.add_patch(plt.Rectangle((c, r), 1, 1, fill=False, edgecolor=SURFACE, linewidth=2))
            color = TEXT_SECONDARY
        else:
            color = "white" if value / vmax > 0.55 else TEXT_PRIMARY
        ax.text(c + 0.5, r + 0.5, labels[r][c], ha="center", va="center", color=color, fontsize=9)
    ax.set_xticks(np.arange(len(col_names)) + 0.5, col_names, color=TEXT_SECONDARY)
    ax.set_yticks(np.arange(len(row_names)) + 0.5, row_names, color=TEXT_SECONDARY)
    ax.invert_yaxis()
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)


def refusal_heatmap(refusals: pd.DataFrame, path: Path) -> None:
    """Personas (sorted by true risk, high first) x pipeline stage refusal rate."""
    df = refusals.reset_index().sort_values(["true_risk", "persona"], ascending=[False, True])
    stages = ["simulator_refused", "target_refused"] + [
        c for c in df.columns if c.startswith("scanner_refused:")
    ]
    values = df[stages].to_numpy(dtype=float)
    stage_names = ["User simulator", "Target"] + [
        "Scanner:\n" + c.split(":", 1)[1].replace("_", " ").replace("@", "\n") for c in stages[2:]
    ]
    labels = [["n/a" if np.isnan(v) else f"{v:.0%}" for v in row] for row in values]
    rows = [
        f"{p} ({r}, {s})"
        for p, r, s in zip(df["persona"], df["true_risk"], df["user_source"], strict=True)
    ]

    fig, ax = plt.subplots(figsize=(5.5 + 1.2 * len(stages), 4.4), facecolor=SURFACE)
    _heatmap(ax, values, labels, rows, stage_names, vmax=1.0)
    ax.set_title(
        "Share of transcripts refused at each stage\n(persona, true risk, user source)",
        loc="left",
        color=TEXT_PRIMARY,
        fontsize=11,
    )
    fig.text(
        0.01,
        0.01,
        "Target: excludes conversations the simulator refused. Scanners: every transcript"
        " that exists, including ones the target refused partway."
        + (" n/a: stage never reached." if np.isnan(values).any() else ""),
        color=TEXT_SECONDARY,
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)


def confusion_heatmap(preds: pd.DataFrame, path: Path, title_suffix: str = "") -> None:
    """True risk x predicted outcome counts, with non-scores as their own columns."""
    scores = ["1", "2", "3", "4", "5"]
    non_scores = ["refused", "no_transcript"] + [
        o for o in ("no_result", "no_answer", "error") if o in set(preds["predicted_risk"])
    ]
    outcomes = scores + non_scores
    table = pd.crosstab(preds["true_risk"], preds["predicted_risk"]).reindex(
        columns=outcomes, fill_value=0
    )
    values = table.to_numpy(dtype=float)
    labels = [[str(int(v)) if v else "" for v in row] for row in values]

    fig, ax = plt.subplots(figsize=(5 + len(non_scores), 3.4), facecolor=SURFACE)
    names = {
        "refused": "Scanner\nrefused",
        "no_transcript": "No\ntranscript",
        "no_result": "No\nresult",
        "no_answer": "No valid\nanswer",
        "error": "Error",
    }
    col_names = scores + [names[o] for o in non_scores]
    _heatmap(ax, values, labels, [str(r) for r in table.index], col_names, vmax=values.max())
    ax.axvline(5, color=TEXT_SECONDARY, linewidth=1)  # scores | non-scores
    ax.set_xlabel("Predicted risk / outcome", color=TEXT_SECONDARY)
    ax.set_ylabel("True risk", color=TEXT_SECONDARY)
    ax.set_title(
        "Scanner outcomes by true risk (transcript counts)"
        + (f": {title_suffix.replace('_', ' ')}" if title_suffix else ""),
        loc="left",
        color=TEXT_PRIMARY,
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)


# Categorical slots 1-2 of the reference palette (validated: CVD and contrast pass).
SERIES = {"whole_transcript": ("#2a78d6", "o"), "per_turn": ("#eb6834", "s")}


def cost_curve(metrics: pd.DataFrame, costs: pd.DataFrame, path: Path) -> None:
    """Metric vs. cost per transcript for every scanner@model, one panel per metric.

    Series = scanner (color + marker shape); points are labeled with the model,
    so identity never depends on color alone.
    """
    panels = [
        ("concerning_recall_failsafe", "Concerning recall\n(flagged or refused)"),
        (
            "hard_negative_review_burden",
            "Hard-negative review burden\n(flagged or refused; lower is better)",
        ),
        ("category_macro_f1", "Threat-category macro-F1"),
    ]
    fig, axes = plt.subplots(1, len(panels), figsize=(13, 4.2), facecolor=SURFACE)
    for ax, (metric, label) in zip(axes, panels, strict=True):
        for scanner_key in costs.index:
            scanner, _, model = scanner_key.partition("@")
            if (scanner_key, metric) not in metrics.index:
                continue
            color, marker = SERIES.get(scanner, (TEXT_SECONDARY, "^"))
            row = metrics.loc[(scanner_key, metric)]
            x = costs.loc[scanner_key, "mean_cost_per_transcript"]
            ax.errorbar(
                x,
                row["estimate"],
                yerr=[[row["estimate"] - row["ci_low"]], [row["ci_high"] - row["estimate"]]],
                fmt=marker,
                color=color,
                ecolor=color,
                elinewidth=1,
                capsize=0,
                markersize=8,
                markeredgecolor=SURFACE,
                markeredgewidth=2,
            )
            ax.annotate(
                model.split("/")[-1],
                (x, row["estimate"]),
                xytext=(6, 4),
                textcoords="offset points",
                fontsize=7,
                color=TEXT_SECONDARY,
            )
        ax.set_xscale("log")
        ax.set_ylim(-0.05, 1.05)
        ax.set_title(label, loc="left", color=TEXT_PRIMARY, fontsize=10)
        ax.set_xlabel("Mean scan cost per transcript (USD, log scale)", color=TEXT_SECONDARY)
        ax.grid(color="#e8e7e3", linewidth=0.6)
        ax.set_axisbelow(True)
        ax.tick_params(colors=TEXT_SECONDARY, length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)
    handles = [
        plt.Line2D([], [], marker=m, color=c, linestyle="", markersize=8, label=s.replace("_", " "))
        for s, (c, m) in SERIES.items()
    ]
    fig.legend(handles=handles, loc="upper right", frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
