# Validation protocol runbook — reduced-scale (100 traces per architecture)

**Purpose.** Execute validation of the TLC paper at a scale sufficient to detect *systematic* modelling errors (wrong constant, wrong opcode, missed path). A full-protocol run (`n ≥ 1 000`) is scheduled as a follow-up if this pass is clean.

**Success criterion.** For every trace, `|G_observed − G_PIDGC| ≤ 100 gas` (the memory-expansion rounding bound `ε` from §3.4). Per-architecture mean diff within ±10 gas, with no systematic sign. If the criterion holds for all ~800 traces, PIDGC is empirically validated at reduced scale. If it fails, the root-cause procedure below decides whether the failure is (a) a modelling bug to fix, (b) a new limitation to document, or (c) an ε recalibration.

---

## Phase 1 — Environment (target: 2–3 days)

### 1.1 Foundry and fork setup

Install Foundry (`foundryup`) at a pinned version. Target:
- `forge 0.2.0+` with Cancun support
- `anvil` with `--fork-url` and `--fork-block-number`
- `cast` for read-side inspection

Pin the fork block. Use a block from Q1 2026 where the Chainalysis Sanctions Oracle and USDC are both at their then-current implementations. Record the exact block number in `README.md`. Every subsequent run uses the same block; no drift permitted.

```bash
export FORK_BLOCK=20800000   # example — pick an actual Q1 2026 block
export RPC_URL="https://eth.llamarpc.com"
anvil --fork-url $RPC_URL --fork-block-number $FORK_BLOCK --port 8545
```

Verify with `cast block-number --rpc-url http://localhost:8545` — must return `$FORK_BLOCK`.

### 1.2 Repo skeleton (TODO)

```
tlc-validation/
├── contracts/          # reference deployments for B, C, E, F, D
├── scripts/            # Foundry deploy + workload scripts
├── workloads/          # 100-trace JSON specifications per architecture
├── traces/             # output .jsonl files (one line = one trace)
├── pidgc/              # Python implementation of §4.6 closed forms
├── analysis/           # validation reports, outlier investigation
├── reproduce.sh        # end-to-end pipeline
└── README.md           # pinned versions, fork block, how to run
```

