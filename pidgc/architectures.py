"""PIDGC — closed-form per-architecture cost expressions .

Each `G_<letter>_transfer` returns the predicted per-transfer gas under the
Shanghai/Cancun schedule, parameterised by warmth and the minimal architecture-
specific parameter set identified in §5 of the paper.

All values are pre-refund; subtract min(R(τ), G/5) externally if modelling a
refund-bearing revert or slot-zeroing path.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

from . import constants as C

Warmth = Literal["cold", "warm"]


def _sload(warmth: Warmth) -> int:
    return C.SLOAD_COLD if warmth == "cold" else C.SLOAD_WARM


def _call(warmth: Warmth) -> int:
    return C.CALL_COLD if warmth == "cold" else C.CALL_WARM


# ------------------------------------------------------------------
# A — Blocklist (USDC, USDT-like shape)
# G_A = G_ERC20_core + 2·SLOAD + 2·JUMPI
# ------------------------------------------------------------------
def G_A_transfer(warmth: Warmth = "warm") -> int:
    return C.G_ERC20_CORE + 2 * _sload(warmth) + 2 * C.JUMPI


# B — Allowlist (ERC-1404). Identical shape to A.
def G_B_transfer(warmth: Warmth = "warm") -> int:
    return G_A_transfer(warmth)


# ------------------------------------------------------------------
# G — Shared compliance oracle (Chainalysis / EAS)
# G_G = G_ERC20_core + 2·(CALL + SLOAD) + 2·JUMPI
# Two parties (sender, recipient) each STATICCALL the oracle, which itself
# performs one SLOAD on its own storage.
# ------------------------------------------------------------------
def G_G_transfer(warmth: Warmth = "warm") -> int:
    return C.G_ERC20_CORE + 2 * (_call(warmth) + _sload(warmth)) + 2 * C.JUMPI


# ------------------------------------------------------------------
# C — ERC-3643 / T-REX. Multi-registry fan-out parameterised by:
#   T = #claim topics required
#   U = #users in the claim path (typically 1, rises on transferFrom)
#   k_rules = #compliance rules (cap, countries, ...)
# ------------------------------------------------------------------
def G_C_transfer(warmth: Warmth = "warm", T: int = 2, U: int = 1,
                 k_rules: int = 2) -> int:
    call = _call(warmth)
    sload = _sload(warmth)
    # IdentityRegistry lookup (lookup + claimTopics + countries)
    identity_registry = call + 2 * sload
    # ClaimTopicsRegistry
    claim_topics_registry = call + sload
    # Per-topic: TrustedIssuersRegistry + OnchainID + claim SLOAD +
    # issuer STATICCALL + signature verification (ECRECOVER)
    per_topic = (call            # TrustedIssuersRegistry
                 + U * sload     # U·SLOAD in TIR (users in claim path)
                 + call          # OnchainID
                 + sload         # claim
                 + call          # issuer
                 + C.ECRECOVER)
    compliance = call + k_rules * sload
    return (C.G_ERC20_CORE
            + identity_registry
            + claim_topics_registry
            + T * per_topic
            + compliance)


# ------------------------------------------------------------------
# E — Partitioned (ERC-1400 / ERC-7518). Parameterised by p = #partitions.
# G_E = G_ERC20_core + SLOAD_list + p·(2·SLOAD + policy_eval)
# policy_eval ≈ 3 opcodes (ISZERO + JUMPI + small arith) per partition.
# ------------------------------------------------------------------
def G_E_transfer(warmth: Warmth = "warm", p: int = 3,
                 policy_eval_per_partition: int = 50) -> int:
    sload = _sload(warmth)
    list_read = sload  # partition list head
    per_partition = 2 * sload + policy_eval_per_partition
    return C.G_ERC20_CORE + list_read + p * per_partition


# ------------------------------------------------------------------
# F — zkKYC (Groth16 verifier).
# G_F = G_ERC20_core + G_calldata(π) + CALL_Verifier + ECPAIRING(k)
#        + ECMUL·m + ECADD·n + SLOAD·x
# Defaults to Groth16: k=3 pairs, m=~6 scalar-muls, n=~10 adds, x=3 sloads
# (verifying key layout), proof π ≈ 8 field elements = 256 nonzero calldata bytes.
# ------------------------------------------------------------------
def G_F_transfer(warmth: Warmth = "warm", k_pairs: int = 3,
                 m_ecmul: int = 4, n_ecadd: int = 5,
                 x_sload: int = 1,
                 proof_nonzero_bytes: int = 224,
                 proof_zero_bytes: int = 0) -> int:
    sload = _sload(warmth)
    call = _call(warmth)
    return (C.G_ERC20_CORE
            + C.G_calldata(proof_zero_bytes, proof_nonzero_bytes)
            + call                         # verifier contract call
            + C.ECPAIRING(k_pairs)
            + C.ECMUL * m_ecmul
            + C.ECADD * n_ecadd
            + sload * x_sload)


# ------------------------------------------------------------------
# OUT OF PAPER"S SCOPE
# D — ERC-7943 (uRWA) adapter overlay.
# ΔG_D = k_read·SLOAD + k_logic·3 + JUMPI
# D is not a standalone architecture; it is an interface overlay.
# D-on-X cost = X cost + ΔG_D.
# ------------------------------------------------------------------
def dG_D_adapter(warmth: Warmth = "warm", k_read: int = 2,
                 k_logic: int = 3) -> int:
    return k_read * _sload(warmth) + k_logic * 3 + C.JUMPI


def G_D_on(base_arch: str, warmth: Warmth = "warm", **kwargs) -> int:
    """D-on-X for X in {A, B, C, E, F, G}."""
    table = {
        "A": G_A_transfer,
        "B": G_B_transfer,
        "C": G_C_transfer,
        "E": G_E_transfer,
        "F": G_F_transfer,
        "G": G_G_transfer,
    }
    if base_arch not in table:
        raise ValueError(f"unknown base architecture {base_arch!r}")
    base = table[base_arch](warmth=warmth, **kwargs)
    return base + dG_D_adapter(warmth=warmth)


@dataclass(frozen=True)
class Prediction:
    arch: str
    warmth: str
    params: dict
    gas: int
    compliance_overhead: int

    def __str__(self) -> str:
        p = ", ".join(f"{k}={v}" for k, v in self.params.items()) or "—"
        return (f"{self.arch:18s} {self.warmth:4s}  gas={self.gas:>7d}  "
                f"overhead={self.compliance_overhead:>7d}  [{p}]")


def predict(arch: str, warmth: Warmth = "warm", **kwargs) -> Prediction:
    """Dispatch to the right G_<arch>_transfer and wrap in a Prediction."""
    arch_upper = arch.upper()
    if arch_upper.startswith("D-ON-"):
        base = arch_upper.split("-ON-", 1)[1]
        gas = G_D_on(base, warmth=warmth, **kwargs)
    else:
        fn = {
            "A": G_A_transfer,
            "B": G_B_transfer,
            "C": G_C_transfer,
            "E": G_E_transfer,
            "F": G_F_transfer,
            "G": G_G_transfer,
        }[arch_upper]
        gas = fn(warmth=warmth, **kwargs)
    return Prediction(
        arch=arch_upper,
        warmth=warmth,
        params=dict(kwargs),
        gas=gas,
        compliance_overhead=gas - C.G_ERC20_CORE,
    )
