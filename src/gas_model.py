"""
Ethereum gas model: how much more does a DID transaction cost
if X25519 keys are replaced with ML-KEM keys?

Gas on Ethereum is charged for BYTES and STATE, not for CPU time.
So this model uses the real sizes of keys / ciphertexts, not the timings.

Pricing rules implemented (gas used per transaction):
  tokens       = zero_bytes + 4 * nonzero_bytes
  standard     = 4 * tokens + execution_gas            (4 / 16 gas per byte)
  CURRENT      (Pectra EIP-7623, live since 2025):
      floor    = 10 * tokens                           (10 / 40 gas per byte)
  PROPOSED     (Glamsterdam EIP-7976, not yet live):
      floor    = 16 * 4 * (zero_bytes + nonzero_bytes) (64 / 64 gas per byte)
  gas_used     = 21000 + max(standard, floor)
  Per-transaction cap (Fusaka EIP-7825): 16,777,216 gas.

Execution gas is a simplified estimate (see constants below) - the goal is a
fair comparison between X25519 and ML-KEM, not an exact contract audit.
"""
import math
import random
import pandas as pd

# ---------------- Sizes (bytes) from the standards ----------------
SCHEMES = {
    #               public key, ciphertext / ephemeral key
    "X25519":      (32,   32),
    "ML-KEM-512":  (800,  768),
    "ML-KEM-768":  (1184, 1088),
    "ML-KEM-1024": (1568, 1568),
}
DATA_SIZES_KB = [10, 50, 100, 500, 1024]

# ---------------- Gas constants ----------------
TX_BASE = 21_000
TX_GAS_CAP = 2**24                # EIP-7825 (Fusaka)
SSTORE_NEW_SLOT = 20_000 + 2_100  # zero -> non-zero write + cold slot access (EIP-2929)
LOG_BASE, LOG_TOPIC, LOG_BYTE = 375, 375, 8
CALL_OVERHEAD = 5_000             # ASSUMPTION: dispatch, ABI decoding, checks
NONCE_TAG = 12 + 16               # AES-GCM nonce + tag
POINTER = 34                      # IPFS CIDv0 (sha256 multihash) of the off-chain credential

rng = random.Random(42)           # reproducible "random" bytes


def abi_bytes_arg(payload: bytes) -> bytes:
    """Calldata for f(bytes): selector + offset + length + payload padded to 32."""
    pad = (-len(payload)) % 32
    return (rng.randbytes(4)
            + (32).to_bytes(32, "big")
            + len(payload).to_bytes(32, "big")
            + payload + b"\x00" * pad)


def memory_cost(n_bytes: int) -> int:
    words = math.ceil(n_bytes / 32)
    return 3 * words + words * words // 512


def tx_gas(calldata: bytes, execution_gas: int, rule: str) -> int:
    zeros = calldata.count(0)
    nonzeros = len(calldata) - zeros
    tokens = zeros + 4 * nonzeros
    standard = 4 * tokens + execution_gas
    if rule == "current (EIP-7623)":
        floor = 10 * tokens
    elif rule == "proposed (EIP-7976)":
        floor = 16 * 4 * (zeros + nonzeros)
    else:
        raise ValueError(rule)
    return TX_BASE + max(standard, floor)


# ---------------- Three DID scenarios ----------------
def scenario_register_key(pk_len):
    """A. Store the holder's public key in a DID registry contract (storage)."""
    calldata = abi_bytes_arg(rng.randbytes(pk_len))
    slots = 1 if pk_len <= 31 else 1 + math.ceil(pk_len / 32)   # Solidity `bytes` layout
    execution = CALL_OVERHEAD + slots * SSTORE_NEW_SLOT + memory_cost(pk_len)
    return calldata, execution


