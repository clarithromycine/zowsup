import json

class ApiResult:

    @staticmethod
    def success(data):
        if data is None:
            return json.dumps({
                "retcode":0
            },indent=4),200,[("Content-Type","application/json")]
        else:
            return json.dumps({
                "retcode":0,
                "data":data
            },indent=4),200,[("Content-Type","application/json")]
        
    @staticmethod
    def fail(code,msg):
        return json.dumps({
            "retcode":code,
            "msg":msg
        },indent=4)
