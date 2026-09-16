"""As cinco regras aprovadas, com AND=min e OR=max.

Não usar NOT(low) para obter high: input ausente deve manter ambos em zero.
"""


def evaluate(memberships: dict[str, dict[str, float]]) -> dict[str, float]:
    c = memberships["conflict"]
    f = memberships["frequency"]
    d = memberships["deviation"]
    t = memberships["ratio"]
    r = memberships["reputation"]
    anomalous = max(f["high"], d["high"], t["high"])
    return {
        "R1": c["high"],
        "R2": min(c["low"], anomalous, r["new"]),
        "R3": min(c["low"], anomalous, r["known"]),
        "R4": min(c["low"], f["low"], d["low"], t["low"], r["new"]),
        "R5": min(c["low"], f["low"], d["low"], t["low"], r["known"]),
    }
