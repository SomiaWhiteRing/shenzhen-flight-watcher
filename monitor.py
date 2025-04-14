import requests
import os
import json
import logging
from bs4 import BeautifulSoup
import sys
from typing import Optional, Dict, Any
import asyncio
# 导入 Playwright 相关模块
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError

# --- 配置日志记录 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
# logging.getLogger('playwright').setLevel(logging.DEBUG)

# --- 全局变量和配置 ---
PUSHPLUS_API_URL = "https://www.pushplus.plus/send"
PLAYWRIGHT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36'
CONFIG_FILE_LOCAL = "config.local.json"
SCREENSHOT_PATH = "debug_screenshot.png"
BASE_URL = "https://www.shenzhenair.com/"
MAX_RETRIES = 1
RETRY_DELAY = 5
# --- 增加超时时间 ---
GOTO_TIMEOUT_BASE = 120000 # 120 seconds for base URL
GOTO_TIMEOUT_TARGET = 150000 # 150 seconds for target URL
WAIT_FOR_CONTAINER_TIMEOUT = 60000 # 60 seconds
WAIT_FOR_ROW_TIMEOUT = 30000 # 30 seconds
# --- 超时设置结束 ---

# --- 检测是否在 GitHub Actions 环境 ---
IS_GITHUB_ACTIONS = os.environ.get('GITHUB_ACTIONS') == 'true'

# --- 函数定义 ---

def load_config() -> Optional[Dict[str, Any]]:
    """ 加载配置 """
    config = {}
    config['PUSHPLUS_TOKEN'] = os.environ.get('PUSHPLUS_TOKEN')
    config['FLIGHT_NUMBER'] = os.environ.get('FLIGHT_NUMBER')
    config['TARGET_URL'] = os.environ.get('TARGET_URL')

    if not IS_GITHUB_ACTIONS and os.path.exists(CONFIG_FILE_LOCAL):
         logging.info(f"本地环境，尝试从 {CONFIG_FILE_LOCAL} 加载或补充配置...")
         try:
             with open(CONFIG_FILE_LOCAL, 'r', encoding='utf-8') as f: local_config = json.load(f)
             config['PUSHPLUS_TOKEN'] = config['PUSHPLUS_TOKEN'] or local_config.get('PUSHPLUS_TOKEN')
             config['FLIGHT_NUMBER'] = config['FLIGHT_NUMBER'] or local_config.get('FLIGHT_NUMBER')
             config['TARGET_URL'] = config['TARGET_URL'] or local_config.get('TARGET_URL')
             logging.info(f"成功从 {CONFIG_FILE_LOCAL} 加载或补充配置。")
         except Exception as e: logging.error(f"读取本地配置文件 {CONFIG_FILE_LOCAL} 时出错: {e}"); return None
    elif not all(v for k, v in config.items() if k in ['PUSHPLUS_TOKEN', 'FLIGHT_NUMBER', 'TARGET_URL']):
         if not IS_GITHUB_ACTIONS: logging.warning(f"本地配置文件 {CONFIG_FILE_LOCAL} 不存在，将依赖环境变量。")
         else: logging.info("GitHub Actions 环境，依赖环境变量或 Secrets。")

    if not config.get('PUSHPLUS_TOKEN'): logging.error("错误：未找到 PUSHPLUS_TOKEN"); return None
    if not config.get('FLIGHT_NUMBER'): logging.error("错误：未找到 FLIGHT_NUMBER"); return None
    if not config.get('TARGET_URL'): logging.error("错误：未找到 TARGET_URL"); return None
    if config['PUSHPLUS_TOKEN'] == "你的PushPlus Token" or config['PUSHPLUS_TOKEN'] == "******":
        logging.error("错误：PushPlus Token 使用了示例值，请配置你自己的有效 Token。")
        return None

    logging.info("配置加载成功。")
    return config

