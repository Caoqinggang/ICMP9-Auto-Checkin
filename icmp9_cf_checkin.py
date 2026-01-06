#!/usr/bin/env python3
"""
ICMP9 强力调试版脚本
功能：
1. 失败时自动截图 + 保存HTML源码 (方便排查)
2. 打印当前页面所有可见文本，确认是否被 Cloudflare 拦截
3. 使用 JS 暴力移除遮罩层，防止点击被拦截
"""

import os
import time
import logging
from datetime import datetime
from DrissionPage import ChromiumPage, ChromiumOptions

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ICMP9Checkin:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.page = None
        self.base_url = "https://icmp9.com"
        self.stats = {"status": "未知"}
        
    def init_browser(self):
        co = ChromiumOptions()
        if os.getenv('GITHUB_ACTIONS'):
            co.set_browser_path('/usr/bin/google-chrome')
        
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-gpu')
        co.set_argument('--window-size=1920,1080') 
        co.set_argument('--start-maximized')
        co.set_argument('--lang=zh-CN') 
        co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        self.page = ChromiumPage(co)
        self.page.set.timeouts(15)

    def save_debug_info(self, prefix="error"):
        """保存截图和源码用于调试"""
        try:
            timestamp = datetime.now().strftime("%H%M%S")
            # 截图
            shot_name = f"{prefix}_{timestamp}.png"
            self.page.get_screenshot(path=shot_name, full_page=True)
            logger.info(f"!!! 已保存截图: {shot_name}")
            
            # 保存源码
            html_name = f"{prefix}_{timestamp}.html"
            with open(html_name, "w", encoding="utf-8") as f:
                f.write(self.page.html)
            logger.info(f"!!! 已保存HTML源码: {html_name}")
            
            # 打印当前页面标题和URL
            logger.info(f"当前页面标题: {self.page.title}")
            logger.info(f"当前页面URL: {self.page.url}")
            
            # 打印部分文本内容，看看是不是被CF拦截了
            body_text = self.page.ele('tag:body').text[:500].replace('\n', ' ')
            logger.info(f"页面头部文本: {body_text}")
            
        except Exception as e:
            logger.error(f"保存调试信息失败: {e}")

    def handle_turnstile(self):
        try:
            start_time = time.time()
            while time.time() - start_time < 5:
                iframe = self.page.get_frame('@src^https://challenges.cloudflare.com')
                if iframe:
                    btn = iframe.ele('tag:input') or iframe.ele('@type=checkbox') or iframe.ele('text=Verify you are human')
                    if btn:
                        logger.info("点击验证框...")
                        btn.click()
                        time.sleep(3)
                        return True
                time.sleep(0.5)
            return False
        except: return False

    def login(self):
        try:
            logger.info(f"1. 打开登录页...")
            self.page.get(f"{self.base_url}/user/login")
            self.handle_turnstile()
            
            logger.info("2. 输入账号密码...")
            email_ele = self.page.ele('css:input[type="email"]') or self.page.ele('@placeholder:邮箱')
            if not email_ele:
                logger.error("未找到邮箱输入框")
                self.save_debug_info("login_fail")
                return False
                
            email_ele.input(self.email)
            self.page.ele('css:input[type="password"]').input(self.password)
            
            btn = self.page.ele('css:button[type="submit"]') or self.page.ele('text:登录')
            if btn: btn.click()
            
            time.sleep(5)
            self.handle_turnstile()
            
            if "dashboard" in self.page.url or "user" in self.page.url:
                logger.info("3. 登录成功")
                return True
            
            logger.error("登录未跳转")
            self.save_debug_info("login_stuck")
            return False
        except Exception as e:
            logger.error(f"登录异常: {e}")
            return False

    def checkin_flow(self):
        try:
            if "dashboard" not in self.page.url:
                self.page.get(f"{self.base_url}/user/dashboard")
                time.sleep(8) # 增加等待时间，防止白屏

            # ==========================================
            # 1. 暴力处理弹窗 (JS 移除遮罩)
            # ==========================================
            logger.info("4. 处理弹窗和遮罩...")
            try:
                # 尝试点击“我知道了”
                pop_btn = self.page.ele('text=我知道了') or self.page.ele('.ant-modal-close')
                if pop_btn:
                    logger.info("点击弹窗关闭按钮")
                    pop_btn.click()
                    time.sleep(2)
                
                # 【大招】直接运行JS移除常见的遮罩层，防止挡住点击
                js_remove_mask = """
                var masks = document.querySelectorAll('.ant-modal-mask, .ant-modal-wrap, .modal-backdrop');
                masks.forEach(m => m.remove());
                var modals = document.querySelectorAll('.ant-modal, .modal');
                modals.forEach(m => m.remove());
                """
                self.page.run_js(js_remove_mask)
                logger.info("已执行JS强制移除遮罩层")
            except Exception as e:
                logger.warning(f"弹窗处理警告: {e}")

            # ==========================================
            # 2. 寻找导航菜单
            # ==========================================
            logger.info("5. 寻找导航菜单 [每日签到]...")
            
            # 打印当前页面所有的链接文本，帮我确认页面到底加载了什么
            # links = self.page.eles('tag:a')
            # logger.info(f"页面上发现 {len(links)} 个链接")
            
            # 尝试多种定位方式
            nav_item = None
            
            # 方式A: 精确 CSS (你提供的代码)
            nav_item = self.page.ele('css:a.nav-item[data-section="checkin"]')
            
            # 方式B: 只用 data-section
            if not nav_item:
                nav_item = self.page.ele('@data-section=checkin')
                
            # 方式C: 寻找包含 SVG 的那个链接 (根据你的HTML结构)
            if not nav_item:
                logger.info("尝试通过 SVG 结构查找...")
                # 找包含 '每日签到' 文本的 nav-item 类
                nav_items = self.page.eles('.nav-item')
                for item in nav_items:
                    if "每日签到" in item.text:
                        nav_item = item
                        break

            if nav_item:
                logger.info(f">>> 找到导航菜单，文本: {nav_item.text.strip()} <<<")
                # 强制 JS 点击，无视遮挡
                self.page.run_js('arguments[0].click()', nav_item)
                time.sleep(5)
            else:
                logger.error("!!! 无法找到导航菜单 !!!")
                # 截图保存现场
                self.save_debug_info("nav_missing")
                
                # 尝试直接打印所有 nav-item 的内容，看看有没有类似的
                logger.info("列出页面上所有 .nav-item 的内容:")
                items = self.page.eles('.nav-item')
                for i, item in enumerate(items):
                    logger.info(f"Item {i}: {item.text.replace('\n', ' ')} | HTML: {item.outer_html[:50]}")
                return False

            # ==========================================
            # 3. 签到按钮
            # ==========================================
            logger.info("6. 寻找签到按钮 [#checkin-btn]...")
            self.handle_turnstile()
            
            btn = self.page.ele('#checkin-btn')
            if not btn:
                # 尝试等待一下
                time.sleep(3)
                btn = self.page.ele('#checkin-btn')

            if btn:
                text = btn.text
                disabled = btn.attr('disabled') is not None
                logger.info(f"按钮状态: 文本=[{text}], Disabled=[{disabled}]")
                
                if "已" in text or disabled:
                    self.stats["status"] = "今日已签到"
                else:
                    logger.info("点击签到...")
                    # 强制 JS 点击
                    self.page.run_js('arguments[0].click()', btn)
                    time.sleep(5)
                    self.stats["status"] = "今日签到成功"
            else:
                logger.error("未找到 #checkin-btn")
                self.save_debug_info("btn_missing")
                # 即使没找到按钮，也尝试读数据，万一已经显示了呢

            # ==========================================
            # 4. 读取数据
            # ==========================================
            logger.info("7. 读取统计数据...")
            
            def get_text(eid):
                e = self.page.ele(f'#{eid}')
                return e.text.strip() if e else "未找到"

            self.stats["today_reward"] = get_text("today-reward") + " GB"
            self.stats["total_traffic"] = get_text("total-checkin-traffic") + " GB"
            self.stats["total_days"] = get_text("total-checkins") + " 天"
            self.stats["streak_days"] = get_text("continuous-days") + " 天"
            
            logger.info(f"结果: {self.stats}")
            return True

        except Exception as e:
            logger.error(f"流程崩溃: {e}")
            self.save_debug_info("crash")
            return False

    def run(self):
        self.init_browser()
        try:
            if self.login():
                self.checkin_flow()
            return True, self.stats
        finally:
            self.page.quit()

# ... (MultiAccountManager 类保持不变) ...
class MultiAccountManager:
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.accounts = self.load_accounts()

    def load_accounts(self):
        accounts = []
        s_email = os.getenv('ICMP9_EMAIL', '').strip()
        s_pass = os.getenv('ICMP9_PASSWORD', '').strip()
        if s_email and s_pass:
            accounts.append({'email': s_email, 'password': s_pass})
        return accounts

    def run_all(self):
        for acc in self.accounts:
            task = ICMP9Checkin(acc['email'], acc['password'])
            task.run()

if __name__ == "__main__":
    MultiAccountManager().run_all()
