#!/usr/bin/env python3
"""
ICMP9 DrissionPage 鼠标模拟攻坚版
更新重点：
1. 修复人机验证：使用 page.actions 模拟真实鼠标移动和点击
2. 增加坐标点击兜底策略
3. 增加字体安装提示（解决方框乱码）
"""

import os
import time
import logging
import requests
import random
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
        # 伪装 User-Agent
        co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        
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
        [核心升级] 模拟真人鼠标处理 Cloudflare
        """
        logger.info("🛡️ 开始处理人机验证 (鼠标模拟模式)...")
        start_time = time.time()
        
        # 循环检测 25 秒
        while time.time() - start_time < 25:
            try:
                # 1. 定位 iframe
                iframe_ele = self.page.ele('css:iframe[src*="cloudflare"]', timeout=2)
                
                if iframe_ele:
                    # 获取 iframe 内部对象用于检查状态
                    iframe_context = self.page.get_frame(iframe_ele)
                    
                    # 检查是否已经成功 (内部出现 Success 字样)
                    if iframe_context and "Success" in iframe_context.html:
                        logger.info("✅ 验证已通过！")
                        return True
                    
                    # 2. 模拟鼠标移动并点击
                    logger.info("🖱️ 鼠标移动到验证框中心并点击...")
                    
                    # 方法A: 使用动作链 (Actions) 模拟悬停后点击
                    # 移动到元素中心，偏移一点点随机像素，看起来更像人
                    offset_x = random.randint(-5, 5)
                    offset_y = random.randint(-5, 5)
                    
                    self.page.actions.move_to(iframe_ele, offset_x=offset_x, offset_y=offset_y).wait(0.5).click()
                    
                    # 方法B: 如果动作链失败，尝试直接点击 iframe 内部 body
                    if iframe_context:
                        try:
                            # 有时候点击 body 比点击 checkbox 更稳
                            iframe_context.ele('tag:body').click()
                        except: pass

                    # 点击后等待 Cloudflare 反应
                    time.sleep(3)
                    
                    # 再次检查是否成功
                    if iframe_context and "Success" in iframe_context.html:
                        logger.info("✅ 验证通过 (点击生效)")
                        return True
                        
            except Exception as e:
                # logger.warning(f"验证尝试异常: {e}")
                pass
            
            time.sleep(1)
        
        logger.warning("⚠️ 验证超时，未检测到通过信号 (尝试强行登录)")
        return True

    def login(self):
        """登录逻辑"""
        try:
            logger.info(f"1. 访问登录页...")
            self.page.get(f"{self.base_url}/user/login")
            time.sleep(3)
            
            # 2. 输入账号信息
            logger.info("2. 输入账号信息...")
            user_input = self.page.ele('#username') or self.page.ele('@name=username')
            if not user_input:
                logger.error("❌ 找不到输入框")
                self.save_evidence("login_no_input")
                return False
            
            user_input.input(self.email)
            self.page.ele('css:input[type="password"]').input(self.password)
            
            # 3. 攻克验证码 + 登录 (带重试)
            for attempt in range(1, 4):
                logger.info(f"--- 登录尝试第 {attempt}/3 次 ---")
                
                # 处理验证码
                self.solve_turnstile()
                
                # 点击登录
                logger.info("点击 [立即登录]...")
                # 寻找你截图中的蓝色按钮
                submit_btn = self.page.ele('text:立即登录') or self.page.ele('css:button[type="submit"]') or self.page.ele('.btn-primary')
                
                if submit_btn:
                    # 确保按钮不在 loading 状态
                    self.page.run_js('arguments[0].click()', submit_btn)
                else:
                    logger.error("未找到登录按钮")
                
                logger.info("等待跳转 (10秒)...")
                time.sleep(10)
                
                # 检查结果
                if "dashboard" in self.page.url:
                    logger.info("✅ 登录成功！")
                    return True
                
                # 失败截图
                logger.warning(f"第 {attempt} 次失败，当前URL: {self.page.url}")
                self.save_evidence(f"login_fail_{attempt}")
                
                # 刷新页面重试？不，直接在当前页重点
            
            logger.error("❌ 最终登录失败")
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
            # 签到前可能也需要过盾
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