async def fetch_html_with_playwright(target_url: str, base_url: str) -> Optional[str]:
    """ 使用 Playwright 获取 HTML, 先访问首页 """
    logging.info(f"使用 Playwright 抓取，先访问首页: {base_url}，再访问目标: {target_url}")
    html_content = None
    console_messages = []

    async with async_playwright() as p:
        browser = None
        context = None
        page = None
        response = None
        try:
            run_headless = IS_GITHUB_ACTIONS
            browser = await p.chromium.launch(
                headless=run_headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-infobars',
                    '--disable-dev-shm-usage', # Often needed in CI/Docker
                    '--window-position=-10000,0',
                ]
            )
            logging.info(f"Playwright Chromium 浏览器已启动 (Headless: {run_headless})。")

            context = await browser.new_context(
                user_agent=PLAYWRIGHT_USER_AGENT,
                java_script_enabled=True,
                ignore_https_errors=True,
                # --- 添加额外的请求头 ---
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7', # 优先使用中文
                    'Accept-Encoding': 'gzip, deflate, br', # Playwright通常会自动处理压缩，显式添加可能无害
                    'Sec-CH-UA': '"Chromium";v="1XX", "Not(A:Brand";v="99", "Google Chrome";v="1XX"', # XX替换为你的Chrome版本，或者用Playwright的默认值，或者省略
                    'Sec-CH-UA-Mobile': '?0',
                    'Sec-CH-UA-Platform': '"Windows"', # GitHub Actions是Linux环境，或者改为'"Windows"'如果你想模拟Windows
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'same-origin', # 从首页到搜索页是 same-origin
                    'Sec-Fetch-User': '?1',
                    'Upgrade-Insecure-Requests': '1'
                }
                # --- 添加结束 ---
            )
            page = await context.new_page()
            page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"))
            logging.info("已设置控制台消息捕获。")

            # --- 步骤 1: 访问基础域名 ---
            logging.info(f"步骤 1: 访问基础域名: {base_url}")
            base_visit_success = False
            try:
                # --- 使用增加后的超时时间 ---
                await page.goto(base_url, timeout=GOTO_TIMEOUT_BASE, wait_until='load')
                logging.info(f"成功访问基础域名，等待 5 秒让脚本执行...")
                await asyncio.sleep(5)
                cookies = await context.cookies()
                logging.info(f"访问首页后获取到的 Cookies: {[c['name'] for c in cookies]}")
                base_visit_success = True
            except Exception as base_e:
                logging.error(f"访问基础域名 {base_url} 失败: {base_e}")
                try: await page.screenshot(path="debug_base_url_fail.png")
                except: pass
                logging.info("已截屏保存基础域名访问失败状态。")
                # return None # 基础域名访问失败则直接退出
                # --- 修改：即使基础访问失败，也尝试继续访问目标URL，以获取更多信息 ---
                logging.warning("基础域名访问失败，但仍将尝试访问目标 URL...")

            # --- 步骤 2: 导航到目标 URL (仅当基础访问成功或选择继续时执行) ---
            # if base_visit_success: # 可以取消注释，如果基础失败就不继续
            target_nav_success = False
            for attempt in range(MAX_RETRIES + 1):
                try:
                    logging.info(f"步骤 2: 导航到目标 URL (尝试 {attempt + 1}/{MAX_RETRIES + 1}): {target_url}")
                    # --- 使用增加后的超时时间 ---
                    # response = await page.goto(target_url, timeout=GOTO_TIMEOUT_TARGET, wait_until='domcontentloaded')
                    response = await page.goto(target_url, timeout=GOTO_TIMEOUT_TARGET, wait_until='networkidle')
                    if response:
                        logging.info(f"目标 URL 导航成功，响应状态码: {response.status}")
                        if response.ok:
                             target_nav_success = True
                             break
                        else:
                             logging.warning(f"导航成功但状态码为 {response.status}...")
                    else:
                        logging.warning(f"导航未抛出异常但没有收到响应对象...")

                except (PlaywrightTimeoutError, PlaywrightError) as e:
                    logging.error(f"目标 URL 导航尝试 {attempt + 1} 失败: {e}")
                    if response: logging.error(f"失败时的响应状态: {response.status}")
                    if attempt >= MAX_RETRIES:
                        logging.error("达到最大重试次数，目标 URL 导航失败。")
                        try: await page.screenshot(path=SCREENSHOT_PATH); logging.info(f"已截屏保存目标URL导航失败状态 {SCREENSHOT_PATH}")
                        except: pass
                        return None # 重试完还失败，则退出

                # 仅在未成功且未达到最大次数时等待
                if not target_nav_success and attempt < MAX_RETRIES:
                     logging.info(f"将在 {RETRY_DELAY} 秒后重试...")
                     await asyncio.sleep(RETRY_DELAY)

            if not target_nav_success:
                 logging.error(f"目标 URL 导航重试后最终失败。")
                 return None

            logging.info("目标 URL 导航成功，开始等待页面内容...")
            # --- 等待航班列表容器出现 ---
            container_selector = '#flightInfoListDC'
            wait_selector = f'{container_selector} table.tblRouteList tr.flightTr'
            try:
                 # --- 使用增加后的超时时间 ---
                 await page.wait_for_selector(container_selector, state='visible', timeout=WAIT_FOR_CONTAINER_TIMEOUT)
                 logging.info(f"容器元素 '{container_selector}' 已可见。")
                 try:
                     await page.wait_for_selector(wait_selector, state='attached', timeout=WAIT_FOR_ROW_TIMEOUT)
                     logging.info(f"具体航班行元素 '{wait_selector}' 已找到。")
                 except PlaywrightTimeoutError:
                     logging.warning(f"容器已出现，但等待具体航班行 '{wait_selector}' 超时。")

                 await page.screenshot(path=SCREENSHOT_PATH)
                 logging.info(f"已截屏保存至 {SCREENSHOT_PATH}。")
                 html_content = await page.content()
                 logging.info("成功获取页面渲染后的 HTML 内容。")

            except PlaywrightTimeoutError:
                 logging.error(f"等待容器元素 '{container_selector}' 可见超时。")
                 try: await page.screenshot(path=SCREENSHOT_PATH)
                 except: pass
                 logging.info(f"已截屏保存至 {SCREENSHOT_PATH} (容器超时)。")
                 html_content = await page.content()
                 logging.warning("由于容器超时，获取到的HTML可能不完整。")

        except Exception as e:
            logging.error(f"Playwright 执行过程中发生意外错误: {e}")
            if page:
                try: await page.screenshot(path=SCREENSHOT_PATH); logging.info(f"已截屏保存错误状态 {SCREENSHOT_PATH}")
                except: pass
        finally:
            if console_messages:
                logging.info("捕获到的浏览器控制台消息:")
                for msg in console_messages: logging.info(f"  {msg}")
            else: logging.info("未捕获到浏览器控制台消息。")
            if page: await page.close()
            if context: await context.close()
            if browser: await browser.close()
            logging.info("Playwright 资源已关闭。")

    return html_content

