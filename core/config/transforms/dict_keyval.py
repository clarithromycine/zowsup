from ...config.base.transform import ConfigTransform
from typing import Any, Optional, Dict, List, Tuple



class DictKeyValTransform(ConfigTransform):
    def transform(self, data) -> Any:
        """
        :param data:
        :type data: dict
        :return:
        :rtype:
        """
        out=[]
        keys = sorted(data.keys())
        for k in keys:
            out.append(f"{k}={data[k]}")
        return "\n".join(out)

    def reverse(self, data) -> Any:
        out = {}
        for l in data.split('\n'):
            line = l.strip()
            if len(line) and line[0] not in ('#',';'):
                prep = line.split('#', 1)[0].split(';', 1)[0].split('=', 1)
                varname = prep[0].strip()
                val = prep[1].strip()
                out[varname.replace('-', '_')] = val
        return out
