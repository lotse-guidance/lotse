import uuid
from typing import Callable, Union

from .context import ContextVector
from .strategy import Strategy
from .suggestion import SuggestionContent, Suggestion, SuggestionModel


class ConditionalGuidanceAction:
    """
    Conditional guidance action class.
    TODO: finalize docs
    """

    # The metadata object can hold arbitraty metadata about the conditional action.
    # The demonstrator uses metadata to store unique guidance action ids. Those ids
    # will be used in the frontend to determine what to do with new guidance suggestions
    metadata: dict
    # whether a suggestion has been made from this action or not
    suggested = False

    def __init__(self, strategy: Strategy, condition: Callable[[ContextVector], bool]):
        """
        The constructor takes two mandatory parameters:

        :param strategy: The guidance strategy that produced this conditional action.
        :param condition: the condition(s) under which this action should generate suggestions.
        """
        self.condition = condition
        self.strategy = strategy

    def accept(self, suggestion, context, delta: dict):
        """
        Accept the suggestion. Potential things to do:
        - update data models
        - update rule sets to initiate adaptation
        """
        pass

    def reject(self, suggestion, context, delta: dict):
        """
        Reject the suggestion. Potential things to do:
        - update data models
        - update rule sets to initiate adaptation
        """
        pass

    def preview_start(self, suggestion, context, delta: dict):
        """
        Called when users start to preview the suggestion.
        """
        raise NotImplementedError

    def preview_end(self, suggestion, context, delta: dict):
        """
        Called when users start to preview the suggestion.
        """
        raise NotImplementedError

    def is_applicable(self, context: ContextVector, delta: dict) -> bool:
        """
        Determines whether the action should produce new suggestions in the current context based on the current condition(s).

        :param context: The context on which to verify the conditions
        :param delta: The delta to the last context vector that was passed for evaluation. Can be None.
        :return: True if the action should generate suggestions in the given context
        """
        pass

    def should_retract(self, context: ContextVector, delta: dict, suggestion: SuggestionModel) -> bool:
        """
        Determines whether the given suggestion should be retracted given the current context vector.

        :param context: The context on which to verify a potential retract
        :param delta: The context delta
        :param suggestion: The suggestion to potentially retract
        :return: True if the suggestion should be retracted.
        """
        pass

    def retract(self, context: ContextVector, delta: dict, suggestion: SuggestionModel):
        """
        A callback that you can define to override what should happen when suggestions are retracted.

        :param context: The context in which the suggestion was retracted
        :param delta: The context delta
        :param suggestion: the rectracted suggestion
        """
        pass

    def generate_suggestions(self, context: ContextVector) -> Union[None, SuggestionModel]:
        """
        Generate new suggestions, potentially conditioned on the current context.
        This method is automatically called by the guidance engine.
        To modifiy the content of generated suggestions, see `generate_suggestion_content`.

        :param context: The current Analysis Context
        :return: a new suggestion
        """
        try:
            content, title, desc = self.generate_suggestion_content(context)
        except Exception as e:
            print(str(e))
            print("did not get enough suggestion content, return none")
            return None

        print('generating new sugg')
        print(content, title, desc)
        content = SuggestionContent(action_id=self.metadata.get('action_id', ''), value=content)
        suggestion = Suggestion(title=title,
                                description=desc,
                                id=str(uuid.uuid4()),
                                degree=self.metadata.get('degree', ''),
                                event=content,
                                strategy=self.strategy.metadata.get('strategy_id',
                                                                    self.strategy.metadata.get('strategy')))
        return SuggestionModel(suggestion=suggestion, action=self)

    def generate_suggestion_content(self, context: ContextVector) -> (any, str, str):
        """
        Generates the content of new suggestions.
        This method is called by `generate_suggestions` and can be implemented in the yaml files.

        :param context: the current analysis context.
        :return: (content, title, description). `Content` can be any arbitrary python object that can be natively json-
        serialized. Title and description are strings that should summarize, justify or explain the suggestion and can
        be visualized in the frontend.
        """
        return None, "", ""
