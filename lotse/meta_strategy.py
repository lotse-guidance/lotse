from typing import List

from .action import ConditionalGuidanceAction
from .context import ContextVector


class MetaStrategy:
    metadata: dict

    def filter_actions(self, actions: List[ConditionalGuidanceAction], context: ContextVector):
        return actions
