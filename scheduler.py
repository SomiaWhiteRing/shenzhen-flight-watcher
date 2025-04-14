import asyncio
import time
import subprocess
import logging
from datetime import datetime, timedelta

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("scheduler.log")
    ]
)

# 脚本路径
SCRIPT_PATH = "D:\\NetDisk\\OneDrive\\文档\\GitHub\\airplane-watcher\\monitor.py"

async def run_monitor():
    """执行监控脚本"""
    try:
        logging.info("开始执行监控脚本...")
        # 使用subprocess执行Python脚本
        process = subprocess.Popen(
            ["python", SCRIPT_PATH],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            logging.info("监控脚本执行成功")
        else:
            logging.error(f"监控脚本执行失败，返回码：{process.returncode}")
            if stdout:
                logging.info(f"输出: {stdout}")
            if stderr:
                logging.error(f"错误: {stderr}")
    except Exception as e:
        logging.error(f"执行监控脚本时发生错误: {e}")

async def main():
    """主函数，每30分钟执行一次监控脚本"""
    logging.info("调度器已启动")
    
    while True:
        # 获取当前时间
        now = datetime.now()
        
        # 计算下一个整点或半点时间
        if now.minute < 30:
            next_run = now.replace(minute=30, second=0, microsecond=0)
        else:
            next_run = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
        
        # 计算等待时间
        wait_seconds = (next_run - now).total_seconds()
        if wait_seconds <= 0:
            wait_seconds = 1  # 避免负数，至少等待1秒
        
        logging.info(f"下次执行时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')}, 等待 {wait_seconds:.1f} 秒")
        
        # 等待到下一个执行时间
        await asyncio.sleep(wait_seconds)
        
        # 执行监控脚本
        await run_monitor()

if __name__ == "__main__":
    asyncio.run(main())