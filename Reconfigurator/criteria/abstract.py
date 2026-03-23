from abc import ABC, abstractmethod
from typing import Dict, Any

class AbstractReconfigCriterion(ABC):
    def __init__(self):
        self.reset()
    
    @abstractmethod
    def reset(self):
        ...

    @abstractmethod
    def update(self, session: Dict[str, Any]):
        ...

    @abstractmethod
    def should_reconfigure(self) -> bool:
        ...