"""As cinco regras aprovadas, com AND=min e OR=max.

Não usar NOT(low) para obter high: input ausente deve manter ambos em zero.
ADR 0013: nas regras de calma (R4/R5), desvio e ratio ausentes são neutros (1);
conflito e frequência continuam obrigatórios, e evidência presente e ruim barra a calma.
"""


def optional(m: dict[str, float]) -> float:
    return m["low"] if m["low"] + m["high"] > 0 else 1.0


def evaluate(memberships: dict[str, dict[str, float]]) -> dict[str, float]:
    c = memberships["conflict"]
    f = memberships["frequency"]
    d = memberships["deviation"]
    t = memberships["ratio"]
    r = memberships["reputation"]
    calm = min(c["low"], f["low"], optional(d), optional(t))
    anomalous = max(f["high"], d["high"], t["high"])
    return {
        "R1": c["high"],
        "R2": min(c["low"], anomalous, r["new"]),
        "R3": min(c["low"], anomalous, r["known"]),
        "R4": min(calm, r["new"]),
        "R5": min(calm, r["known"]),
    }