### 1.3 Python analysis environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install web3==6.15 pandas pytest
```

Pin exact versions in `requirements.txt`. The PIDGC module must run on stock Python with no EVM dependency — it is pure arithmetic over the Yellow-Paper schedule.

---

## Phase 2 — Reference contracts (target: 4–6 days; F is the long pole)

### 2.1 On-mainnet architectures — use directly

- **A (blocklist)** = USDC, `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48`
- **G (shared oracle)** = Chainalysis Sanctions Oracle, `0x40C57923924B5c5c5455c48D93317139ADDaC8fb`

No deployment needed. Interact via the fork with `cast call` / `cast send` as the tx originator. Fund test accounts with `anvil_setBalance`.

### 2.2 Deploy fresh — OpenZeppelin / Tokeny references

- **B (allowlist)**: OpenZeppelin ERC-1404 reference → `contracts/B_Allowlist.sol`
- **C (ERC-3643)**: Tokeny T-REX full stack (`github.com/TokenySolutions/T-REX`) → deploy Identity Registry, Trusted Issuers Registry, Claim Topics Registry, ONCHAINID, Compliance, and Token at `T=2 claim topics, U=1 issuer per topic` as the canonical case
- **E (ERC-1400)**: OpenZeppelin-compatible ERC-1400 reference → deploy at `p=3 partitions`
- **D (ERC-7943 adapter)**: thin adapter contract that forwards `canTransfer` / `canSend` / `canReceive` / `getFrozenTokens` to either A, C, E, or G — need four separate D-on-X deployments

### 2.3 Deploy fresh — F is the long pole

**F (zkKYC)** is the implementation gap. No production mainnet TLC-specific SNARK verifier exists as an obvious reference. Options, in order of preference:

1. Port PARScoin's verifier (Kiayias et al., IACR 2023/1908) if source is available
2. Compile a minimal Groth16 verifier circuit for a toy KYC predicate and generate the verifier contract via `snarkjs` or `circom`
3. Use Tornado Cash's BN254 Groth16 verifier as a shape proxy (same precompile pattern, different predicate)

Target `k=3 pairing products` as the canonical case. Record the circuit's `(m, n, x)` parameters — the PIDGC formula for F needs them.

### 2.4 One-shot deployment script

```bash
forge script scripts/DeployAll.s.sol --rpc-url http://localhost:8545 --broadcast
# writes deployed-addresses.json with stable keys: B, C_token, C_IR, C_CTR, C_TIR, ..., E, F_verifier, F_token, D_A, D_C, D_E, D_G
```

---

## Phase 3 — Workload design (target: 2–3 days)

### 3.1 The 100-trace split per architecture

| Bucket | Count | What it tests |
|---|---|---|
| Happy path, warm | 40 | Steady-state (frontier-relevant) operating point |
| Happy path, cold | 30 | First-touch EIP-2929 pricing |
| Revert paths (per guard) | 15 | Path-exactness P2; each guard exercised at least twice |
| Parameter sweep | 10 | Parametric terms (C: T/U; E: p; F: k) |
| Refund-bearing | 5 | EIP-3529 cap arithmetic |
| **Total per architecture** | **100** | |

Allocation above applies to A, B, G. For C, replace 10 parameter-sweep with `(T=3,U=2) × 5` and `(T=4,U=2) × 5`. For E, replace with `p=2 × 5` and `p=6 × 5`. For F, replace with `k=2 × 5` and `k=4 × 5`.

### 3.2 Workload file format

```json
// workloads/A.json
[
  {
    "trace_id": "A-0001",
    "bucket": "happy_warm",
    "caller": "0xAAA...",
    "target_function": "transfer(address,uint256)",
    "calldata_args": {"to": "0xBBB...", "amount": "1000000"},
    "prewarm": [{"contract": "USDC", "slot": "blocklist[0xAAA]"}, ...],
    "expected_guard": "sender_ok && receiver_ok && balance_ok",
    "expected_path": "A_transfer_happy"
  },
  ...
]
```

Each entry is declarative — the execution script reads it, performs the prewarm if any, sends the transaction, records `gasUsed`. The `expected_guard` and `expected_path` are the PIDGC labels against which the observed trace will be compared.

### 3.3 Prewarming strategy

EIP-2929 warmth is per-transaction, so "warm" traces must touch the relevant slot earlier *in the same transaction*. The clean way: use a Foundry helper contract that calls a read-only touch opcode (a `STATICCALL` to an `extcodehash` or a throwaway `SLOAD`) before the real transfer call, inside the same transaction. Avoid using EIP-2930 access lists for prewarming in initial runs — those change the intrinsic cost separately and complicate the attribution. Record the prewarm strategy per trace in the workload file.

---

## Phase 4 — Trace collection (target: 3–5 days)

### 4.1 Execution loop

For each architecture, for each trace in `workloads/$ARCH.json`:

```solidity
// scripts/RunWorkload.s.sol — executes one trace and emits a structured log
function runTrace(TraceSpec spec) external returns (TraceResult memory) {
    // 1. prewarm if required
    for (uint i = 0; i < spec.prewarm.length; i++) {
        // touch the slot via a read
    }
    // 2. send the transaction, capture gasleft() before and after
    uint256 g0 = gasleft();
    (bool ok, bytes memory ret) = spec.target.call(spec.calldata);
    uint256 g1 = gasleft();
    // 3. emit structured event: gasUsed, revert status, block, tx.origin, msg.sender
    return TraceResult({gasUsed: g0 - g1, reverted: !ok, returnData: ret, ...});
}
```

Wrap the loop in a driver that resets the fork to `$FORK_BLOCK` between traces so state does not carry over. Export to `traces/$ARCH.jsonl` with one JSON object per line.

### 4.2 Trace record schema

```json
{
  "trace_id": "A-0001",
  "architecture": "A",
  "bucket": "happy_warm",
  "block": 20800000,
  "gas_used": 48742,
  "reverted": false,
  "revert_reason": null,
  "calldata": "0xa9059cbb...",
  "caller": "0xAAA...",
  "target_contract": "USDC",
  "warmth_state": {
    "blocklist_sender": "warm",
    "blocklist_receiver": "cold",
    "balance_sender": "warm",
    "balance_receiver": "cold"
  },
  "policy_parameters": {},
  "refund_accrued": 0,
  "timestamp_utc": "2026-04-25T10:14:32Z"
}
```

Every field must be derivable without re-executing the EVM — that is, the record is self-sufficient for PIDGC evaluation offline.

---

## Phase 5 — PIDGC evaluation (target: 2–3 days)

### 5.1 Reference implementation

`pidgc/pidgc.py`:

```python
# Shanghai/Cancun constants (§4.6)
SLOAD_COLD = 2100
SLOAD_WARM = 100
SSTORE_RESET_WARM = 2900
CALL_COLD = 2600
CALL_WARM = 100
JUMPI = 10
INTRINSIC = 21000
ERC20_CORE = 48000  # baseline — calibrated per §4.6
ECRECOVER = 3000
ECADD = 150
ECMUL = 6000
def ECPAIRING(k): return 45000 + 34000 * k
def LOG3(length_bytes): return 1500 + 8 * length_bytes

