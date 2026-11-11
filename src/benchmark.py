"""
ML-KEM vs X25519 hybrid encryption benchmark.
Measures each phase separately for several data sizes and saves results to data/results.csv.
"""
import os
import time
import random
import platform
import pandas as pd
from kyber_py.ml_kem import ML_KEM_512, ML_KEM_768, ML_KEM_1024
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from hybrid import aes_encrypt, aes_decrypt, derive

# ---------------- Experiment settings ----------------
DATA_SIZES_KB = [10, 50, 100, 500, 1024]   # 10KB ~ 1MB
REPEATS = 200                               # trials per (scheme, size)
WARMUP = 20                                 # discarded rounds at start
SEED = 42                                   # fixed seed -> same order every run


# ---------------- Wrap every scheme in the same 3-function shape ----------------
def make_mlkem(kem):
    def keygen():
        return kem.keygen()                       # (public, secret)
    def encaps(pk):
        key, ct = kem.encaps(pk)
        return key, ct                            # (32-byte key, capsule to send)
    def decaps(sk, ct):
        return kem.decaps(sk, ct)
    return keygen, encaps, decaps

def x25519_keygen():
    sk = X25519PrivateKey.generate()
    return sk.public_key(), sk

def x25519_encaps(pk):
    eph = X25519PrivateKey.generate()
    key = derive(eph.exchange(pk))
    return key, eph.public_key().public_bytes_raw()

def x25519_decaps(sk, ct):
    return derive(sk.exchange(X25519PublicKey.from_public_bytes(ct)))

SCHEMES = {
    "ML-KEM-512":  (*make_mlkem(ML_KEM_512),  512),
    "ML-KEM-768":  (*make_mlkem(ML_KEM_768),  768),
    "ML-KEM-1024": (*make_mlkem(ML_KEM_1024), 1024),
    "X25519":      (x25519_keygen, x25519_encaps, x25519_decaps, 0),
}


def ms(t0, t1):
    return (t1 - t0) / 1e6   # nanoseconds -> milliseconds


def run_one(keygen, encaps, decaps, data):
    """One full send/receive round. Returns timings (ms) and sizes (bytes)."""
    t0 = time.perf_counter_ns(); pk, sk = keygen();             t1 = time.perf_counter_ns()
    key, ct = encaps(pk);                                       t2 = time.perf_counter_ns()
    nonce, body, tag = aes_encrypt(key, data);                  t3 = time.perf_counter_ns()
    key2 = decaps(sk, ct);                                      t4 = time.perf_counter_ns()
    out = aes_decrypt(key2, nonce, body, tag);                  t5 = time.perf_counter_ns()
    assert out == data, "decryption failed!"
    pk_len = len(pk) if isinstance(pk, bytes) else 32
    return {
        "keygen_ms": ms(t0, t1),
        "encaps_ms": ms(t1, t2),
        "aes_enc_ms": ms(t2, t3),
        "decaps_ms": ms(t3, t4),
        "aes_dec_ms": ms(t4, t5),
        "public_key_bytes": pk_len,
        "kem_ct_bytes": len(ct),
    }


def main():
    # 1) Make the fake credentials once per size
    datasets = {kb: os.urandom(kb * 1024) for kb in DATA_SIZES_KB}

    # 2) Build every (scheme, size) job, repeated REPEATS times, then SHUFFLE.
    #    Running in random order spreads background noise (other apps,
    #    CPU power states) evenly across all conditions instead of hitting one block.
    jobs = [(name, kb) for name in SCHEMES for kb in DATA_SIZES_KB] * REPEATS
    random.seed(SEED)
    random.shuffle(jobs)

    # 3) Warm-up: run a few rounds of every scheme and throw the results away
    for _ in range(WARMUP):
        for name, (keygen, encaps, decaps, dim) in SCHEMES.items():
            run_one(keygen, encaps, decaps, datasets[DATA_SIZES_KB[0]])

    # 4) Real measurements
    rows = []
    for idx, (name, kb) in enumerate(jobs):
        keygen, encaps, decaps, dim = SCHEMES[name]
        r = run_one(keygen, encaps, decaps, datasets[kb])
        r.update({"scheme": name, "lattice_dim": dim, "data_kb": kb, "run_order": idx})
        rows.append(r)
        if (idx + 1) % 500 == 0:
            print(f"progress: {idx + 1}/{len(jobs)}")

    df = pd.DataFrame(rows)
    df["encrypt_total_ms"] = df["encaps_ms"] + df["aes_enc_ms"]
    df["decrypt_total_ms"] = df["decaps_ms"] + df["aes_dec_ms"]
    df["machine"] = f"{platform.system()} {platform.machine()} / Python {platform.python_version()}"

    os.makedirs("../data", exist_ok=True)
    df.to_csv("../data/results.csv", index=False)
    print(f"\nsaved {len(df)} rows -> data/results.csv\n")

    # quick summary: median per scheme & size
    summary = df.groupby(["scheme", "data_kb"])[["encrypt_total_ms", "decrypt_total_ms"]].median()
    print(summary.round(3))


if __name__ == "__main__":
    main()