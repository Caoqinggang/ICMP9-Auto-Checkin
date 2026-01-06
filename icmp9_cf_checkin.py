#!/usr/bin/env python3
"""
ICMP9 强力调试版 (无视风控)
功能：
1. 登录后强制跳转 Dashboard (不信邪模式)
2. 全程关键节点截图，用于排查 IP 风控
3. 移除封号退出的逻辑，强行尝试签到
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
        # 使用最新的 User-Agent 伪装
        co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        
        self.page = ChromiumPage(co)
        self.page.set.timeouts(15)

    def save_screenshot(self, name):
        """保存截图用于调试"""
        try:
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"{name}_{timestamp}.png"
            self.page.get_screenshot(path=filename, full_page=True)
            logger.info(f"📸 已保存截图: {filename}")
            
            # 同时保存 HTML
            with open(f"{name}_{timestamp}.html", "w", encoding="utf-8") as f:
                f.write(self.page.html)
        except Exception as e:
            logger.error(f"截图失败: {e}")

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
            email_ele = self.page.ele('css:input[type="username"]') or self.page.ele('@placeholder:用户名')
            if not email_ele:
                logger.error("未找到邮箱输入框")
                self.save_screenshot("no_input")
                return False
                
            email_ele.input(self.email)
            self.page.ele('css:input[type="password"]').input(self.password)
            
            btn = self.page.ele('css:button[type="submit"]') or self.page.ele('text:登录')
            if btn: btn.click()
            
            logger.info("等待登录跳转 (10秒)...")
            time.sleep(10)
            self.handle_turnstile()
            
            # 截图看登录后到底是什么鬼样子
            self.save_screenshot("after_login")
            
            # 检查是否还在登录页
            if "login" in self.page.url:
                logger.warning("⚠️ URL 仍停留在 login，尝试强制跳转 Dashboard...")
            
            # 无论页面提示什么，强行跳转 Dashboard
            logger.info("3. 强制跳转 /user/dashboard")
            self.page.get(f"{self.base_url}/user/dashboard")
            time.sleep(8)
            self.save_screenshot("force_dashboard")
            
            return True
            
        except Exception as e:
            logger.error(f"登录异常: {e}")
            return False

    def get_id_text(self, ele_id, unit=""):
        try:
            ele = self.page.ele(f'#{ele_id}')
            if ele: return f"{ele.text.strip()} {unit}"
            return "未找到"
        except: return "N/A"

    def checkin_flow(self):
        try:
            # 1. 处理弹窗
            logger.info("4. 处理弹窗...")
            try:
                # JS 暴力移除遮罩
                self.page.run_js("document.querySelectorAll('.ant-modal-mask, .ant-modal-wrap, .modal-backdrop').forEach(m => m.remove())")
                pop_btn = self.page.ele('text=我知道了') or self.page.ele('.ant-modal-close')
                if pop_btn:
                    logger.info("点击弹窗关闭")
                    self.page.run_js('arguments[0].click()', pop_btn)
                    time.sleep(2)
            except: pass

            # 2. 寻找导航
            logger.info("5. 寻找导航菜单 [每日签到]...")
            self.save_screenshot("before_nav")
            
            nav_item = self.page.ele('css:a[data-section="checkin"]') or self.page.ele('@data-section=checkin')
            
            # 移动端兼容
            if not nav_item:
                menu_btn = self.page.ele('.navbar-toggler') or self.page.ele('button[class*="toggle"]')
                if menu_btn:
                    menu_btn.click()
                    time.sleep(1)
                    nav_item = self.page.ele('css:a[data-section="checkin"]')

            if nav_item:
                logger.info(">>> 点击导航菜单 <<<")
                self.page.run_js('arguments[0].click()', nav_item)
                time.sleep(5)
            else:
                logger.error("!!! 无法找到导航菜单 !!!")
                # 再次截图，看看是不是被风控页面挡住了
                self.save_screenshot("nav_not_found")
                
                # 尝试直接寻找签到按钮（万一已经在签到页）
                pass

            # 3. 签到按钮
            logger.info("6. 寻找签到按钮 [#checkin-btn]...")
            self.handle_turnstile()
            
            btn = None
            for _ in range(5):
                btn = self.page.ele('#checkin-btn')
                if btn: break
                time.sleep(1)

            if btn:
                text = btn.text
                disabled = btn.attr('disabled') is not None
                if "已" in text or disabled:
                    self.stats["status"] = "今日已签到"
                else:
                    self.page.run_js('arguments[0].click()', btn)
                    time.sleep(5)
                    self.stats["status"] = "今日签到成功"
            else:
                # 如果找不到按钮，把页面 HTML 打印一部分看看
                logger.warning("未找到按钮，当前页面 Body 文本前 200 字:")
                logger.info(self.page.ele('tag:body').text[:200].replace('\n', ' '))
                self.stats["status"] = "异常：未找到 #checkin-btn"

            # 4. 读取数据
            logger.info("7. 读取统计数据...")
            self.stats["today_reward"] = self.get_id_text("today-reward", "GB")
            self.stats["total_traffic"] = self.get_id_text("total-checkin-traffic", "GB")
            self.stats["total_days"] = self.get_id_text("total-checkins", "天")
            self.stats["streak_days"] = self.get_id_text("continuous-days", "天")
            
            logger.info(f"结果: {self.stats}")
            return True

        except Exception as e:
            logger.error(f"流程崩溃: {e}")
            return False

    def run(self):
        self.init_browser()
        try:
            if self.login():
                self.checkin_flow()
            return True, self.stats
        finally:
            self.page.quit()

# ... MultiAccountManager 保持不变 ...
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

    def send_notify(self, results):
        if not self.bot_token or not self.chat_id: return
        msg = "✈️ <b>ICMP9 签到报告</b>\n" + "-" * 20 + "\n"
        for email, success, stats in results:
            mask_email = email.split('@')[0][:3] + "***"
            msg += f"👤 {mask_email}\nSTATUS: {stats['status']}\n"
            if "成功" in stats['status'] or "已" in stats['status']:
                msg += f"🎁 获: {stats['today_reward']} | 总: {stats['total_traffic']}\n"
            msg += "-" * 20 + "\n"
        requests.post(f"https://api.telegram.org/bot{self.bot_token}/sendMessage", json={"chat_id": self.chat_id, "text": msg, "parse_mode": "HTML"})

    def run_all(self):
        for acc in self.accounts:
            task = ICMP9Checkin(acc['email'], acc['password'])
            task.run()

if __name__ == "__main__":
    MultiAccountManager().run_all()
