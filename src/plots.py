"""
Figures for the README. Run after benchmark.py, analysis.py and gas_model.py.
Saves PNG files into ../figures/.

Color logic (same in every figure):
  ML-KEM-512 / 768 / 1024 -> light -> dark blue (ordered: bigger lattice = darker)
  X25519 (classical baseline) -> orange
"""
import os
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

os.makedirs("../figures", exist_ok=True)

# ---------------- Style ----------------
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
COLORS = {"ML-KEM-512": "#5598e7", "ML-KEM-768": "#256abf",
          "ML-KEM-1024": "#0d366b", "X25519": "#eb6834"}
MLKEM = ["ML-KEM-512", "ML-KEM-768", "ML-KEM-1024"]
ORDER = MLKEM + ["X25519"]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK_2, "text.color": INK,
    "xtick.color": INK_2, "ytick.color": INK_2, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "legend.frameon": False,
})
KB_TICKS = [10, 50, 100, 500, 1024]
kb_fmt = FuncFormatter(lambda v, _: f"{int(v)}")


def size_axis(ax):
    ax.set_xscale("log")
    ax.set_xticks(KB_TICKS)
    ax.xaxis.set_major_formatter(kb_fmt)
    ax.xaxis.set_minor_formatter(FuncFormatter(lambda v, _: ""))
    ax.set_xlabel("Credential size (KB, log scale)")


def label_end(ax, x, y, text, color):
    ax.annotate(text, (x, y), xytext=(6, 0), textcoords="offset points",
                va="center", fontsize=9, color=INK, fontweight="bold")
    ax.plot([], [])  # keeps color cycle untouched


def save(fig, name):
    fig.savefig(f"../figures/{name}", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("saved figures/" + name)


timing = pd.read_csv("../data/results.csv")
reg = pd.read_csv("../data/regression_summary.csv")
gas = pd.read_csv("../data/gas_results.csv")

# =====================================================================
# Figure 1 - latency vs credential size (median + interquartile band)
# =====================================================================
fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
for ax, col, title in zip(axes, ["encrypt_total_ms", "decrypt_total_ms"],
                          ["Encryption (encapsulate + AES-GCM)",
                           "Decryption (decapsulate + AES-GCM)"]):
    q = timing.groupby(["scheme", "data_kb"])[col].quantile([0.25, 0.5, 0.75]).unstack()
    for s in ORDER:
        d = q.loc[s]
        ax.fill_between(d.index, d[0.25], d[0.75], color=COLORS[s], alpha=0.15, lw=0)
        ax.plot(d.index, d[0.5], color=COLORS[s], lw=2, marker="o", ms=5.5,
                markeredgecolor=SURFACE, markeredgewidth=1.5, label=s)
        label_end(ax, d.index[-1], d[0.5].iloc[-1], s, COLORS[s])
    size_axis(ax)
    ax.set_xlim(8, 4000)
    ax.set_title(title)
axes[0].set_ylabel("Median time (ms)")
axes[0].set_ylim(bottom=0)
fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=4,
           fontsize=9, bbox_to_anchor=(0.5, -0.1))
fig.suptitle("ML-KEM cost is almost flat in data size: it is a fixed key-exchange cost",
             x=0.01, ha="left", fontsize=12, fontweight="bold")
fig.text(0.01, -0.16, "Lines: median of 200 runs. Bands: 25th-75th percentile. "
         "Pure-Python ML-KEM (kyber-py); absolute times are higher than in C.",
         fontsize=8.5, color=INK_2)
save(fig, "fig1_latency_vs_size.png")

# =====================================================================
# Figure 2 - fixed cost (regression intercept) vs lattice dimension
# =====================================================================
fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
for ax, target, title in zip(axes, ["encrypt_total_ms", "decrypt_total_ms"],
                             ["Encryption", "Decryption"]):
    r = reg[reg.target == target].set_index("scheme")
    xs = [r.loc[s, "lattice_dim"] for s in MLKEM]
    ys = [r.loc[s, "fixed_cost_ms"] for s in MLKEM]
    ax.plot(xs, ys, color=GRID, lw=2, zorder=1)
    for s in MLKEM:
        lo, hi, y = r.loc[s, ["fixed_ci_low", "fixed_ci_high", "fixed_cost_ms"]]
        ax.errorbar(r.loc[s, "lattice_dim"], y, yerr=[[y - lo], [hi - y]], fmt="o",
                    color=COLORS[s], ms=8, capsize=4, elinewidth=1.5,
                    markeredgecolor=SURFACE, markeredgewidth=1.5, zorder=3)
        ax.annotate(f"{y:.2f} ms", (r.loc[s, "lattice_dim"], y), xytext=(10, -4),
                    textcoords="offset points", fontsize=9, color=INK)
    base = r.loc["X25519", "fixed_cost_ms"]
    ax.axhline(base, color=COLORS["X25519"], lw=2, ls="--")
    ax.annotate(f"X25519 baseline: {base:.2f} ms", (512, base), xytext=(0, 6),
                textcoords="offset points", fontsize=9, color=INK)
    ax.set_xticks([512, 768, 1024])
    ax.set_xticklabels(["512\n(ML-KEM-512)", "768\n(ML-KEM-768)", "1024\n(ML-KEM-1024)"])
    ax.set_xlim(420, 1150)
    ax.set_xlabel("Lattice dimension (k x 256)")
    ax.set_title(title)
