#!/usr/bin/env python3
"""
ICMP9 DrissionPage 自动签到脚本 (弹窗完美修复版)
更新内容：
1. 登录后优先循环检测并关闭“我知道了”弹窗
2. 精准定位侧边栏 <a data-section="checkin">
3. 精准操作签到按钮 #checkin-btn
4. 精准提取 ID 数据
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
                        logger.info("检测到验证框，点击...")
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
            email_ele = self.page.ele('css:input[type="email"]') or self.page.ele('@placeholder:邮箱')
            
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
            ele = self.page.ele(f'#{ele_id}')
            if ele:
                val = ele.text.strip()
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

            # ==========================================
            # 1. 优先处理弹窗 (新增重点)
            # ==========================================
            logger.info("4. 检查 [欢迎来到ICMP9] 弹窗...")
            
            # 循环检测几秒，防止弹窗有动画延迟
            for _ in range(5):
                # 精准匹配按钮文字 "我知道了"
                pop_btn = self.page.ele('text=我知道了')
                
                # 备用：右上角关闭图标
                if not pop_btn:
                    pop_btn = self.page.ele('@aria-label=Close') or self.page.ele('.ant-modal-close')
                
                if pop_btn:
                    logger.info(">>> 发现弹窗，点击 [我知道了] <<<")
                    try:
                        pop_btn.click()
                    except:
                        # 强制JS点击
                        self.page.run_js('arguments[0].click()', pop_btn)
                    
                    # 关键：点击后必须等待遮罩层消失，否则无法点击下面的菜单
                    time.sleep(2)
                    break
                time.sleep(1)

            # ==========================================
            # 2. 点击导航栏 (nav-item)
            # ==========================================
            logger.info("5. 寻找导航菜单 [每日签到]...")
            
            # 使用 CSS 选择器精确定位
            nav_item = self.page.ele('css:a[data-section="checkin"]')
            
            if not nav_item:
                nav_item = self.page.ele('@data-section=checkin')

            if nav_item:
                logger.info(">>> 点击导航菜单: 每日签到 <<<")
                try:
                    nav_item.click()
                except:
                    self.page.run_js('arguments[0].click()', nav_item)
                time.sleep(3)
            else:
                logger.error("!!! 无法找到导航菜单 [data-section='checkin'] !!!")
                # 尝试点击移动端菜单
                menu_btn = self.page.ele('.navbar-toggler') or self.page.ele('button[class*="toggle"]')
                if menu_btn:
                    logger.info("尝试点击移动端菜单...")
                    menu_btn.click()
                    time.sleep(1)
                    nav_item = self.page.ele('css:a[data-section="checkin"]')
                    if nav_item: nav_item.click()

            # ==========================================
            # 3. 操作签到按钮 #checkin-btn
            # ==========================================
            logger.info("6. 寻找签到按钮 [#checkin-btn]...")
            self.handle_turnstile()

            # 简单的重试机制
            checkin_btn = None
            for _ in range(5):
                checkin_btn = self.page.ele('#checkin-btn')
                if checkin_btn: break
                time.sleep(1)
            
            if checkin_btn:
                btn_text = checkin_btn.text
                is_disabled = checkin_btn.attr('disabled') is not None
                
                if "已" in btn_text or is_disabled:
                    self.stats["status"] = "今日已签到"
                    logger.info(f"状态：已签到 (文本: {btn_text})")
                else:
                    logger.info("状态：未签到，执行点击...")
                    self.handle_turnstile()
                    
                    checkin_btn.click()
                    time.sleep(3)
                    self.handle_turnstile()
                    
                    self.stats["status"] = "今日签到成功"
                    logger.info("签到动作完成")
            else:
                if "已签到" in self.page.html:
                    self.stats["status"] = "今日已签到 (无按钮)"
                else:
                    self.stats["status"] = "异常：未找到 #checkin-btn"

            # ==========================================
            # 4. 数据读取 (ID 定位)
            # ==========================================
            logger.info("7. 读取统计数据...")
            time.sleep(2)
            
            self.stats["today_reward"] = self.get_id_text("today-reward", "GB")
            self.stats["total_traffic"] = self.get_id_text("total-checkin-traffic", "GB")
            self.stats["total_days"] = self.get_id_text("total-checkins", "天")
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
