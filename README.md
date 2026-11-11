# pqc-gas-project
Personal data security project

## Limitations

**Gas model**

- **Execution overhead is an assumption.** Each contract call is charged a fixed 5,000 gas for function dispatch, ABI decoding and checks (`CALL_OVERHEAD` in `src/gas_model.py`). This figure is an estimate, not a measurement from a deployed contract. The goal is a fair comparison between X25519 and ML-KEM rather than an exact audit of a specific contract.
- **USD figures are illustrative only.** The dollar costs assume a gas price of 1 gwei and an ETH price of $3,000 (`GAS_PRICE_GWEI` and `ETH_USD` at the bottom of `src/gas_model.py`). Both values change constantly and should be updated before quoting any dollar amount.
- **Percentage increases do not depend on market prices.** The main result, the gas increase of ML-KEM relative to X25519, is a ratio of gas units. Gas price and ETH price cancel out, so the percentages hold regardless of market conditions.
- **Gas is calculated, not regressed.** The original plan was to predict gas fees with a statistical regression. However, Ethereum gas is determined exactly by a published formula (calldata bytes, storage slots and execution cost), not by CPU time. Gas is therefore computed directly from the standardized key and ciphertext sizes. Statistical modelling is applied where it belongs: to the timing measurements, which contain real measurement noise.
- **Proposed pricing rules may change.** The "proposed" scenario uses EIP-7976 (64/64 gas per calldata byte), which is planned for the Glamsterdam upgrade but is not yet live. Its final parameters, and other proposed repricings (e.g. storage costs), may differ from what is modelled here.

**Timing benchmark**

- **Pure-Python implementation.** ML-KEM timings come from `kyber-py`, a pure-Python reference implementation that is not optimized for speed. Absolute timings, and the ML-KEM vs X25519 ratio, are much larger than they would be with an optimized C implementation such as liboqs. The structural finding (a fixed key-encapsulation cost plus an identical per-MB AES cost) is expected to hold, but the absolute numbers should not be generalized.
- **Single machine.** All timings were measured on one laptop (macOS, Apple Silicon). Results on other hardware will differ in absolute terms.
