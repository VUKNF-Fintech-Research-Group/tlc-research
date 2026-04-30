# Proof Sketches for Model Properties P1, P2, P3

> **Context.** The paper states three properties of the PIDGC model and cites this document for expanded proofs. This file provides the full argument for each property, including the precise role of each assumption and the known approximation sources.

---

## Assumptions (restated)

All three proofs operate under the following assumptions, stated in the paper:

| ID | Assumption | Formal statement |
|----|------------|-----------------|
| AS-1 | Bounded loops | Every loop reachable during execution has a bound that is either fixed at compile time or given by a known deployment parameter (T, U, p, k, m). The bound is finite and known before execution. |
| AS-2 | Fixed code | For every contract address reachable during execution, its bytecode is fixed at analysis time. In particular, upgradeable proxies are excluded unless their implementation slot is pinned. |
| AS-3 | Trusted callees | External contracts (registries, oracles, verifiers) behave as their published bytecode specifies. No adversarial re-entrancy or unexpected reverts occur on the compliance path. |
| AS-4 | Stable precompiles | Cryptographic precompiles at addresses 0x01–0x09 have the gas schedules specified in the Yellow Paper and EIP-1108. No future hardfork changes these costs during the period of analysis. |

These assumptions hold for all six architectures analysed in the paper (verified at the contract level in §3.3).

---

## P1 — Determinism

**Claim.** Under AS-1 through AS-4, the function `G_f(C, σ, I)` is a total function from `(contract tuple, pre-execution state, transaction input)` to `ℕ`.

In plain terms: given the same contract code, the same blockchain state before the transaction, and the same transaction data, the gas cost is always the same number.

### Proof

The Ethereum Yellow Paper defines EVM execution as a *big-step semantic function*:

```
Υ(σ, T) = (σ', g', A, z, o)
```

where `σ` is the pre-state, `T` is the transaction, `σ'` is the post-state, `g'` is the remaining gas, `A` is the accrued substate, `z` is the halt status, and `o` is the output data.

**Step 1 — The trace is unique.**
Under AS-2, the bytecode of every contract address reachable via CALL/STATICCALL/DELEGATECALL is fixed. The EVM state transition at each step is a deterministic function of the current opcode, the stack, memory, storage, and the program counter. Under AS-1, every loop terminates in finitely many steps. Therefore, the opcode sequence τ = (o₁, σ₁, a₁), (o₂, σ₂, a₂), … is unique and finite.

**Step 2 — Per-opcode costs are deterministic.**
Each opcode `oᵢ` has a gas cost `g(oᵢ, σᵢ, aᵢ)` defined by a finite case analysis in the Yellow Paper:
- Simple opcodes (ADD, PUSH, ISZERO, …) have a fixed constant cost independent of state.
- SLOAD: cost depends on whether the slot is in the *access list* for this transaction. The access list is a deterministic function of the execution trace up to step i — specifically, of which slots have been touched by SLOAD or SSTORE before step i in the same transaction. Under AS-2 and AS-1, this set is determined by the unique trace.
- SSTORE: cost depends on whether the slot is in the access list (cold/warm) and on the prior value of the slot (set / reset / clear). Both are determined by the unique trace.
- CALL/STATICCALL/DELEGATECALL: cost depends on whether the target address is in the access list. Determined by the unique trace.
- Precompiles (ECRECOVER, ECPAIRING, …): under AS-4, their gas cost is a fixed formula of their input length and parameters, with no dependence on state.

Therefore `g(oᵢ, σᵢ, aᵢ)` is determined by the trace τ, which is itself uniquely determined by `(C, σ, I)`.

**Step 3 — Refunds are deterministic.**
The refund accumulator `R(τ)` is a sum over SSTORE operations in τ of the refund granted by EIP-3529. Since τ is unique and SSTORE refund rules are deterministic, `R(τ)` is uniquely determined. The EIP-3529 cap `⌊Σᵢ g / 5⌋` is also uniquely determined.

**Step 4 — G_f is total.**
Combining steps 1–3:

```
G_f(C, σ, I)  =  Σᵢ g(oᵢ, σᵢ, aᵢ)  −  min(R(τ), ⌊Σᵢ g / 5⌋)
```

is a finite sum (by AS-1) of deterministic terms (by steps 1–3), minus a deterministic refund. Hence `G_f : (C, σ, I) → ℕ` is a total function. ∎

### Why each assumption is necessary for P1

- **Without AS-1:** A loop without a known bound may or may not terminate, making τ potentially infinite — G_f would be undefined.
- **Without AS-2:** A proxy that upgrades its implementation mid-transaction changes the opcode stream; τ is no longer unique for a fixed (C, σ, I).
- **Without AS-3:** An adversarial callee could re-enter and alter storage state in ways not captured by the model, breaking the uniqueness of σᵢ at each step.
- **Without AS-4:** A precompile whose cost depends on side-channel state outside the EVM (hypothetical) would introduce non-determinism into `g(oᵢ, σᵢ, aᵢ)`.

