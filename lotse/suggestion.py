from typing import Any, Literal

from pydantic import BaseModel, Field


class SuggestionContent(BaseModel):
    """
    The `SuggestionContent` contains the actual suggestion value. The value can be any, arbitrary JSON-serializable
    data structure.
    """
    value: Any = Field(description="The actual value being suggested. The value can be any arbitrary JSON-serializable \
                                   data structure.")
    action_id: str = Field(description="The `action_id` as specified in the generating action's yaml file. Can be used \
     in the frontend application to filter which visualization components should receive suggestions from which \
      strategies or actions.")


class Suggestion(BaseModel):
    """
    The Suggestion class summarizes important information about a suggestion, such as the strategy that created it or
    the degree with which it is intended to be visualized. Furthermore, it contains the title and description of the
    suggestion and the actual `SuggestionContent`. Finally, each suggestion receives a unique ID.
    """
    title: str = Field(description="The title of the suggestion. This text field can be filled by actions generating \
     the suggestion and is intended to support the user by explaining or justifying the suggestion.")
    description: str = Field(description="The description of the suggestion. This text field can be filled by actions \
     generating the suggestion and is intended to support the user by explaining or justifying the suggestion.")
    id: str = Field(description="The globally unique ID of the suggestion")
    degree: str = Field(description="The guidance degree (orienting, directing, prescribing) with which the suggestion \
     is intended to be visualized.")
    event: SuggestionContent = Field(description="The actual `SuggestionContent`")
    strategy: str = Field(description="The ID (if defined, otherwise the name) of the strategy which generated this \
     suggestion.")


class SuggestionModel(BaseModel):
    """
    The SuggestionModel class is a wrapper around the actual suggestion, specifying its type (currently, always
    guidance), and the interaction that was performed on the suggestion.
    """
    suggestion: Suggestion = Field(description="The suggestion itself.")
    type: str = Field('guidance', description="Currently, only the type `guidance` is supported")
    interaction: Literal['make', 'accept', 'reject', 'preview start', 'preview end', 'retract'] = Field('make', description="The \
       interaction performed on the suggestion. The system will typically `make` or `retract` suggestions. Incoming \
        interactions from the frontend will typically `accept`, `reject` or `preview` the suggestion.")
    action: Any = Field(exclude=True)

    class Config:
        fields = {
            'action': {
                'exclude': True
            }
        }
