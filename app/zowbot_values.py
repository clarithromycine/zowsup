from typing import Any, Optional, Dict, List, Tuple, Union, Callable
class ZowBotType() :
    TYPE_REG_COMPANION_SCANQR      = "REG_COMPANION_SCANQR"       #扫码注册副机模式，  等待指令，执行完注册流程就结束    
    TYPE_REG_COMPANION_LINKCODE    = "REG_COMPANION_LINKCODE"     #配对码注册副机模式，  等待指令，执行完注册流程就结束      
    TYPE_RUN_IN_CLUSTER            = "RUN_IN_CLUSTER"             #集群模式运行，登录退出均由集群控制，登录后啥也不干，通过集群指令完成功能
    TYPE_RUN_SINGLETON             = "RUN_SINGLETON"              #单号运行模式，使用Main运行方式，使用控制台交互式指令完成功能
    TYPE_RUN_TEMP                  = "RUN_TEMP"                   #临时运行，通常是登录一个号码完成某种操作，账号目录也是放在临时目录，不会保留        
class ZowBotStatus():
    STATUS_UNKNOWN         = "UNKNOWN"
    STATUS_INITIAL         = "INITIAL"
    STATUS_RUNNING         = "RUNNING"
    STATUS_STOPPING        = "STOPPING"        
    STATUS_STOPPED         = "STOPPED"      
    STATUS_ERROR           = "ERROR"