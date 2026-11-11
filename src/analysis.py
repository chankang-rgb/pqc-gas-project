"""
Regression analysis of benchmark results.

Timing data has a heavy right tail: most runs are fast, but a few runs get
interrupted by the OS and take 5-10x longer. Ordinary least squares (OLS)
fits the MEAN, so those rare spikes drag the line around.
We therefore use MEDIAN (quantile, q=0.5) regression as the main model,
and report OLS only for comparison.

Model 1 (per scheme):   median time = b0 + b1 * data_kb
    b0 = fixed cost (key exchange: ML-KEM or X25519)
    b1 = marginal cost per KB (AES-GCM)
Model 2 (all schemes):  does the per-KB slope differ between schemes?
Model 3 (ML-KEM only):  fixed cost vs lattice dimension
"""
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

df = pd.read_csv("../data/results.csv")
TARGETS = ["encrypt_total_ms", "decrypt_total_ms"]
pd.set_option("display.width", 200)

# ---------------- Step 0: look at the outliers first ----------------
print("=== Step 0: outlier check (runs slower than 3x the median of their group) ===")
for target in TARGETS:
    med = df.groupby(["scheme", "data_kb"])[target].transform("median")
    df[f"{target}_outlier"] = df[target] > 3 * med
out = df.groupby("scheme")[[f"{t}_outlier" for t in TARGETS]].mean() * 100
out.columns = ["encrypt_outlier_%", "decrypt_outlier_%"]
print(out.round(2))
print("max encrypt time (ms):", df.groupby("scheme")["encrypt_total_ms"].max().round(1).to_dict())

# ---------------- Model 1: median regression per scheme ----------------
rows = []
for target in TARGETS:
    for scheme, g in df.groupby("scheme"):
        q = smf.quantreg(f"{target} ~ data_kb", data=g).fit(q=0.5)
        o = smf.ols(f"{target} ~ data_kb", data=g).fit(cov_type="HC3")
        ci = q.conf_int()
        rows.append({
            "target": target,
            "scheme": scheme,
            "lattice_dim": g["lattice_dim"].iloc[0],
            "fixed_cost_ms": q.params["Intercept"],
            "fixed_ci_low": ci.loc["Intercept", 0],
            "fixed_ci_high": ci.loc["Intercept", 1],
            "slope_ms_per_MB": q.params["data_kb"] * 1024,
            "slope_ci_low": ci.loc["data_kb", 0] * 1024,
            "slope_ci_high": ci.loc["data_kb", 1] * 1024,
            "ols_fixed_cost_ms": o.params["Intercept"],      # for comparison only
            "ols_slope_ms_per_MB": o.params["data_kb"] * 1024,
            "n": int(q.nobs),
        })
summary = pd.DataFrame(rows)
base = summary[summary.scheme == "X25519"].set_index("target")["fixed_cost_ms"]
summary["fixed_cost_vs_x25519"] = summary.apply(lambda r: r.fixed_cost_ms / base[r.target], axis=1)
summary.to_csv("../data/regression_summary.csv", index=False)

print("\n=== Model 1: median regression, time = fixed cost + slope * size ===")
print(summary[["target", "scheme", "fixed_cost_ms", "fixed_ci_low", "fixed_ci_high",
               "slope_ms_per_MB", "slope_ci_low", "slope_ci_high",
               "fixed_cost_vs_x25519"]].round(3).to_string(index=False))
print("\n(OLS for comparison - pulled around by outliers)")
print(summary[["target", "scheme", "ols_fixed_cost_ms", "ols_slope_ms_per_MB"]]
      .round(3).to_string(index=False))

# ---------------- Model 2: are the slopes the same? ----------------
print("\n=== Model 2: does the per-KB slope depend on the scheme? (median regression) ===")
for target in TARGETS:
    full = smf.quantreg(f"{target} ~ data_kb * C(scheme)", data=df).fit(q=0.5)
    names = list(full.params.index)
    inter = [i for i, n in enumerate(names) if n.startswith("data_kb:")]
    R = np.zeros((len(inter), len(names)))
    for row, col in enumerate(inter):
        R[row, col] = 1
    test = full.f_test(R)
    p = float(test.pvalue)
    print(f"{target}: F = {float(np.squeeze(test.fvalue)):.2f}, p = {p:.4g}")
s = summary[summary.target == "encrypt_total_ms"]
fixed_gap = s.fixed_cost_ms.max() - s.fixed_cost_ms.min()
slope_gap = s.slope_ms_per_MB.max() - s.slope_ms_per_MB.min()
print(f"effect size: fixed costs differ by up to {fixed_gap:.2f} ms, "
      f"slopes differ by up to {slope_gap:.2f} ms per MB")

# ---------------- Model 3: fixed cost vs lattice dimension ----------------
print("\n=== Model 3: ML-KEM fixed cost vs lattice dimension ===")
mlkem = summary[summary.scheme != "X25519"]
for target in TARGETS:
    t = mlkem[mlkem.target == target]
    m = smf.ols("fixed_cost_ms ~ lattice_dim", data=t).fit()
    print(f"{target}: +{m.params['lattice_dim'] * 256:.3f} ms per +256 dimensions "
          f"(R^2 = {m.rsquared:.3f}, only 3 points -> descriptive only)")