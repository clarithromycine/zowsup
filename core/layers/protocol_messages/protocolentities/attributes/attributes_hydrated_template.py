from typing import Any
class HydratedTemplateAttributes:
    def __init__(self, hydrated_content_text,hydrated_buttons) -> None:
        self._hydrated_content_text = hydrated_content_text
        self._hydrated_buttons = hydrated_buttons        
        
    def __str__(self):
        attrs = []
        if self._hydrated_content_text is not None:
            attrs.append(("hydrated_content_text", self._hydrated_content_text))
        if self._hydrated_buttons is not None:                          
            attrs.append(("hydrated_buttons", self._hydrated_buttons))        
        
        return "[%s]" % " ".join(map(lambda item: "%s=%s" % item, attrs))

    @property
    def hydrated_content_text(self) -> Any:
        return self._hydrated_content_text

    @hydrated_content_text.setter
    def hydrated_content_text(self, value: Any) -> None:        
        self._hydrated_content_text = value

    @property
    def hydrated_buttons(self) -> Any:
        return self._hydrated_buttons

    @hydrated_buttons.setter
    def hydrated_buttons(self, value: Any) -> None:        
        self._hydrated_buttons = value