"""The paired gate: decide whether an ontology edit ships.

McNemar's test on the discordant pairs, exactly as specified:
  b = parent wrong & candidate right
  c = parent right & candidate wrong

If b + c >= 10: exact two-sided binomial McNemar (math.comb, no scipy);
keep iff p < 0.05 AND b > c AND candidate accuracy > parent accuracy.
If b + c < 10: margin fallback; keep iff (b - c) >= 2 AND candidate
accuracy > parent accuracy.

With only 8 validation questions, b + c is always < 10, so the margin
fallback is what actually decides here — that is documented, not hidden.
"""
from __future__ import annotations

import math


def mcnemar_p_value(b: int, c: int) -> float:
    """Exact two-sided binomial p-value for McNemar's test.

    Under the null the discordant pairs split 50/50, so
    p = 2 * sum_{k=0}^{min(b,c)} C(b+c, k) * 0.5^(b+c).
    """
    n = b + c
    if n == 0:
        return 1.0
    k_max = min(b, c)
    tail = sum(math.comb(n, k) for k in range(k_max + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)


def decide_gate(b: int, c: int, parent_acc: float,
                candidate_acc: float) -> tuple[str, str, float | None]:
    """Return (decision, reason, p_value). decision is 'keep' or 'reject'."""
    n = b + c
    if n >= 10:
        p = mcnemar_p_value(b, c)
        if p < 0.05 and b > c and candidate_acc > parent_acc:
            return ("keep",
                    f"McNemar exact p={p:.4f} < 0.05, b={b} > c={c}", p)
        return ("reject",
                f"McNemar exact p={p:.4f} not significant "
                f"(need p < 0.05, b > c, higher accuracy)", p)
    # Margin fallback for small discordant counts.
    if (b - c) >= 2 and candidate_acc > parent_acc:
        return ("keep",
                f"margin fallback: b-c={b - c} >= 2 "
                f"(b={b}, c={c}, too few discordant pairs for McNemar)", None)
    return ("reject",
            f"margin fallback: b-c={b - c} < 2 "
            f"(b={b}, c={c}, too few discordant pairs for McNemar)", None)
