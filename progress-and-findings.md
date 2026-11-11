# ML-KEM DID Gas Project — Progress & Findings

Repo: github.com/chankang-rgb/pqc-gas-project

## Design decisions
- ML-KEM is a KEM (32-byte shared secret), so data is encrypted with KEM-DEM: ML-KEM + AES-256-GCM. Baseline: X25519 + HKDF + AES-256-GCM.
- Library: kyber-py (pure Python, FIPS 203). Timings are NOT representative of C implementations; plan to re-run with liboqs-python.
- Gas fee is driven by on-chain bytes (calldata 4/16, EIP-7623 floor 10/40; EIP-7976 64/64 under discussion), not CPU time → gas computed from key/ciphertext sizes, not regressed from latency.

## Done
1. src/hybrid.py + test_hybrid.py — hybrid encryption works; extra bytes for key delivery: ML-KEM-768 1088 B vs X25519 32 B.
2. src/benchmark.py — 4 schemes × 5 sizes (10KB–1MB) × 200 reps, randomized order (seed 42), 20 warm-up rounds → data/results.csv (4000 rows).
   - Lesson: blocked (non-randomized) order gave non-monotonic medians; randomization fixed it.
3. src/analysis.py — median (quantile) regression; OLS shown for comparison.
   - Lesson: OLS was distorted by 0.5–1.1% outliers (max 116 ms vs ~5.6 ms median), even gave a negative slope.

## Results (user's MacBook, median regression, encrypt)
| Scheme | Fixed cost (ms) | Slope (ms/MB) | vs X25519 |
|---|---|---|---|
| ML-KEM-512 | 2.581 | 0.362 | 17.8× |
| ML-KEM-768 | 3.974 | 0.350 | 27.4× |
| ML-KEM-1024 | 5.596 | 0.358 | 38.6× |
| X25519 | 0.145 | 0.356 | 1× |
- Slopes are practically identical (max difference 0.01 ms/MB); Model 2 p = 0.21 (encrypt), 0.048 (decrypt). Significant ≠ important.
- Fixed cost grows ~1.5 ms (enc) / ~1.8 ms (dec) per +256 lattice dimensions (3 points, descriptive only).
- Conclusion: PQ overhead is a fixed cost dominated by key encapsulation; AES cost per MB is the same for all schemes.

## Next
- Gas model (calldata/storage cost of public keys & ciphertexts, current vs EIP-7976 pricing)
- Plots (matplotlib/seaborn)
- liboqs-python re-run
- README (English)
