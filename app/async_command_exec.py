import os, sys
sys.path.append(os.getcwd())

import logging
import json
import inspect
import asyncio
from conf.constants import SysVar

logger = logging.getLogger(__name__)


class AsyncCommandExec:


    def __init__(self, bot, cmd_args, options):
        """
        Args:
            bot: ZowBot 实例
            cmd_args: 命令和参数列表，e.g., ["msg.send", "recipient", "hello"]
            options: 命令选项字典
        """
        self.bot = bot
        self.cmd_args = cmd_args
        self.options = options

    async def run(self):
        """
        异步执行命令流程：
        1. 等待 bot 登录成功（非阻塞）
        2. 执行指定命令
        3. 返回结果后主程序可以退出
        """
        if not self.cmd_args:
            logger.error("No command specified")
            return False

        cmd_name = self.cmd_args[0]
        cmd_args = self.cmd_args[1:] if len(self.cmd_args) > 1 else []

        logger.info(f"Waiting for BOT {self.bot.botId} to login...")

        # 等待登录 - 这里使用异步方式，不阻塞 event loop
        if not await self._wait_login_async():
            logger.error(f"BOT {self.bot.botId} login timeout or failed")
            return False

        if self.bot.botLayer.detect40x:
            logger.error(f"BOT {self.bot.botId} login failed (40x error)")
            return False

        logger.info(f"BOT {self.bot.botId} ready, executing command: {cmd_name}")

        # 根据命令类型执行
        await self._execute_command(cmd_name, cmd_args)        

        self.bot.disconnect() #执行完命令后断开连接，主程序可以退出
        return True        

    async def _wait_login_async(self, timeout=30):
        """
        异步等待登录 - 非阻塞方式
        使用 asyncio.wait_for 和 asyncio.sleep 轮询
        """
        start_time = asyncio.get_event_loop().time()

        while True:

            if self.bot.botLayer.loginEvent.is_set():
                return True
            
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                return False

            # 非阻塞休眠，给其他任务运行的机会
            await asyncio.sleep(0.1)

    async def _execute_command(self, cmd_name, cmd_args):

        # 根据命令类型确定等待时间
        wait_time = self._get_wait_time(cmd_name)

        try:
            fn = self.bot.cmdList.get(cmd_name)
            if not fn:
                logger.error(f"Command '{cmd_name}' not found")
                return False
            
            result = await fn(cmd_args, self.options)
            if result == "JUSTWAIT":
                logger.info(f"Command waiting {wait_time} seconds...")
                await asyncio.sleep(wait_time)
                logger.info("Command complete")
            else:
                logger.info(f"Command '{cmd_name}' complete, result={json.dumps(result)}")
            return True

        except Exception as e:
            logger.error(f"Command '{cmd_name}' exception: {e}", exc_info=True)
            return False

    def _get_wait_time(self, cmd_name):
        """根据命令类型返回等待时间"""
        if cmd_name == "init":
            return 10
        elif cmd_name == "mdlink":
            return 60
        else:
            return 20

        # 允许通过配置覆盖
        return SysVar.CMD_WAIT if SysVar.CMD_WAIT is not None else 20
