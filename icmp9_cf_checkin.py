#!/usr/bin/env python3
"""
ICMP9 DrissionPage 回归经典版
基于早期成功登录的逻辑，结合最新的 ID 定位
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
        
        self.page = ChromiumPage(co)
        self.page.set.timeouts(10)

    def handle_turnstile(self):
        """
        简单的验证码处理逻辑 (回归版)
        只尝试一次点击，不进行死循环卡顿
        """
        try:
            # 查找 iframe
            iframe = self.page.ele('css:iframe[src*="cloudflare"]', timeout=3)
            if iframe:
                # 获取 frame 上下文
                frame_doc = self.page.get_frame(iframe)
                if frame_doc:
                    # 尝试点击 body (通常最有效)
                    frame_doc.ele('tag:body').click()
                    time.sleep(2)
        except:
            pass

    def login(self):
        """登录逻辑 (回归简单直接)"""
        try:
            logger.info("1. 访问登录页...")
            self.page.get(f"{self.base_url}/user/login")
            time.sleep(3)
            
            # 处理可能的验证码
            self.handle_turnstile()
            
            # 输入账号 (使用你提供的 id="username")
            logger.info("2. 输入账号信息...")
            self.page.ele('#username').input(self.email)
            self.page.ele('css:input[type="password"]').input(self.password)
            
            # 点击登录
            logger.info("3. 点击登录...")
            # 再次尝试处理验证码（防止输入后出现）
            self.handle_turnstile()
            
            # 点击按钮
            self.page.ele('css:button[type="submit"]').click()
            
            # 等待跳转
            logger.info("4. 等待跳转...")
            time.sleep(5)
            
            if "dashboard" in self.page.url:
                logger.info("✅ 登录成功")
                return True
            
            # 如果没跳转，可能卡在验证码，再点一次
            if "login" in self.page.url:
                logger.info("⚠️ 似乎未跳转，尝试二次点击验证码和登录...")
                self.handle_turnstile()
                time.sleep(2)
                self.page.ele('css:button[type="submit"]').click()
                time.sleep(5)
            
            if "dashboard" in self.page.url:
                logger.info("✅ 重试后登录成功")
                return True
                
            return False

        except Exception as e:
            logger.error(f"登录出错: {e}")
            return False

    def get_id_text(self, ele_id, unit=""):
        try:
            # 直接获取文本，不报错
            ele = self.page.ele(f'#{ele_id}', timeout=2)
            return f"{ele.text.strip()} {unit}" if ele else "未找到"
        except: return "N/A"

    def checkin_flow(self):
        """签到流程 (适配最新 ID)"""
        try:
            if "dashboard" not in self.page.url:
                self.page.get(f"{self.base_url}/user/dashboard")
                time.sleep(5)

            # 1. 清理弹窗 (强制 JS 移除)
            logger.info("清理弹窗...")
            try:
                self.page.run_js("document.querySelectorAll('.ant-modal-mask, .ant-modal-wrap, .modal-backdrop').forEach(m => m.remove())")
                pop = self.page.ele('text=我知道了')
                if pop: pop.click()
            except: pass
            time.sleep(1)

            # 2. 点击侧边栏
            logger.info("点击 [每日签到]...")
            # 使用最稳的属性定位
            nav = self.page.ele('@data-section=checkin')
            if nav:
                # 使用 JS 点击防止被遮挡
                self.page.run_js('arguments[0].click()', nav)
                time.sleep(3)
            else:
                # 尝试移动端菜单
                menu = self.page.ele('.navbar-toggler')
                if menu:
                    menu.click()
                    time.sleep(1)
                    self.page.ele('@data-section=checkin').click()
                    time.sleep(3)

            # 3. 点击签到按钮
            logger.info("操作签到按钮...")
            # 再次检查验证码 (签到页可能有)
            self.handle_turnstile()
            
            # 使用 ID 定位按钮
            btn = self.page.ele('#checkin-btn')
            if btn:
                if "已" in btn.text or btn.attr('disabled'):
                    self.stats["status"] = "今日已签到"
                    logger.info("状态: 已签到")
                else:
                    self.page.run_js('arguments[0].click()', btn)
                    time.sleep(3)
                    self.stats["status"] = "今日签到成功"
                    logger.info("状态: 签到成功")
            else:
                self.stats["status"] = "未找到按钮"
                logger.warning("未找到 #checkin-btn")

            # 4. 读取数据
            logger.info("读取数据...")
            self.stats["today_reward"] = self.get_id_text("today-reward", "GB")
            self.stats["total_traffic"] = self.get_id_text("total-checkin-traffic", "GB")
            self.stats["total_days"] = self.get_id_text("total-checkins", "天")
            self.stats["streak_days"] = self.get_id_text("continuous-days", "天")
            
            logger.info(f"结果: {self.stats}")
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
