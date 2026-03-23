from Reconfigurator.criteria.abstract import AbstractReconfigCriterion

class BasicReconfigCriterion(AbstractReconfigCriterion):
    def __init__(self, interval: int):
        assert interval >= 0, f"The interval to reconfig must be non-negative ({interval} < 0)"
        self.interval = interval
        super().__init__()

    def reset(self):
        self.num_sessions = 0

    def update(self, session):
        self.num_sessions += 1
        
    def should_reconfigure(self):
        return self.num_sessions >= self.interval