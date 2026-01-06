#!/usr/bin/env python3
"""
ICMP9 DrissionPage 最终适配版
更新内容：
1. 登录框适配：修改为 <input id="username"> 定位
2. 保持之前的弹窗处理、侧边栏点击、ID数据抓取逻辑
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
        co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
        
        self.page = ChromiumPage(co)
        self.page.set.timeouts(15)

    def save_evidence(self, name):
        """保存截图和源码"""
        try:
            timestamp = datetime.now().strftime("%H%M%S")
            self.page.get_screenshot(path=f"{name}_{timestamp}.png", full_page=True)
            with open(f"{name}_{timestamp}.html", "w", encoding="utf-8") as f:
                f.write(self.page.html)
            logger.info(f"📸 已保存证据: {name}_{timestamp}.png")
        except: pass

    def solve_turnstile(self):
        """处理 Cloudflare"""
        start_time = time.time()
        while time.time() - start_time < 8:
            iframe = self.page.get_frame('@src^https://challenges.cloudflare.com')
            if iframe:
                btn = iframe.ele('tag:input') or iframe.ele('@type=checkbox') or iframe.ele('text=Verify you are human')
                if btn:
                    try:
                        logger.info("点击 CF 验证...")
                        btn.click()
                        time.sleep(2)
                    except: pass
                if "Success" in iframe.html:
                    return True
            time.sleep(1)
        return True

    def login(self):
        """登录逻辑 (已针对 input#username 修正)"""
        try:
            logger.info(f"1. 访问登录页...")
            self.page.get(f"{self.base_url}/user/login")
            self.solve_turnstile()
            
            # ==========================================
            # [修正点] 适配新的输入框 HTML
            # <input type="text" id="username" name="username" ...>
            # ==========================================
            logger.info("2. 输入账号信息...")
            
            # 优先使用 id="username"
            user_input = self.page.ele('#username')
            
            # 备用：使用 name="username"
            if not user_input:
                user_input = self.page.ele('@name=username')
            
            # 备用：使用 placeholder
            if not user_input:
                user_input = self.page.ele('@placeholder:用户名')

            if not user_input:
                logger.error("❌ 找不到用户名/邮箱输入框")
                self.save_evidence("login_input_missing")
                return False
            
            # 输入账号
            user_input.input(self.email)
            
            # 输入密码 (通常 type="password" 是通用的)
            self.page.ele('css:input[type="password"]').input(self.password)
            
            # 3. 点击登录
            logger.info("3. 点击登录按钮...")
            self.solve_turnstile()
            
            submit_btn = self.page.ele('css:button[type="submit"]') or self.page.ele('text:登录')
            if submit_btn:
                self.page.run_js('arguments[0].click()', submit_btn)
            else:
                logger.error("❌ 未找到登录按钮")
                return False
            
            # 4. 等待跳转
            logger.info("4. 等待跳转 (15秒)...")
            time.sleep(15)
            
            # 检测结果
            if "dashboard" in self.page.url:
                logger.info("✅ 登录成功")
                return True
            
            # 检查是否有错误提示
            body_text = self.page.ele('tag:body').text
            if "验证码" in body_text:
                logger.error("⛔ 需要二次验证")
                self.save_evidence("login_2fa")
                return False
            elif "密码错误" in body_text or "用户不存在" in body_text:
                logger.error("❌ 账号密码错误")
                return False

            # 尝试强制跳转
            if "user" in self.page.url:
                logger.info("🔄 尝试强制跳转 Dashboard...")
                self.page.get(f"{self.base_url}/user/dashboard")
                time.sleep(8)
                if "dashboard" in self.page.url:
                    logger.info("✅ 强制跳转成功")
                    return True

            logger.error("登录失败")
            self.save_evidence("login_failed")
            return False

        except Exception as e:
            logger.error(f"登录出错: {e}")
            return False

    def get_id_text(self, ele_id, unit=""):
        try:
            ele = self.page.ele(f'#{ele_id}')
            return f"{ele.text.strip()} {unit}" if ele else "未找到"
        except: return "N/A"

    def checkin_flow(self):
        try:
            logger.info(">>> 开始签到流程 <<<")
            
            # 1. 移除弹窗
            try:
                self.page.run_js("document.querySelectorAll('.ant-modal-mask, .ant-modal-wrap, .modal-backdrop').forEach(m => m.remove())")
                pop_btn = self.page.ele('text=我知道了')
                if pop_btn: self.page.run_js('arguments[0].click()', pop_btn)
            except: pass
            time.sleep(1)

            # 2. 点击导航 [每日签到]
            # <a class="nav-item" data-section="checkin">
            logger.info("寻找导航 [每日签到]...")
            nav_item = self.page.ele('css:a[data-section="checkin"]') or self.page.ele('@data-section=checkin')
            
            if not nav_item:
                # 移动端兼容
                menu_btn = self.page.ele('.navbar-toggler')
                if menu_btn:
                    menu_btn.click()
                    time.sleep(1)
                    nav_item = self.page.ele('css:a[data-section="checkin"]')
            
            if nav_item:
                self.page.run_js('arguments[0].click()', nav_item)
                time.sleep(5)
            else:
                logger.error("❌ 找不到导航菜单")
                self.save_evidence("nav_missing")
                return False

            # 3. 点击按钮 #checkin-btn
            logger.info("寻找按钮 [#checkin-btn]...")
            self.solve_turnstile()
            
            btn = None
            for _ in range(5):
                btn = self.page.ele('#checkin-btn')
                if btn: break
                time.sleep(1)

            if btn:
                if "已" in btn.text or btn.attr('disabled'):
                    self.stats["status"] = "今日已签到"
                    logger.info("状态: 已签到")
                else:
                    self.page.run_js('arguments[0].click()', btn)
                    time.sleep(5)
                    self.stats["status"] = "今日签到成功"
                    logger.info("状态: 签到成功")
            else:
                self.stats["status"] = "异常：未找到按钮"

            # 4. 抓取数据
            self.stats["today_reward"] = self.get_id_text("today-reward", "GB")
            self.stats["total_traffic"] = self.get_id_text("total-checkin-traffic", "GB")
            self.stats["total_days"] = self.get_id_text("total-checkins", "天")
            self.stats["streak_days"] = self.get_id_text("continuous-days", "天")
            
            logger.info(f"最终结果: {self.stats}")
            return True

        except Exception as e:
            logger.error(f"签到出错: {e}")
            return False

    def run(self):
        self.init_browser()
        try:
            if self.login():
                self.checkin_flow()
            else:
                self.stats["status"] = "登录失败"
            return True, self.stats
        finally:
            self.page.quit()

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
            mask = email.split('@')[0][:3] + "***"
            msg += f"👤 {mask}\nSTATUS: {stats['status']}\n"
            if "成功" in stats['status'] or "已" in stats['status']:
                msg += f"🎁 {stats['today_reward']} | 🗓 {stats['total_days']}\n"
            msg += "-" * 20 + "\n"
        requests.post(f"https://api.telegram.org/bot{self.bot_token}/sendMessage", json={"chat_id": self.chat_id, "text": msg, "parse_mode": "HTML"})

    def run_all(self):
        results = []
        for acc in self.accounts:
            task = ICMP9Checkin(acc['email'], acc['password'])
            success, stats = task.run()
            results.append((acc['email'], success, stats))
        self.send_notify(results)

if __name__ == "__main__":
    MultiAccountManager().run_all()