# --- parse_price 和 send_notification 函数保持不变 ---
def parse_price(html_content: str, target_flight_number: str) -> Optional[float]:
    """ 解析HTML提取价格 """
    if not html_content: logging.warning("HTML内容为空，无法解析。"); return None
    logging.info(f"开始解析HTML，目标航班号: {target_flight_number}")
    soup = BeautifulSoup(html_content, 'lxml')
    flight_list_div = soup.find('div', id='flightInfoListDC')
    if not flight_list_div:
        logging.warning("未在HTML中找到航班列表容器 'div#flightInfoListDC'。")
        if len(html_content) < 2000: logging.debug(f"HTML片段: {html_content[:500]}...")
        else: logging.debug(f"HTML开头: {html_content[:500]}..."); logging.debug(f"HTML结尾: ...{html_content[-500:]}")
        return None
    flight_table = flight_list_div.find('table', class_='tblRouteList')
    if not flight_table: logging.warning("未找到航班表格 'table.tblRouteList'。"); return None
    flight_rows = flight_table.find_all('tr', class_='flightTr')
    if not flight_rows: logging.warning("未找到任何航班行 'tr.flightTr'。"); return None
    logging.info(f"找到 {len(flight_rows)} 个航班行，查找 {target_flight_number}...")
    target_flight_found = False
    min_price = float('inf')
    for row in flight_rows:
        flight_info_td = row.find('td', class_='flightInfoForm')
        if not flight_info_td: continue
        flight_number_div = flight_info_td.find('div', class_='F20')
        if flight_number_div and flight_number_div.text.strip() == target_flight_number:
            logging.info(f"找到目标航班: {target_flight_number}")
            target_flight_found = True
            price_cells = row.find_all('td', class_='classInfo')
            if not price_cells: logging.warning(f"航班 {target_flight_number} 未找到价格单元格。"); continue
            logging.info(f"找到 {len(price_cells)} 个价格单元格，提取价格...")
            found_price_in_row = False
            for cell in price_cells:
                price_div = cell.find('div', class_='F22 notHover')
                if price_div and ('￥' in price_div.text or '¥' in price_div.text):
                    price_text_raw = price_div.text.strip()
                    price_text = price_text_raw.replace('￥', '').replace('¥', '').replace(',', '').strip()
                    price_parts = price_text.split(); price_text = price_parts[0] if price_parts else ""
                    try: price_value = float(price_text); logging.info(f"  提取到价格 (NotHover): {price_value}"); min_price = min(min_price, price_value); found_price_in_row = True
                    except ValueError: logging.warning(f"  无法转换价格文本 '{price_text}' (来自 '{price_text_raw}')")
                else:
                    hover_price_div = cell.find('div', class_='needHover')
                    if hover_price_div:
                        price_span = hover_price_div.find('span', style=lambda v: v and 'font-size:18px' in v)
                        if price_span and ('￥' in price_span.text or '¥' in price_span.text):
                            price_text_raw = price_span.text.strip()
                            price_text = price_text_raw.replace('￥', '').replace('¥', '').replace(',', '').strip()
                            price_parts = price_text.split(); price_text = price_parts[0] if price_parts else ""
                            try: price_value = float(price_text); logging.info(f"  提取到价格 (Hover): {price_value}"); min_price = min(min_price, price_value); found_price_in_row = True
                            except ValueError: logging.warning(f"  无法转换悬停价格文本 '{price_text}' (来自 '{price_text_raw}')")
            if not found_price_in_row: logging.warning(f"航班 {target_flight_number} 未找到有效价格。")
            break
    if not target_flight_found: logging.warning(f"未找到目标航班 {target_flight_number}。"); return None
    if min_price == float('inf'): logging.warning(f"找到航班 {target_flight_number} 但未提取到价格。"); return None
    logging.info(f"解析完成，航班 {target_flight_number} 最低价格: {min_price}"); return min_price

