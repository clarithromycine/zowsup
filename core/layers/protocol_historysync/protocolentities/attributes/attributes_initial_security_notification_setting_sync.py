from typing import Any
class InitialSecurityNotificationSettingSyncAttribute:
    def __init__(self, security_notification_enabled=True) -> None:
        self._security_notification_enabled = security_notification_enabled

    @property
    def security_notification_enabled(self) -> Any:
        return self._security_notification_enabled

    @security_notification_enabled.setter
    def security_notification_enabled(self, value: Any) -> None:
        self._security_notification_enabled = value


