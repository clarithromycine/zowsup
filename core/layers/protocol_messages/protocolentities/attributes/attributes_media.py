from .....layers.protocol_messages.protocolentities.attributes.attributes_context_info import ContextInfoAttributes
from typing import Optional, Any, List, Dict, Union


class MediaAttributes:
    def __init__(self, context_info=None) -> None:
        """
        :type context_info: ContextInfo | None
        """
        if context_info:
            assert type(context_info) is ContextInfoAttributes, type(context_info)
            self._context_info = context_info  # type: ContextInfoAttributes | None
        else:
            self._context_info = None

    @property
    def context_info(self) -> Any:
        return self._context_info

    @context_info.setter
    def context_info(self, value: Any) -> None:
        assert type(value) is ContextInfoAttributes, type(value)
        self._context_info = value
