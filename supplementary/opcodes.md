# Full Opcode and Precompile Table — PIDGC Cost Schedule

> **Source.** All constants are pinned to the **Shanghai/Cancun** gas schedule.
> Primary references: Ethereum Yellow Paper (Wood 2025), EIP-2929, EIP-2930, EIP-3529, EIP-1108.
> The paper prints an abbreviated version. This file is the complete reference.

---

## 1. Storage operations (EIP-2929 / EIP-2930)

EIP-2929 introduced cold/warm pricing for storage and account accesses. Within a single transaction, the first access to a slot (or contract address) is *cold*; any subsequent access is *warm*. EIP-2930 access lists allow pre-declaring slots as warm at the cost of a small intrinsic surcharge.

| Opcode | Cold gas | Warm gas | EIP | Used in |
|--------|----------|----------|-----|---------|
| `SLOAD` | 2,100 | 100 | EIP-2929 | Every compliance check. Dominant cost driver for A, B, E. |
| `SSTORE` set (0 → nonzero) | 20,000 | 20,000 | Yellow Paper G_sset | Mint, initial blocklist insertion, first partition rule write. |
| `SSTORE` reset (nonzero → nonzero) | 5,000 | 2,900 | EIP-2929 | Balance update — fires twice per transfer (sender − amount, recipient + amount). |
| `SSTORE` clear (nonzero → 0) | 5,000 − refund +4,800 | — | EIP-3529 | Un-blocklisting, claim revocation. Net cost after refund ≈ 200 gas (capped). |
| `TLOAD` | 100 | 100 | EIP-1153 | Transient storage; not used in any of the six architectures but relevant for future designs. |
| `TSTORE` | 100 | 100 | EIP-1153 | As above. |

**Refund cap (EIP-3529).** Storage-clearing refunds are capped at `floor(G_used / 5)`. The effective credit for clearing one slot is therefore at most ~4,800 gas, regardless of how many slots are cleared.

---

## 2. Cross-contract calls (EIP-2929)

The cold/warm distinction applies equally to contract addresses: the first call to a given address in a transaction is cold (2,600 gas); subsequent calls are warm (100 gas). This is the dominant cost driver for architectures G and C.

| Opcode | Cold gas | Warm gas | EIP | Used in |
|--------|----------|----------|-----|---------|
| `CALL` | 2,600 | 100 | EIP-2929 | External function call (state-modifying). Used in C (registry fan-out). |
| `STATICCALL` | 2,600 | 100 | EIP-2929 | Read-only external call. Used in G (oracle query), C (claim lookup). |
| `DELEGATECALL` | 2,600 | 100 | EIP-2929 | Proxy dispatch. Used in upgradeable ERC-3643 / UUPS proxies. |
| `CALLCODE` | 2,600 | 100 | EIP-2929 | Legacy; present in older ERC-20 implementations. |

**Note on call gas forwarding.** The `CALL` opcode itself costs the above; the *forwarded* gas consumed inside the callee is charged separately and is already counted in the callee's opcode trace within PIDGC.

---

## 3. Control flow

| Opcode | Gas | Source | Used in |
|--------|-----|--------|---------|
| `JUMPI` | 10 | Yellow Paper | Each `require()` check — fires once per compliance guard. |
| `JUMP` | 8 | Yellow Paper | Unconditional branches; rare in compliance paths. |
| `JUMPDEST` | 1 | Yellow Paper | Jump destination marker; negligible. |

---

## 4. Arithmetic and stack (selected)

These opcodes appear in compliance logic but are individually cheap. They are listed for completeness; their contribution to total gas is < 1% in all six architectures.

| Opcode | Gas | Used in |
|--------|-----|---------|
| `ADD`, `SUB`, `MUL` | 3 | Balance arithmetic. |
| `EQ`, `ISZERO`, `LT`, `GT` | 3 | Comparison in require() guards. |
| `AND`, `OR`, `XOR` | 3 | Bitmask operations (partition flags in E). |
| `PUSH1`–`PUSH32` | 3 | Constant loading. |
| `DUP1`–`DUP16` | 3 | Stack duplication. |
| `SWAP1`–`SWAP16` | 3 | Stack reordering. |
| `MLOAD` | 3 | Memory read. |
| `MSTORE` | 3 | Memory write. |
| `CALLDATALOAD` | 3 | Read one word from calldata. |
| `CALLDATASIZE` | 2 | Length of calldata. |

---

## 5. Logging

| Opcode | Gas | Formula | Used in |
|--------|-----|---------|---------|
| `LOG0` | 375 + 8·len | 375 + 0·375 + 8·len | Not used in compliance paths. |
| `LOG1` | 375 + 8·len + 375 | 1-topic log | Approval events. |
| `LOG2` | 375 + 8·len + 750 | 2-topic log | Some Transfer events. |
| `LOG3` | **1,500 + 8·len** | 375 + 3·375 + 8·len | ERC-20 Transfer event: 3 topics (event sig, from, to), data = uint256 amount. For 32-byte data: **1,500 + 8·32 = 1,756 gas**. Used in G_core baseline. |

The `LOG3` cost is included in `G_ERC20_CORE ≈ 48,000 gas`, not in the compliance overhead column of Table 3.

---

## 6. Intrinsic transaction cost