axes[0].set_ylabel("Fixed cost = regression intercept (ms)")
axes[0].set_ylim(bottom=0)
fig.suptitle("Fixed cost grows linearly with lattice dimension",
             x=0.01, ha="left", fontsize=12, fontweight="bold")
fig.text(0.01, -0.1, "Median (quantile) regression: time = fixed cost + slope x size. "
         "95% confidence intervals are drawn but are narrower than the markers.", fontsize=8.5, color=INK_2)
save(fig, "fig2_fixed_cost_vs_dimension.png")

# =====================================================================
# Figure 3 - gas increase vs X25519 per DID scenario
# =====================================================================
groups = [("A. register key", "current (EIP-7623)", "A. Store public key\nin contract storage"),
          ("B. key exchange (data off-chain)", "current (EIP-7623)",
           "B. Key exchange message\n(current pricing, EIP-7623)"),
          ("B. key exchange (data off-chain)", "proposed (EIP-7976)",
           "B. Key exchange message\n(proposed pricing, EIP-7976)")]
fig, ax = plt.subplots(figsize=(10, 4.6))
bar_h, gap = 0.24, 0.03
for gi, (scen, rule, label) in enumerate(groups):
    for si, s in enumerate(MLKEM):
        v = gas[(gas.scenario == scen) & (gas.rule == rule) & (gas.scheme == s)][
            "increase_vs_x25519_%"].iloc[0]
        y = gi - (si - 1) * (bar_h + gap)
        ax.barh(y, v, height=bar_h, color=COLORS[s], label=s if gi == 0 else None)
        ax.annotate(f"+{v:,.0f}%", (v, y), xytext=(5, 0), textcoords="offset points",
                    va="center", fontsize=9, color=INK)
ax.set_yticks(range(len(groups)))
ax.set_yticklabels([g[2] for g in groups])
ax.invert_yaxis()
ax.grid(axis="y", visible=False)
ax.set_xlabel("Gas increase vs X25519 (%)")
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}%"))
ax.set_xlim(0, 1800)
ax.legend(loc="lower right", fontsize=9)
ax.set_title("On-chain cost depends on design: storing ML-KEM keys costs up to 16x more gas",
             fontsize=12)
fig.text(0.01, -0.03, "X25519 = 0%. Gas computed from standardized key/ciphertext sizes; "
         "percentages do not depend on gas price or ETH price.", fontsize=8.5, color=INK_2)
save(fig, "fig3_gas_increase_by_scenario.png")

# =====================================================================
# Figure 4 - relative overhead shrinks as the credential grows
#   (two measures, two panels - never one chart with two y-axes)
# =====================================================================
fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
med = timing.groupby(["scheme", "data_kb"])["encrypt_total_ms"].median().unstack(0)
ax = axes[0]
for s in MLKEM:
    over = (med[s] / med["X25519"] - 1) * 100
    ax.plot(over.index, over.values, color=COLORS[s], lw=2, marker="o", ms=5.5,
            markeredgecolor=SURFACE, markeredgewidth=1.5, label=s)
    label_end(ax, over.index[-1], over.values[-1], s, COLORS[s])
size_axis(ax)
ax.set_xlim(8, 4000)
ax.set_ylim(bottom=0)
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}%"))
ax.set_ylabel("Extra encryption time vs X25519")
ax.set_title("Computation (median time)")

ax = axes[1]
c = gas[(gas.scenario == "C. full credential on-chain") & (gas.rule == "current (EIP-7623)")]
# smallest credential that no longer fits in one tx (floor pricing: ~40 gas per byte)
cap_kb = (2**24 - 21_000) / 40 / 1024
ax.axvspan(cap_kb, 1400, color=GRID, alpha=0.6, lw=0)
ax.text((cap_kb * 1400) ** 0.5, 0.97, f"Does not fit in one\ntransaction (> ~{cap_kb:.0f} KB,\nEIP-7825 gas cap)", transform=ax.get_xaxis_transform(),
        ha="center", va="top", fontsize=8.5, color=INK_2)
for s in MLKEM:
    d = c[c.scheme == s].set_index("data_kb")
    ax.plot(d.index, d["increase_vs_x25519_%"], color=COLORS[s], lw=2, label=s)
    ok = d[d.fits_one_tx]
    bad = d[~d.fits_one_tx]
    ax.plot(ok.index, ok["increase_vs_x25519_%"], "o", color=COLORS[s], ms=5.5,
            markeredgecolor=SURFACE, markeredgewidth=1.5)
    ax.plot(bad.index, bad["increase_vs_x25519_%"], "o", ms=6,
            markerfacecolor=SURFACE, markeredgecolor=COLORS[s], markeredgewidth=1.5)
size_axis(ax)
ax.set_xlim(8, 1400)
ax.set_ylim(bottom=0)
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
ax.set_ylabel("Extra gas vs X25519")
ax.set_title("On-chain cost (scenario C: whole credential on-chain)")
ax.legend(loc="center right", fontsize=9)
fig.suptitle("The bigger the credential, the smaller the relative post-quantum overhead",
             x=0.01, ha="left", fontsize=12, fontweight="bold")
save(fig, "fig4_relative_overhead_vs_size.png")
