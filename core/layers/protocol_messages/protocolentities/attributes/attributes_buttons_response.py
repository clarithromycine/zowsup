from typing import Any
class ButtonsResponseAttributes:
    def __init__(self, selected_button_id, selected_display_text, type=1,context_info=None) -> None:
        self._selected_button_id = selected_button_id
        self._selected_display_text = selected_display_text
        self._type = type        
        self._context_info = context_info

    def __str__(self):
        attrs = []
        if self._selected_button_id is not None:
            attrs.append(("selected_button_id", self.selected_button_id))
        if self._selected_display_text is not None:
            attrs.append(("selected_display_text", self.selected_display_text))
        if self._type is not None:
            attrs.append(("type", self.type))            

        if self._context_info is not None:
            attrs.append(("context_info", self._context_info))

        return "[%s]" % " ".join(map(lambda item: "%s=%s" % item, attrs))

    @property
    def selected_button_id(self) -> Any:
        return self._selected_button_id

    @selected_button_id.setter
    def selected_button_id(self, value: Any) -> None:
        self._selected_button_id = value

    @property
    def selected_display_text(self) -> Any:
        return self._selected_display_text

    @selected_display_text.setter
    def selected_display_text(self, value: Any) -> None:
        self._selected_display_text = value

    @property
    def type(self) -> Any:
        return self._type

    @type.setter
    def type(self, value: Any) -> None:
        self._type = value