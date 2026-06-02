from typing import Any
class ListResponseAttributes:
    def __init__(self, selected_row_id, title, list_type=1,context_info=None) -> None:
        self._selected_row_id = selected_row_id
        self._title = title
        self._list_type = list_type        
        self._context_info = context_info

    def __str__(self):
        attrs = []
        if self._selected_row_id is not None:
            attrs.append(("selected_row_id", self.selected_row_id))
        if self._title is not None:
            attrs.append(("title", self.title))
        if self._list_type is not None:
            attrs.append(("list_type", self.list_type))            

        if self._context_info is not None:
            attrs.append(("context_info", self._context_info))

        return "[%s]" % " ".join(map(lambda item: "%s=%s" % item, attrs))

    @property
    def selected_row_id(self) -> Any:
        return self._selected_row_id

    @selected_row_id.setter
    def selected_row_id(self, value: Any) -> None:
        self._selected_row_id = value

    @property
    def title(self) -> Any:
        return self._title

    @title.setter
    def title(self, value: Any) -> None:
        self._title = value

    @property
    def list_type(self) -> Any:
        return self._list_type

    @list_type.setter
    def list_type(self, value: Any) -> None:
        self._list_type = value