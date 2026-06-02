from typing import Any
class SenderKeyDistributionMessageAttributes:
    def __init__(self, group_id, axolotl_sender_key_distribution_message) -> None:
        self._group_id = group_id
        self._axolotl_sender_key_distribution_message = axolotl_sender_key_distribution_message

    def __str__(self):
        attrs = []
        if self.group_id is not None:
            attrs.append(("group_id", self.group_id))
        if self.axolotl_sender_key_distribution_message is not None:
            attrs.append(("axolotl_sender_key_distribution_message", "[binary omitted]"))

        return "[%s]" % " ".join(map(lambda item: "%s=%s" % item, attrs))

    @property
    def group_id(self) -> Any:
        return self._group_id

    @group_id.setter
    def group_id(self, value: Any) -> None:
        self._group_id = value

    @property
    def axolotl_sender_key_distribution_message(self) -> Any:
        return self._axolotl_sender_key_distribution_message

    @axolotl_sender_key_distribution_message.setter
    def axolotl_sender_key_distribution_message(self, value: Any) -> None:
        self._axolotl_sender_key_distribution_message = value