| Item | Gas | Source | Notes |
|------|-----|--------|-------|
| Base intrinsic cost | **21,000** | Yellow Paper G_transaction | Charged once per transaction regardless of execution. |
| Calldata — zero byte | 4 | Yellow Paper G_txdatazero | Per zero byte in calldata. |
| Calldata — nonzero byte | 16 | Yellow Paper G_txdatanonzero | Per nonzero byte in calldata. |
| Access list entry (EIP-2930) | 2,400 | EIP-2930 | Per address pre-declared warm. |
| Access list storage key (EIP-2930) | 1,900 | EIP-2930 | Per storage slot pre-declared warm. |

**Calldata cost for Architecture F (zkKYC).** A Groth16 proof for a 3-pairing verification circuit consists of approximately 8 field elements (π_A, π_B, π_C each ≈ 64–128 bytes), totalling ~256–320 nonzero bytes. At 16 gas/byte: `G_calldata(π) ≈ 256 × 16 = 4,096 gas`.

---

## 7. Cryptographic precompiles

Precompile addresses are fixed by the Yellow Paper and EIPs. Their gas schedules are independent of cold/warm access-list state — precompiles are not subject to EIP-2929 pricing.

| Precompile | Address | Gas formula | EIP | Used in |
|------------|---------|-------------|-----|---------|
| `ECRECOVER` | `0x01` | **3,000** flat | Yellow Paper | Architecture C: each trusted issuer signature verification. Fires once per (topic, issuer) pair — T·U times per transfer. |
| `SHA2-256` | `0x02` | 60 + 12·⌈len/32⌉ | Yellow Paper | Not used in current architectures. |
| `RIPEMD-160` | `0x03` | 600 + 120·⌈len/32⌉ | Yellow Paper | Not used. |
| `Identity` | `0x04` | 15 + 3·⌈len/32⌉ | Yellow Paper | Occasional use in calldata forwarding. |
| `MODEXP` | `0x05` | formula per EIP-2565 | EIP-2565 | Not used in TLC architectures. |
| `ECADD` (BN254) | `0x06` | **150** flat | EIP-1108 | Architecture F: elliptic-curve point addition in Groth16 verification. Fires n times (n ≈ 5–10 for typical circuits). |
| `ECMUL` (BN254) | `0x07` | **6,000** flat | EIP-1108 | Architecture F: scalar multiplication. Fires m times (m ≈ 4–6). |
| `ECPAIRING` (BN254) | `0x08` | **45,000 + 34,000·k** | EIP-1108 | Architecture F: pairing check. k = number of pairing products. For Groth16: k = 3 (one for each group element in the proof). |
| `BLAKE2F` | `0x09` | 1 per round | EIP-152 | Not used. |
| `KZG point eval` | `0x0A` | 50,000 | EIP-4844 | Not used in TLC. Relevant for blob-based L2 data availability. |

**ECPAIRING dominance in F.** At k=3 pairing products: `ECPAIRING(3) = 45,000 + 34,000×3 = 147,000 gas`. This single call accounts for ~84% of architecture F's compliance overhead (~173,600 gas warm). ECMUL and ECADD contribute ~3% each.

---

## 8. ERC-20 core baseline (G_core)

The baseline `G_ERC20_CORE ≈ 48,000 gas` used in all PIDGC formulas is composed as follows:

| Component | Gas (approx.) | Notes |
|-----------|---------------|-------|
| Intrinsic tx cost | 21,000 | Fixed per transaction |
| `SSTORE` sender balance (nz→nz, warm) | 2,900 | Debit |
| `SSTORE` recipient balance (nz→nz, warm) | 2,900 | Credit |
| `LOG3` Transfer event (32-byte data) | 1,756 | 3 topics + 32 bytes |
| Function dispatch, stack, arithmetic | ~3,500 | `PUSH`, `DUP`, `MLOAD`, `EQ`, etc. |
| Calldata (68-byte transfer call, warm) | ~1,000 | Approx. for typical address/amount |
| Padding / rounding | ~14,944 | Accounts for compiler-generated scaffolding |
| **Total (empirical baseline)** | **≈ 48,000** | Matches Ethereum mainnet USDC traces |

The compliance overhead columns in Table 3 are all computed as `G_arch_warm − G_ERC20_CORE`.

---

## 9. Refund mechanics (EIP-3529 summary)

| Rule | Value | Source |
|------|-------|--------|
| Refund for clearing a slot (nonzero → 0) | +4,800 gas | EIP-3529 |
| Refund cap | `floor(G_used / 5)` | EIP-3529 |
| Net maximum refund per transaction | 20% of gross gas | Derived |

Pre-EIP-3529 the refund was 15,000 gas per cleared slot with a 50% cap. EIP-3529 reduced both to prevent gas-token abuse. The PIDGC model accounts for refunds in architectures where storage is cleared during the compliance path (e.g., un-blocklisting in A, claim revocation in C).

---

## 10. What changes at each protocol upgrade

| Upgrade | Relevant changes | Impact on PIDGC |
|---------|-----------------|-----------------|
| Berlin (EIP-2929) | Cold/warm storage pricing introduced | Core SLOAD/CALL split |
| London (EIP-3529) | Refund cap reduced 50% → 20% | Refund term in P2 |
| Shanghai (EIP-3855) | PUSH0 opcode (gas=2) | Minor: compiler sometimes uses PUSH0 |
| Cancun (EIP-1153) | TLOAD/TSTORE introduced | Not used yet; relevant for future TLC |
| Cancun (EIP-4844) | Blob transactions; calldata repricing expected | Affects G_calldata; most relevant for F |
| Pectra (future) | EIP-7623: calldata costs may rise significantly | Would increase F overhead; rankings unchanged for A–E |
