"""PIDGC — Yellow-Paper opcode schedule (Shanghai/Cancun).

All constants pinned to the schedule cited in the paper.
A future hardfork changes these; re-evaluate PIDGC at each fork .
"""

from __future__ import annotations

# Storage access (EIP-2929, EIP-2930)
SLOAD_COLD = 2_100
SLOAD_WARM = 100
SSTORE_SET = 20_000          # zero -> non-zero
SSTORE_RESET_WARM = 2_900    # non-zero -> non-zero (warm)
SSTORE_RESET_COLD = 5_000    # includes cold surcharge
SSTORE_REFUND = 4_800        # non-zero -> zero (post-EIP-3529)

# External calls (EIP-2929)
CALL_COLD = 2_600
CALL_WARM = 100
STATICCALL_COLD = 2_600
STATICCALL_WARM = 100

# Control flow
JUMPI = 10
PUSH = 3
DUP = 3
MSTORE = 3
ISZERO = 3
EQ = 3

# Logs
LOG_BASE = 375
LOG_TOPIC = 375
LOG_DATA_BYTE = 8

def LOG3(data_len_bytes: int) -> int:
    """LOG3: 3 topics; gas = 1875 + 8·len."""
    return LOG_BASE + 3 * LOG_TOPIC + LOG_DATA_BYTE * data_len_bytes

# Precompiles (EIP-1108 / Cancun schedule)
ECRECOVER = 3_000
ECADD = 150
ECMUL = 6_000

def ECPAIRING(k: int) -> int:
    """BN254 pairing: 45_000 base + 34_000 per pair (EIP-1108)."""
    return 45_000 + 34_000 * k

# Calldata
CALLDATA_ZERO_BYTE = 4
CALLDATA_NONZERO_BYTE = 16

def G_calldata(zero_bytes: int, nonzero_bytes: int) -> int:
    return CALLDATA_ZERO_BYTE * zero_bytes + CALLDATA_NONZERO_BYTE * nonzero_bytes

# Intrinsic + ERC-20 core (measured baseline, §4.6)
INTRINSIC_TX = 21_000
G_ERC20_CORE = 48_000  # baseline ERC-20 transfer without compliance

# Refund cap (EIP-3529)
REFUND_DIVISOR = 5