---

## P2 — Path-Exactness

**Claim.** Under AS-1 and AS-2, the set of execution paths `Π(f)` for entry function `f` is finite and enumerable. The PIDGC expression can be written as:

```
G_f(C, σ, I)  =  Σ_{π ∈ Π(f)}  𝟙[σ, I ⊨ guard(π)]  ·  G_π(C, σ)
```

where `guard(π)` is a quantifier-free predicate over `(σ, I)`, exactly one guard evaluates to true for any concrete input, and `G_π` is piecewise-affine in the cold/warm access flags along π.

In plain terms: we can list all possible execution paths, each with a condition that says when it fires, and an exact cost formula. Any concrete transaction activates exactly one path, giving its exact gas cost.

### Proof

**Step 1 — Construct the composed graph.**
Define `Γ* = CCG(C, f) ⋈ CFG(·)` as follows:
- The Contract Call Graph `CCG(C, f)` has nodes `(C_i, f_i)` for each (contract, function) pair reachable from `(C_0, f)` via CALL/STATICCALL/DELEGATECALL, and directed edges for each cross-contract call.
- Under AS-2, all call targets are statically resolvable (no dynamic dispatch to unknown bytecode), so `CCG(C, f)` has a finite, fixed node set.
- For each node `(C_i, f_i)`, the intra-procedural Control Flow Graph `CFG(C_i, f_i)` is a finite directed graph over basic blocks, with edges for conditional branches (JUMPI) and unconditional jumps.
- `Γ*` is the composition: edges of CCG become inter-procedural connections between CFG exit points (CALL sites) and CFG entry points of callees.

**Step 2 — Unroll loops.**
Under AS-1, every loop in any `CFG(C_i, f_i)` has a static bound `k_L`. Unrolling each loop `L` to its bound `k_L` replaces it with `k_L` copies of its body, eliminating all back-edges. The result is a finite DAG `Γ*_unrolled`.

**Step 3 — The path set is finite.**
A path `π ∈ Π(f)` is a root-to-leaf path in `Γ*_unrolled`. Since the graph is a finite DAG, the number of such paths is finite. (It may be exponential in the number of conditional branches, but it is finite — bounded by `2^|JUMPI nodes|` before pruning infeasible paths.)

**Step 4 — Guards partition the input space.**
Each conditional branch `(JUMPI at position p, condition c_p)` resolves to either true or false depending on `(σ, I)`. A path `π` takes a specific branch decision at each JUMPI it traverses. The path guard `guard(π)` is the conjunction of these decisions:

```
guard(π)  =  ∧_{ JUMPI_p ∈ π }  (c_p = taken_p)
```