def scenario_key_exchange(ct_len):
    """B. Send an encrypted credential: KEM capsule + nonce/tag + pointer on-chain
          (emitted as an event), the encrypted credential itself stays off-chain."""
    payload_len = ct_len + NONCE_TAG + POINTER
    calldata = abi_bytes_arg(rng.randbytes(payload_len))
    execution = (CALL_OVERHEAD + LOG_BASE + 2 * LOG_TOPIC
                 + LOG_BYTE * payload_len + memory_cost(payload_len))
    return calldata, execution


def scenario_full_onchain(ct_len, data_kb):
    """C. Naive design: put the whole encrypted credential on-chain as well."""
    payload_len = ct_len + NONCE_TAG + data_kb * 1024
    calldata = abi_bytes_arg(rng.randbytes(payload_len))
    execution = (CALL_OVERHEAD + LOG_BASE + 2 * LOG_TOPIC
                 + LOG_BYTE * payload_len + memory_cost(payload_len))
    return calldata, execution


RULES = ["current (EIP-7623)", "proposed (EIP-7976)"]
rows = []
for rule in RULES:
    for scheme, (pk_len, ct_len) in SCHEMES.items():
        cd, ex = scenario_register_key(pk_len)
        rows.append(dict(rule=rule, scenario="A. register key", scheme=scheme, data_kb=0,
                         onchain_bytes=len(cd), gas=tx_gas(cd, ex, rule)))
        cd, ex = scenario_key_exchange(ct_len)
        rows.append(dict(rule=rule, scenario="B. key exchange (data off-chain)", scheme=scheme,
                         data_kb=0, onchain_bytes=len(cd), gas=tx_gas(cd, ex, rule)))
        for kb in DATA_SIZES_KB:
            cd, ex = scenario_full_onchain(ct_len, kb)
            rows.append(dict(rule=rule, scenario="C. full credential on-chain", scheme=scheme,
                             data_kb=kb, onchain_bytes=len(cd), gas=tx_gas(cd, ex, rule)))

df = pd.DataFrame(rows)
df["fits_one_tx"] = df["gas"] <= TX_GAS_CAP

# % increase vs X25519 for the same rule / scenario / data size
base = df[df.scheme == "X25519"].set_index(["rule", "scenario", "data_kb"])["gas"]
df["increase_vs_x25519_%"] = df.apply(
    lambda r: (r.gas / base[(r.rule, r.scenario, r.data_kb)] - 1) * 100, axis=1)

df.to_csv("../data/gas_results.csv", index=False)

# ---------------- Print summary ----------------
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", None)
for scenario in ["A. register key", "B. key exchange (data off-chain)"]:
    print(f"\n=== {scenario} ===")
    t = df[df.scenario == scenario].pivot(index="scheme", columns="rule",
                                          values=["gas", "increase_vs_x25519_%"])
    print(t.round(1).loc[list(SCHEMES)])

print("\n=== C. full credential on-chain: % increase vs X25519 (current rules) ===")
c = df[(df.scenario == "C. full credential on-chain") & (df.rule == RULES[0])]
print(c.pivot(index="data_kb", columns="scheme", values="increase_vs_x25519_%")
       [list(SCHEMES)].round(2))
print("\nfits in one transaction (<= 16,777,216 gas)?")
print(c.pivot(index="data_kb", columns="scheme", values="fits_one_tx")[list(SCHEMES)])

# ---------------- Optional: in USD (illustrative assumptions) ----------------
GAS_PRICE_GWEI = 1.0     # ASSUMPTION - change to today's value
ETH_USD = 3000.0         # ASSUMPTION - change to today's value
print(f"\n=== illustrative cost in USD (gas price {GAS_PRICE_GWEI} gwei, ETH ${ETH_USD:,.0f}) ===")
ab = df[(df.rule == RULES[0]) & (df.data_kb == 0)].copy()
ab["usd"] = ab.gas * GAS_PRICE_GWEI * 1e-9 * ETH_USD
print(ab.pivot(index="scheme", columns="scenario", values="usd").loc[list(SCHEMES)].round(4))