def send_notification(token: str, title: str, content: str, template: str = 'html'):
    """ 使用PushPlus发送通知 """
    if not token or token == "你的PushPlus Token" or token == "******":
        logging.error("PushPlus Token无效或为示例值，无法发送通知。")
        return

    logging.info(f"准备发送PushPlus通知 (模板: {template})...")
    payload = {'token': token, 'title': title, 'content': content, 'template': template}
    try:
        response = requests.post(PUSHPLUS_API_URL, json=payload, timeout=20)
        response.raise_for_status()
        result = response.json()
        if result.get('code') == 200: logging.info("PushPlus通知发送成功。")
        elif result.get('code') == 903: logging.error("PushPlus通知发送失败: Code=903, 无效的用户token。请检查!")
        else: logging.error(f"PushPlus通知发送失败: Code={result.get('code')}, Msg={result.get('msg', '未知')}"); logging.error(f"响应详情: {result}")
    except requests.exceptions.RequestException as e: logging.error(f"发送通知网络错误: {e}")
    except json.JSONDecodeError: logging.error(f"解析响应失败: {response.text}")
    except Exception as e: logging.error(f"发送通知未知错误: {e}")

# --- 主程序异步化 ---
async def main():
    logging.info(f"--- 开始执行深圳航空机票价格监控脚本 (GitHub Actions: {IS_GITHUB_ACTIONS}) ---")
    config = load_config()
    if not config: logging.error("配置加载失败，脚本终止。"); return

    pushplus_token = config['PUSHPLUS_TOKEN']
    target_flight = config['FLIGHT_NUMBER']
    target_url = config['TARGET_URL']

    token_valid = pushplus_token and pushplus_token != "你的PushPlus Token" and pushplus_token != "******"
    if not token_valid: logging.error("PushPlus Token 无效或为示例值，本次运行将无法发送通知。")

    html = await fetch_html_with_playwright(target_url, BASE_URL) # 传入基础 URL

    screenshot_notice = f"\n\n**请查看截图: {SCREENSHOT_PATH}**" if not IS_GITHUB_ACTIONS else "" # Actions 中不提示看本地截图

    if html:
        current_price = parse_price(html, target_flight)
        if current_price is not None:
            title = f"深航 {target_flight} 价格更新"
            content_md = f"当前查询到的最低价格为：**¥{current_price:.2f}**\n\n当前时间：{logging.Formatter('%(asctime)s').formatTime(logging.LogRecord('', 0, '', 0, None, None, None))}\n\n[点击查看详情]({target_url})"
            if token_valid: send_notification(pushplus_token, title, content_md, template='markdown')
        else:
            title = f"深航 {target_flight} 查询失败"
            content = f"未能成功查询到航班 {target_flight} 的价格信息。\n查询页面：{target_url}\n请检查脚本日志。{screenshot_notice}"
            logging.error(content.replace(screenshot_notice,''))
            if token_valid: send_notification(pushplus_token, title, content.replace('\n', '<br>'), template='html')
    else:
        title = f"深航 {target_flight} 抓取失败"
        content = f"无法获取目标页面内容(Playwright)。\n查询页面：{target_url}\n请检查环境/浏览器/网络。{screenshot_notice}"
        logging.error(content.replace(screenshot_notice,''))
        if token_valid: send_notification(pushplus_token, title, content.replace('\n', '<br>'), template='html')

    logging.info("--- 脚本执行完毕 ---")

if __name__ == "__main__":
    asyncio.run(main())