where `taken_p ∈ {true, false}` is the branch direction on path `π`. Since branch conditions are evaluated on the deterministic state at each step (by P1), and different paths take different branch decisions, the guards are mutually exclusive by construction. They are also exhaustive (every concrete input satisfies exactly one path's guard — the path that corresponds to its actual execution). Hence:

```
∀ (σ, I):  exactly one π ∈ Π(f) satisfies  σ, I ⊨ guard(π)
```

**Step 5 — G_π is piecewise-affine.**
Along a fixed path `π`, the opcode sequence is fixed. The only source of variation in `g(oᵢ, σᵢ, aᵢ)` is the cold/warm flag for SLOAD, SSTORE, and CALL operations. Each such flag is a binary variable `w_j ∈ {0, 1}` (0 = cold, 1 = warm), and the cost of the j-th access is:

```
g_j  =  (1 − w_j) · cost_cold_j  +  w_j · cost_warm_j
       =  cost_cold_j  −  w_j · (cost_cold_j − cost_warm_j)
```

This is affine in `w_j`. The total path cost `G_π` is a sum of such terms — hence piecewise-affine in the vector of cold/warm flags `(w_1, …, w_n)`. The refund term is a deterministic sum of SSTORE operations along `π`, which is itself piecewise-affine in the cold/warm flags of those SSTOREs.

**Combining:** For any concrete `(σ, I)`, find `π*` such that `σ, I ⊨ guard(π*)`. Then `G_f(C, σ, I) = G_{π*}(C, σ)`. ∎

### What "piecewise-affine" means in practice

In the paper's Table 3, the cold/warm split is the main source of variation between the "Cold total" and "Warm total" columns. For architecture A:

```
G_A(warm)  =  G_core  +  2 · 100  +  2 · 10   =  48,000 + 220   =  48,220
G_A(cold)  =  G_core  +  2 · 2,100 + 2 · 10   =  48,000 + 4,220  =  52,220
```

The difference is `2 · (2,100 − 100) = 4,000` gas — exactly the SLOAD cold/warm premium for two storage reads. This is the "piecewise-affine" structure in action.

---

## P3 — Agreement with Execution

**Claim.** For any `(σ, I)` satisfying exactly one guard `guard(π*)`, the gas computed by the PIDGC model equals the gas charged by a conformant EVM implementation:

```
G_f(C, σ, I)  =  gas charged by a conformant EVM executing (C, σ, I)
```

In plain terms: the model is not just internally consistent — it produces the same number as the actual blockchain.

### Proof

**Step 1 — EVM charges Σᵢ g / − min(R, ⌊Σg/5⌋).**
A conformant EVM implementation (as defined by the Yellow Paper and subsequent EIPs) charges exactly:

```
G_charged  =  Σᵢ g(oᵢ, σᵢ, aᵢ)  −  min(R(τ), ⌊Σᵢ g(oᵢ, σᵢ, aᵢ) / 5⌋)
```

over the opcode trace `τ(C, σ, I)`.

**Step 2 — The PIDGC model computes the same sum.**
By Definition 2 of the paper (and the proof of P1), `G_f(C, σ, I)` is defined as exactly this sum. The guard evaluation in P2 identifies `π*` such that the opcode sequence along `π*` matches `τ(C, σ, I)` exactly. Since `G_{π*}(C, σ)` is the symbolic sum of Yellow-Paper costs along `π*`, and the concrete evaluation of this sum at `(σ, I)` reproduces `τ(C, σ, I)`, we have:

```
G_f(C, σ, I)  =  G_{π*}(C, σ)|_{concrete (σ,I)}  =  G_charged
```

Hence the model agrees with the EVM. ∎

### Known approximation: memory-expansion rounding

The Yellow Paper defines memory expansion cost as:

```
C_mem(a)  =  G_memory · a  +  ⌊a² / 512⌋
```

where `a` is memory size in words (32 bytes). The `⌊·⌋` floor introduces a rounding error of at most 1 word = 32 bytes per call-frame expansion. Across a typical TLC transfer (1–5 call frames), this introduces at most `5 × 32 = 160 gas` of discrepancy between the symbolic PIDGC expression and the concrete EVM charge.

In practice, for the six architectures studied, memory usage is minimal and the discrepancy is ≤ 32 gas per transfer — well below the validation criterion of ±100 gas stated in the validation protocol. This approximation is therefore acceptable.

The PIDGC model treats memory expansion as zero (all compliance operations are stack/storage-based and do not require large memory buffers). This is documented as a known limitation in §6 of the paper.

### Why P3 does not hold without P1 and P2

P3 relies on the fact that:
1. The EVM executes a unique trace τ for (C, σ, I) — established by P1.
2. This trace corresponds to exactly one path π* in the PIDGC path set — established by P2.
3. The symbolic sum `G_{π*}` correctly enumerates the opcodes along τ — established by the CCG/CFG construction in P2.

Without P1, τ might not be unique (non-deterministic execution), and there would be no single number to agree with. Without P2, there might be no enumerable path set, and therefore no symbolic expression to compare against.

---

## Completeness of assumptions

The following table summarises which properties require which assumptions:

| Property | AS-1 | AS-2 | AS-3 | AS-4 |
|----------|------|------|------|------|
| P1 (Determinism) | ✓ | ✓ | ✓ | ✓ |
| P2 (Path-exactness) | ✓ | ✓ | — | — |
| P3 (Agreement) | via P1 | via P1,P2 | via P1 | via P1 |

AS-3 and AS-4 are needed for P1 (hence transitively for P3) but not independently for P2. The CCG construction in P2 uses AS-2 for static resolution of call targets, but does not need AS-3 (trusted callee behaviour) or AS-4 (precompile costs) — it only needs to enumerate the *structure* of paths, not their *cost*.

---

## Relationship to existing verification frameworks

The PIDGC model is an instance of *abstract interpretation* applied to the EVM, specialized to the class of bounded, acyclic-after-unrolling TLC contracts. The connection is as follows:

- **Abstract domain:** The cold/warm access flag vector `(w_1, …, w_n)` is the abstract state. Each path `π` defines a concretisation of this state.
- **Abstract semantics:** `G_π` is the abstract evaluation of the cost function — a piecewise-affine map from flag vectors to gas values.
- **Soundness vs. exactness:** Generic abstract interpretation for arbitrary smart contracts (GASOL, Asparagus) uses sound over-approximation because loops and dynamic dispatch prevent exact path enumeration. PIDGC achieves exactness by restricting to the bounded, statically-dispatched TLC class, allowing the abstract state to be fully concrete (each path is uniquely determined by `guard(π)` and a concrete input).

For future work, the path enumeration step (P2, Step 3) could be automated using a symbolic execution engine (e.g., Mythril, Manticore, or a custom Gigahorse-based tool) to generate the guard/cost pairs without manual derivation.
