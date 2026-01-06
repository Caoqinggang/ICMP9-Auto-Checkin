#!/usr/bin/env python3
"""
ICMP9 DrissionPage 自动签到脚本 (ID精准定位版)
更新内容：
1. 按钮定位：直接使用 #checkin-btn
2. 状态判断：通过 disabled 属性和文本判断
3. 数据抓取：直接读取 #today-reward 等 ID，无需正则
4. 单位补全：根据描述自动追加 GB 或 天
"""

import os
import time
import logging
import requests
import re
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
        self.stats = {
            "status": "未知",
            "today_reward": "0 GB", 
            "total_traffic": "0 GB", 
            "total_days": "0 天",    
            "streak_days": "0 天"    
        }
        
    def init_browser(self):
        """初始化浏览器"""
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
        self.page.set.timeouts(10)

    def handle_turnstile(self):
        """处理 Cloudflare 验证"""
        try:
            start_time = time.time()
            while time.time() - start_time < 5:
                iframe = self.page.get_frame('@src^https://challenges.cloudflare.com')
                if iframe:
                    btn = iframe.ele('tag:input') or iframe.ele('@type=checkbox') or iframe.ele('text=Verify you are human')
                    if btn:
                        logger.info("检测到验证框，正在点击...")
                        btn.click()
                        time.sleep(3)
                        return True
                time.sleep(0.5)
            return False
        except:
            return False

    def login(self):
        """登录流程"""
        try:
            login_url = f"{self.base_url}/user/login"
            logger.info(f"[{self.email}] 1. 打开登录页: {login_url}")
            self.page.get(login_url)
            self.handle_turnstile()
            
            logger.info("2. 输入账号密码...")
            email_ele = self.page.ele('css:input[type="email"]') or self.page.ele('css:input[name="email"]') or self.page.ele('@placeholder:邮箱')
            
            if not email_ele:
                logger.error("找不到邮箱输入框")
                return False
                
            email_ele.input(self.email)
            self.page.ele('css:input[type="password"]').input(self.password)
            
            login_btn = self.page.ele('css:button[type="submit"]') or self.page.ele('text:登录')
            if login_btn: login_btn.click()
            
            time.sleep(5) 
            self.handle_turnstile()
            
            if "dashboard" in self.page.url or "user" in self.page.url:
                logger.info("3. 登录成功，已到达 Dashboard")
                return True
            
            logger.error(f"登录失败，当前URL: {self.page.url}")
            return False
        except Exception as e:
            logger.error(f"登录异常: {e}")
            return False

    def get_id_text(self, ele_id, unit=""):
        """通过ID直接获取数值并拼接单位"""
        try:
            # 直接使用 #id 选择器
            ele = self.page.ele(f'#{ele_id}')
            if ele:
                # 获取纯数值，去除空格
                val = ele.text.strip()
                # 拼接单位
                return f"{val} {unit}"
            return "未找到"
        except:
            return "N/A"

    def checkin_flow(self):
        """签到核心流程"""
        try:
            if "dashboard" not in self.page.url:
                self.page.get(f"{self.base_url}/user/dashboard")
                time.sleep(5)

            # 1. 处理公告弹窗
            try:
                pop_btn = self.page.ele('text:我知道了') or self.page.ele('.ant-modal-close') or self.page.ele('@aria-label=Close')
                if pop_btn:
                    logger.info("关闭公告弹窗...")
                    pop_btn.click()
                    time.sleep(1)
            except: pass

            # 2. 点击侧边栏 [每日签到] 以加载数据和按钮
            logger.info("4. 寻找 [每日签到] 侧边栏...")
            sidebar = None
            end_time = time.time() + 10
            while time.time() < end_time:
                sidebar = self.page.ele('x://a[contains(., "每日签到")]')
                if not sidebar: sidebar = self.page.ele('@data-section=checkin')
                if sidebar: break
                time.sleep(1)
            
            # 移动端兼容
            if not sidebar:
                menu_btn = self.page.ele('.navbar-toggler') or self.page.ele('button[class*="toggle"]')
                if menu_btn:
                    menu_btn.click()
                    time.sleep(1)
                    sidebar = self.page.ele('x://a[contains(., "每日签到")]')

            if sidebar:
                logger.info(">>> 点击侧边栏 <<<")
                try: sidebar.click()
                except: self.page.run_js('arguments[0].click()', sidebar)
                time.sleep(3) # 等待数据加载
            else:
                logger.error("!!! 无法找到侧边栏，尝试直接查找 ID !!!")

            # 3. 核心：基于 ID 处理签到按钮
            # 按钮 ID: checkin-btn
            self.handle_turnstile()

            logger.info("检查签到按钮 (#checkin-btn)...")
            btn = self.page.ele('#checkin-btn')
            
            if btn:
                # 检查是否已签到：
                # 1. 文本包含 "已"
                # 2. 存在 disabled 属性
                is_disabled = btn.attr('disabled') is not None
                btn_text = btn.text
                
                if "已" in btn_text or is_disabled:
                    self.stats["status"] = "今日已签到"
                    logger.info(f"状态：已签到 (文本:{btn_text}, Disabled:{is_disabled})")
                else:
                    logger.info("状态：未签到，执行点击...")
                    self.handle_turnstile()
                    
                    btn.click()
                    time.sleep(3) # 等待结果刷新
                    self.handle_turnstile()
                    
                    self.stats["status"] = "今日签到成功"
                    logger.info("签到动作完成")
            else:
                # 假如页面还没加载出来，或者ID变了
                if "已签到" in self.page.html:
                    self.stats["status"] = "今日已签到 (无按钮)"
                else:
                    self.stats["status"] = "异常：未找到 #checkin-btn"

            # 4. 数据读取 - 基于具体 ID
            logger.info("读取统计数据...")
            time.sleep(2)
            
            # 今日奖励: id="today-reward", 单位 GB
            self.stats["today_reward"] = self.get_id_text("today-reward", "GB")
            
            # 累计获得: id="total-checkin-traffic", 单位 GB
            self.stats["total_traffic"] = self.get_id_text("total-checkin-traffic", "GB")
            
            # 累计签到: id="total-checkins", 单位 天
            self.stats["total_days"] = self.get_id_text("total-checkins", "天")
            
            # 连续签到: id="continuous-days", 单位 天
            self.stats["streak_days"] = self.get_id_text("continuous-days", "天")
            
            logger.info(f"数据读取完毕: {self.stats}")
            return True

        except Exception as e:
            err_msg = f"流程出错: {str(e)[:100]}"
            self.stats["status"] = err_msg
            logger.error(err_msg)
            return False

    def run(self):
        self.init_browser()
        try:
            if self.login():
                self.checkin_flow()
                return True, self.stats
            return False, {"status": "登录失败"}
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
        
        acc_str = os.getenv('ICMP9_ACCOUNTS', '').strip()
        if acc_str:
            for pair in acc_str.split(','):
                if ':' in pair:
                    p = pair.split(':', 1)
                    accounts.append({'email': p[0].strip(), 'password': p[1].strip()})
        return accounts

    def send_notify(self, results):
        if not self.bot_token or not self.chat_id: return
        
        msg = "✈️ <b>ICMP9 签到报告</b>\n"
        msg += f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        msg += "-" * 25 + "\n"
        
        for email, success, stats in results:
            mask_email = email.split('@')[0][:3] + "***" 
            is_ok = "已" in stats['status'] or "成功" in stats['status']
            status_icon = "✅" if is_ok else "⚠️"
            
            msg += f"👤 <b>账号:</b> {mask_email}\n"
            msg += f"{status_icon} <b>状态:</b> {stats['status']}\n"
            
            if is_ok:
                msg += f"\n"
                msg += f"🎁 <b>今日奖励:</b> {stats['today_reward']}\n"
                msg += f"📊 <b>累计获得:</b> {stats['total_traffic']}\n"
                msg += f"🗓 <b>累计签到:</b> {stats['total_days']}\n"
                msg += f"🔥 <b>连续签到:</b> {stats['streak_days']}\n"
            else:
                msg += f"❌ 错误信息: {stats.get('status')}\n"
                
            msg += "-" * 25 + "\n"

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        requests.post(url, json={"chat_id": self.chat_id, "text": msg, "parse_mode": "HTML"})

    def run_all(self):
        results = []
        for acc in self.accounts:
            task = ICMP9Checkin(acc['email'], acc['password'])
            success, stats = task.run()
            results.append((acc['email'], success, stats))
            time.sleep(5)
        self.send_notify(results)

if __name__ == "__main__":
    MultiAccountManager().run_all()
