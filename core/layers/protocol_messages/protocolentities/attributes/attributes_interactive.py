from typing import Any
class InteractiveAttributes:
    def __init__(self, body, header=None,  footer=None, buttons=None) -> None:
        
        self._body = body
        self._header = header
        self._footer = footer
        self._buttons = buttons   

    @property
    def body(self) -> Any:
        return self._body

    @body.setter
    def text(self, value: Any) -> None:
        self._body = value

    @property
    def header(self) -> Any:
        return self._header

    @header.setter
    def header(self, value: Any) -> None:
        self._header = value


    @property
    def footer(self) -> Any:
        return self._footer

    @footer.setter
    def footer(self, value: Any) -> None:
        self._footer = value

    @property
    def buttons(self) -> Any:
        return self._buttons

    @buttons.setter
    def buttons(self, value: Any) -> None:
        self._buttons = value