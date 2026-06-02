import os,sys
sys.path.append(os.getcwd())

import  logging,time,inspect,traceback
from flask import Flask,request
from threading import Thread
from common.utils import Utils
from .api_result import ApiResult
from .api_exception import ApiException
import json

logger = logging.getLogger(__name__)

class ApiServer:

    def __init__(self,apiObj=None):           
        self.apiObj = apiObj
        self.accessKeyName = 'Cluster-Access-Key'
        self.accessKeyValue = None           #鎵€鏈夌殑api璁块棶閮借鍦╤eader浼犲叆杩欎釜key锛宎pi閴存潈, accessKey=None涓嶉壌鏉?
        self.thread = None
        self.flask = Flask(__name__)
        self.server = None
        self.apiList = self.initApi()           
        
         
    def setAccessKey(self,name,value):
        self.accessKeyName = name
        self.accessKeyValue = value
        return self     #鏂逛究閾惧紡璋冪敤
    
    def status(self):
        return ApiResult.success("SERVICE OK")
    
    def initApi(self):
        apiList = {}
        members = inspect.getmembers(self.apiObj.__class__, predicate = inspect.isfunction)     
        for m in members:            
            if hasattr(m[1], "desc"):  
                apiList[m[1].cmd] =  m[1]      
                                
        return apiList

    def listApi(self):        
        result = {}
        for key,value in self.apiList.items():
            result[key] = value.desc
        return ApiResult.success(data = result)
                
    def shutdown(self):
        if self.server is not None:
            self.server.stop()
            return ApiResult.success("SHUTDOWN OK")
        else:
            return ApiResult.fail(-1,"NOT SUPPORT")
                
    def objCall(self,apiname):    
        key = request.headers.get(self.accessKeyName)   
        if self.accessKeyValue is not None:
            if key is None or key!=self.accessKeyValue:
                return ApiResult.fail(code = 403,msg = "ACCESS DENIED")                
        try :    
            r = request.get_data()    
            inObj = json.loads(r) if r and len(r)>0 else {}
        except:
            inObj = {}
                        
        if apiname not in self.apiList:
            return ApiResult.fail(code = 404,msg = "API %s NOT FOUND" % apiname)            
        try:            
            outObj = self.apiList[apiname](self.apiObj,params = request.args,data = inObj)

            return ApiResult.success(outObj)
        except ApiException as e:
            return ApiResult.fail(e.getCode(),e.getMsg())
        except Exception as e:
            logger.error(traceback.format_exc())
            return ApiResult.fail(-999,"Command Exception:"+str(e))
        
    def runFlask(self,host,port,debug):        
        self.flask.route('/apis', methods=['GET','POST'])(self.listApi)    
        self.flask.route('/<path:apiname>', methods=['POST'])(self.objCall)
        self.flask.run(host=host,port=port,debug=debug,use_reloader=False)       
        #浠ヤ笅閮ㄥ垎锛岀ǔ瀹氫箣鍚庡彲浠ユ浛鎹㈡帀涓婁竴鍙elf.flask.run, 澧炲己绋冲畾鎬у拰骞跺彂
        #self.server = WSGIServer((host, port), self.flask)
        #self.server.serve_forever()        
    
    def run(self,host="0.0.0.0",port=5001,debug=False,background=False):
        if not background:
            return self.runFlask(host,port,debug)
        else: 
            self.thread = Thread(daemon=True,target=self.runFlask,args=(host,port,debug))
            self.thread.start()

if __name__ == "__main__":
    Utils.init_log(logging.INFO)
    server = ApiServer(None)    
    server.run(background=True)    
    while (True):
        print(".",end='',flush=True)
        time.sleep(1)