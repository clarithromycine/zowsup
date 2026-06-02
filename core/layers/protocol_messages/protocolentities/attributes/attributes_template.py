from typing import Any
class TemplateAttributes:
    def __init__(self, text, buttons = None) -> None:
        
        self._text = text
        self._buttons = buttons        

    def __str__(self):
        attrs = []        
        if self.text is not None:
            attrs.append(("text", self.text))
        if self.buttons is not None:
            attrs.append(("buttons", self.buttons))

        return "[%s]" % " ".join(map(lambda item: "%s=%s" % item, attrs))

    @property
    def text(self) -> Any:
        return self._text

    @text.setter
    def text(self, value: Any) -> None:
        self._text = value

    @property
    def buttons(self) -> Any:
        return self._buttons

    @buttons.setter
    def buttons(self, value: Any) -> None:
        self._buttons = value
