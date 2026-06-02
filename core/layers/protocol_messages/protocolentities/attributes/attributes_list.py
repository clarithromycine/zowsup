from typing import Any
class ListAttributes:
    def __init__(self, title, description,button_text,footer,list_content,context_info=None) -> None:
        self._title = title
        self._description = description
        self._footer = footer        
        self._button_text = button_text
        self._list_content = list_content
        self._context_info = context_info

    def __str__(self):
        attrs = []
        if self._title is not None:
            attrs.append(("title", self.title))
        if self._description is not None:
            attrs.append(("description", self.description))
        if self._footer is not None:
            attrs.append(("footer", self.footer))            
        if self._button_text is not None:
            attrs.append(("button_text", self.button_text))            
        if self._list_content is not None:
            attrs.append(("text", self.list_content))            
        if self._context_info is not None:
            attrs.append(("context_info", self._context_info))

        return "[%s]" % " ".join(map(lambda item: "%s=%s" % item, attrs))

    @property
    def title(self) -> Any:
        return self._title

    @title.setter
    def title(self, value: Any) -> None:
        self._title = value

    @property
    def description(self) -> Any:
        return self._description

    @description.setter
    def description(self, value: Any) -> None:
        self._description = value

    @property
    def footer(self) -> Any:
        return self._footer

    @footer.setter
    def footer(self, value: Any) -> None:
        self._footer = value

    @property
    def button_text(self) -> Any:
        return self._button_text

    @button_text.setter
    def button_text(self, value: Any) -> None:
        self._button_text = value        

    @property
    def list_content(self) -> Any:
        return self._list_content

    @list_content.setter
    def list_content(self, value: Any) -> None:
        self._list_content = value            
