from ...config.base.transform import ConfigTransform
import json
from typing import Any, Optional, Dict, List, Tuple



class DictJsonTransform(ConfigTransform):
    def transform(self, data) -> Any:
        return json.dumps(data, sort_keys=True, indent=4, separators=(',', ': '))

    def reverse(self, data) -> Any:
        return json.loads(data)

