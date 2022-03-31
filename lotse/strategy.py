from typing import Callable, Literal, Any

from .context import ContextVector


class Strategy:
    condition: Callable[[ContextVector], bool]
    degree: Literal['orienting', 'directing', 'prescribing']
    name: str
    component: str
    metadata: dict
    action: Any

    def generate_actions(self):
        return [self.action]

    def determine_applicability(self, context: ContextVector, delta: dict) -> bool:
        return True
