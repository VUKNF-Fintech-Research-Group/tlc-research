# tlc-research

**Model Based Comparison of Gas Costs in Token Level Compliance Architectures**

Supplementary repository for the conference paper submitted to the BIS conference on financial innovation and technology.

---

## What this paper does

Regulated tokens — stablecoins, tokenized bonds, real-world assets — must enforce compliance checks (sanctions screening, KYC, asset freezes) directly inside their smart contracts at every transfer. This design pattern is called **token level compliance (TLC)**. Its gas cost is economically significant: at scale, compliance overhead can represent millions of dollars per month in user fees, yet no systematic method exists for comparing the cost of different TLC designs.

This paper addresses that gap in three steps:

1. **Defines TLC formally** as an on-chain predicate applied at every state-changing token function, grounded in the Ethereum Yellow Paper execution model.

2. **Constructs PIDGC** (Path-Indexed Deterministic Gas Cost) — a closed-form gas cost model that produces *exact* (not upper-bound) per-transfer gas expressions by exploiting the bounded, loop-free structure of TLC contracts.

3. **Compares six production TLC architectures** using PIDGC, derives their closed-form cost formulas, and positions them on a gas-overhead vs. compliance-functionality map.

### Key result

Compliance overhead ranges from **220 gas** (simple blocklist, O(1)) to **173,600 gas** (ZK proof verification, O(k)) — a factor of ~800×. The dominant cost driver is *storage access structure*, not compliance logic complexity.

### The six architectures

| ID | Design | Example deployments | Cost class |
|----|--------|---------------------|------------|
| A | Blocklist | USDC, USDT, PYUSD | Θ(1) |
| B | Allowlist | ERC-1404, Paxos PAXG | Θ(1) |
| G | Shared compliance oracle | Chainalysis Oracle, Ethereum Attestation Service | Θ(1) |
| E | Partitioned tokens | Codefi / Universal Token | Θ(p) |
| C | Modular identity (ERC-3643) | BlackRock BUIDL| Θ(T·U) |
| F | Zero-knowledge verification | PARScoin, Sismo Connect | Θ(k) |

---

## What is in this repository

The paper is 15 pages. Several technical components were shortened or omitted for space. This repository provides the full versions.

```
tlc-research/
├── README.md                        ← this file
├── supplementary/
│   ├── opcodes.md                   ← full opcode/precompile table used in PIDGC formulas
│   ├── proof-sketches.md            ← expanded proofs for P1 (Determinism),
│   │                                   P2 (Path-exactness), P3 (Agreement)
│   └── validation-protocol.md       ← full validation runbook: how to test PIDGC
│                                       predictions against mainnet-fork traces
├── pidgc/
│   ├── constants.py                 ← Shanghai/Cancun opcode schedule (source of truth
│   │                                   for all numbers in the paper)
│   └── architectures.py             ← closed-form G_A … G_G functions + predict()
```

### `supplementary/opcodes.md`

The complete table of EVM opcodes and precompile costs used in every PIDGC formula, pinned to the Shanghai/Cancun gas schedule (Yellow Paper + EIP-2929 + EIP-1108 + EIP-3529). The paper prints an abbreviated version as Table 2; this file includes all constants, their EIP source, and which architecture each drives.

### `supplementary/proof-sketches.md`

Formal sketches for the three model properties stated in §4.3 of the paper:
- **P1 Determinism** — same inputs always yield the same gas cost
- **P2 Path-exactness** — cost equals the sum over a finite, enumerable path set
- **P3 Agreement with execution** — model matches a conformant EVM implementation exactly

This file provides the full argument for each property, including the role of each assumption (AS-1 through AS-4) and the known approximation (memory-expansion rounding, ≤32 bytes per call-frame).

### `supplementary/validation-protocol.md`

A complete protocol for empirical validation of PIDGC predictions against mainnet-fork execution traces. The paper states (Limitations) that quantitative results are model-based and have not yet been validated at scale. This document specifies exactly how that validation should be conducted: environment setup, reference contract deployment, workload design (100 traces per architecture across 5 buckets), trace collection, PIDGC comparison, outlier triage, and paper integration. The `pidgc/` module is the reference implementation used in the comparison step.

### `pidgc/`

Pure-Python, dependency-free reference implementation of the PIDGC closed forms of the paper. No EVM required — it is arithmetic over the Yellow Paper schedule.

```python
from pidgc import predict

# Reproduce Table 2 and Figure 3, warm row for C (T=2, U=1)
p = predict("C", warmth="warm", T=2, U=1, k_rules=2)
print(p.gas)                # 55 700
print(p.compliance_overhead) # 7 700
```
---

## Quick start

```bash
# No installation needed — pure Python stdlib
python3 pidgc/architectures.py
```

Or, to reproduce all Table 2 and Figure 3 data:

```python
from pidgc.architectures import predict

configs = [
    ("A",  "cold"),
    ("A",  "warm"),
    ("B",  "warm"),
    ("G",  "warm"),
    ("E",  "warm", {"p": 3}),
    ("C",  "warm", {"T": 2, "U": 1, "k_rules": 2}),
    ("C",  "warm", {"T": 4, "U": 2, "k_rules": 2}),
    ("F",  "warm"),
]

for cfg in configs:
    arch, w = cfg[0], cfg[1]
    kw = cfg[2] if len(cfg) > 2 else {}
    print(predict(arch, warmth=w, **kw))
```

---

## Citing

*Citation details will be added upon paper acceptance.*

---

## Status

| Component | Status |
|-----------|--------|
| PIDGC Python evaluator | Ready — Table 2 and Figure 3 data rows reproduced |
| Opcode table | Complete |
| Proof sketches | Complete |
| Validation protocol | Specified; trace collection pending |
| Trace scripts (Foundry) | A, B, E, G ready; C and F stubs |
| Empirical validation report | Pending (see validation-protocol.md) |

---

## License

The code in `pidgc/` is released under the MIT License.
Supplementary documents are released under CC BY 4.0.
