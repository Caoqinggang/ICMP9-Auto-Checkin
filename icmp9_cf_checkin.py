#!/usr/bin/env python3
"""
ICMP9 DrissionPage 验证码攻坚版
更新内容：
1. 强化 Cloudflare 点击逻辑：显式点击 iframe body
2. 登录失败重试机制：如果第一遍没过，重新点验证码再登录
3. 增加 import requests 防止报错
"""

import os
import time
import logging
import requests
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
        """
        强力处理 Cloudflare
        策略：找到 iframe -> 点击中心 -> 等待变绿
        """
        logger.info("正在处理人机验证...")
        start_time = time.time()
        # 给足 20 秒处理验证码
        while time.time() - start_time < 20:
            try:
                # 1. 查找包含 cloudflare 的 iframe
                iframe_ele = self.page.ele('css:iframe[src*="cloudflare"]', timeout=2)
                
                if iframe_ele:
                    # 获取 iframe 对象
                    iframe = self.page.get_frame(iframe_ele)
                    if iframe:
                        # 尝试1：点击 body (最通用)
                        iframe.ele('tag:body').click()
                        time.sleep(0.5)
                        
                        # 尝试2：点击 checkbox (如果存在)
                        cb = iframe.ele('@type=checkbox')
                        if cb: cb.click()
                        
                        # 点击后，一定要等待它变绿（Cloudflare 处理需要时间）
                        # 这里的等待非常关键，不能马上点登录
                        if "Success" in iframe.html:
                            logger.info("验证似乎已通过 (检测到 Success)")
                            return True
            except:
                pass
            time.sleep(1)
        
        logger.info("验证等待超时 (但不代表失败，继续尝试登录)")
        return True

    def login(self):
        """登录逻辑 (带重试)"""
        try:
            logger.info(f"1. 访问登录页...")
            self.page.get(f"{self.base_url}/user/login")
            time.sleep(3) # 等待页面完全加载
            
            # 2. 填写表单
            logger.info("2. 输入账号信息...")
            user_input = self.page.ele('#username') or self.page.ele('@name=username')
            if not user_input:
                logger.error("❌ 找不到输入框")
                self.save_evidence("login_no_input")
                return False
            
            user_input.input(self.email)
            self.page.ele('css:input[type="password"]').input(self.password)
            
            # 3. 核心：处理验证码 + 点击登录 (循环尝试 3 次)
            for attempt in range(1, 4):
                logger.info(f"--- 登录尝试第 {attempt} 次 ---")
                
                # A. 点击验证码
                self.solve_turnstile()
                
                # B. 等待验证码生效
                logger.info("等待验证码生效 (5秒)...")
                time.sleep(5)
                
                # C. 点击登录按钮
                logger.info("点击登录按钮...")
                submit_btn = self.page.ele('css:button[type="submit"]') or self.page.ele('text:登录') or self.page.ele('.btn-primary')
                
                if submit_btn:
                    # 使用 JS 强制点击，防止按钮被透明层遮挡
                    self.page.run_js('arguments[0].click()', submit_btn)
                else:
                    logger.error("未找到登录按钮")
                
                # D. 等待跳转
                logger.info("等待跳转 (10秒)...")
                time.sleep(10)
                
                # E. 检查结果
                if "dashboard" in self.page.url:
                    logger.info("✅ 登录成功！")
                    return True
                
                # 如果没成功，截图看看为什么
                logger.warning(f"第 {attempt} 次尝试未跳转，当前仍在: {self.page.url}")
                self.save_evidence(f"login_fail_{attempt}")
                
                # 刷新页面或继续尝试点击？这里选择直接重试点击流程
            
            logger.error("❌ 多次尝试登录失败")
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

            # 2. 点击导航
            logger.info("寻找导航 [每日签到]...")
            nav_item = self.page.ele('css:a[data-section="checkin"]') or self.page.ele('@data-section=checkin')
            
            if not nav_item:
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

            # 3. 点击按钮
            logger.info("寻找按钮 [#checkin-btn]...")
            # 签到前可能还需要验证一次
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