def pidgc_A(warmth):
    sload_sender = SLOAD_COLD if warmth['blocklist_sender'] == 'cold' else SLOAD_WARM
    sload_receiver = SLOAD_COLD if warmth['blocklist_receiver'] == 'cold' else SLOAD_WARM
    return ERC20_CORE + sload_sender + sload_receiver + 2 * JUMPI

def pidgc_C(warmth, T, U, k_rules):
    # per §4.6 closed form — full expansion omitted for brevity
    ...
```

One function per architecture. Each takes the fields recorded in the trace schema and returns an integer.

### 5.2 Guard evaluator

A second function `which_guard(trace) → guard_id` that walks the recorded `calldata` and `warmth_state` and returns which guard of `Π(f)` matched. For the happy path this is trivial; for reverts it requires knowing which `require` fired (derived from `revert_reason` where available).

### 5.3 Unit tests

Hard-code the A happy-path example from the algorithm-flow figure (48 742 gas, all cold, sender and receiver not blocklisted, sufficient balance) and assert `pidgc_A(...) == 48742`. Repeat for one canonical example per architecture — these become the regression tests for any future formula change.

---

## Phase 6 — Comparison and outlier analysis (target: 2–3 days)

### 6.1 Validation report

```bash
python analysis/compare.py --traces traces/ --out analysis/validation_report.csv
```

Columns: `arch, trace_id, guard_matched, observed, predicted, diff, within_epsilon`.

### 6.2 Summary statistics per architecture

```
analysis/summary.md:
  - A: n=100, mean(diff)=+3.2, median=0, max|diff|=48, outliers(>100)=0   ✓
  - B: n=100, mean(diff)=-1.1, median=0, max|diff|=32, outliers=0          ✓
  - ...
  - F: n=100, mean(diff)=+142, median=+135, max|diff|=210, outliers=87     ✗
