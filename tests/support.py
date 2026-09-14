"""Providers determinísticos, apenas para testes; nenhuma implementação de banco."""
class FixedReputation:
    def __init__(self, values):
        self.values = values

    def get_reputation(self, mac):
        return self.values.get(mac)


class FixedBaseline:
    def __init__(self, values):
        self.values = values

    def get_baseline_bps(self, mac):
        return self.values.get(mac)