```

A non-zero mean, especially a *consistent sign*, indicates systematic error. In the illustrative F row above, the +142 gas offset suggests a missed cost term in the F closed form — this is exactly the kind of error reduced-scale validation is designed to catch.

### 6.3 Outlier triage

For each outlier (|diff| > 100):

1. **Memory-expansion rounding.** Expected ≤ 32 gas per call-frame expansion. If diff is ≤ 50 and memory-heavy op is present on the path, classify as ε and update ε if needed.

2. **Refund cap arithmetic.** If the trace clears storage and `G_raw / 5` is not an integer, the floor may cause a small off-by-one. Expected ≤ 5 gas. Classify as ε.

3. **Missed opcode.** If diff is consistent across multiple traces of the same bucket, walk the bytecode of the architecture manually and find the cost term absent from the §4.6 formula. Add it to the closed form, re-run validation.

4. **Assumption violation.** If a callee's bytecode changed between analysis and the fork's block (AS-2 breach), rerun on a different block or document as a limitation.

5. **Unexpected precompile behaviour.** If F's ECPAIRING differs from `45000 + 34000·k`, check that the verifier is using the BN254 precompile at `0x08` and not a bundled pairing library. Update AS-4 scope if needed.

---

## Phase 7 — Paper integration (target: 1–2 days)

### 7.1 Text changes

- **Abstract.** Replace "The paper's quantitative claims are therefore model-consistent, not yet trace-consistent" with "Quantitative claims are validated against N=[total] mainnet-fork traces with mean absolute error ≤ [ε'] gas per trace (§5.3a)."

- **§5 (Results).** Insert new subsection §5.3a "Empirical validation" with Table 3 (observed vs predicted per architecture: mean, median, max-abs, outlier count). Keep Figure 3 as-is; add a footnote noting it uses empirically validated points.

- **§5.4 (Limitations).** Promote the taxonomy limit to first position. Move validation from limit to historical note ("an earlier version of this paper reported model-consistent predictions; the present version validates them empirically"). Third limit (AS-2) stays.

- **Changelog.** Bump to v0.6 (empirical validation pass).

### 7.2 Artefact release

Create a GitHub repo with the structure from §1.2. Tag `v1.0-validation`. Archive on Zenodo for a DOI. Add the DOI to the paper's §3.4 and to a new §7 "Artefact availability" section.

Include `CHECKS.md` specifying what a successful third-party reproduction must show: all ~800 PIDGC predictions match the shipped traces within ε on any machine that runs the pinned Foundry version against the pinned fork block.

### 7.3 Artefact evaluation (optional)

If the target venue has an artefact-evaluation track (ACM Functional, ACM Reusable, IEEE Badged), submit for it. The reproduce.sh script and CHECKS.md already satisfy the core requirements; a short response to the artefact-evaluation questionnaire completes it.

---

## Risks and contingencies

**R1 — F reference implementation unavailable.** Mitigation: use Tornado Cash's BN254 Groth16 verifier as a shape proxy and document the substitution. The F closed form validates against the verifier's actual bytecode, which is what matters for precompile cost agreement.

**R2 — ERC-3643 full stack deployment is brittle.** Mitigation: use Tokeny's canonical deployment script unmodified; do not attempt to re-implement the registry pattern. Pin to a specific Tokeny commit.

**R3 — Fork state drift.** Mitigation: pin block number strictly. If anvil version bumps change fork behaviour, pin anvil version too.

**R4 — Systematic error found in a closed form.** Not a contingency — this is the *point* of the validation. Fix the formula, re-run the affected architecture's 100 traces, update the paper.

**R5 — Wall time exceeds estimate.** At reduced scale the bottleneck is typically reference-contract deployment (Phase 2), not trace execution. If Phase 2 runs long, defer F to a follow-up paper and validate five architectures instead of six — the main rankings do not depend on F's empirical number, only on its closed form.

## What "caught systematic errors" means in practice

Reduced scale (n=100) has statistical power to detect:
- Any constant offset ≥ ±20 gas with high confidence (mean diff is a tight estimator at n=100 for a near-deterministic quantity)
- Any missing linear term in the cost, because the parameter sweep would show a slope the formula does not predict
- Any missed opcode, because the hundred traces sample multiple paths and a missed opcode presents on a subset

It does *not* have power to detect:
- Rare-path errors that fire on < 1% of traffic — those require n=1000+ and are the reason the full protocol exists
- Distribution-tail anomalies (gas spikes on specific calldata patterns) — these need adversarial workloads and are out of scope here

This reduced-scale pass is sufficient to claim empirical validity for the rankings and the Pareto frontier, which are the paper's main contributions. The full-protocol run supports stronger claims (statistical distribution agreement) and is the natural next paper.
