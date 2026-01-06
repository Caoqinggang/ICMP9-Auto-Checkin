#!/usr/bin/env python3
"""
ICMP9 DrissionPage 自动签到脚本 (修复侧边栏定位版)
更新点：
1. 使用 data-section="checkin" 精准定位侧边栏
2. 增加模糊文本匹配作为备选
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
            "today_reward": "0 MB", 
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
        co.set_argument('--lang=zh-CN') 
        co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        self.page = ChromiumPage(co)
        self.page.set.timeouts(15)

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
            email_ele = self.page.ele('css:input[type="email"]') or self.page.ele('css:input[name="email"]')
            if not email_ele:
                email_ele = self.page.ele('@placeholder:邮箱')
            
            if not email_ele:
                logger.error("找不到邮箱输入框")
                return False
                
            email_ele.input(self.email)
            self.page.ele('css:input[type="password"]').input(self.password)
            
            login_btn = self.page.ele('css:button[type="submit"]') or self.page.ele('text:登录')
            if login_btn: login_btn.click()
            
            time.sleep(3)
            self.handle_turnstile()
            
            if "dashboard" in self.page.url or "user" in self.page.url:
                logger.info("3. 登录成功，已到达 Dashboard")
                return True
            
            logger.error(f"登录失败，当前URL: {self.page.url}")
            return False
        except Exception as e:
            logger.error(f"登录异常: {e}")
            return False

    def get_stat_value(self, label_text):
        """数据抓取逻辑"""
        try:
            label_ele = self.page.ele(f'text:{label_text}')
            if not label_ele: return "未找到标签"

            target_text = ""
            container = label_ele
            for _ in range(4): 
                container = container.parent()
                if not container: break
                text = container.text
                clean_text = text.replace(label_text, "").strip()
                if any(char.isdigit() for char in clean_text):
                    target_text = clean_text
                    break
            
            if not target_text: return "未找到数值"

            pattern = r'(\d+(\.\d+)?\s*(GB|MB|KB|B|TB|天|Days?)?)'
            match = re.search(pattern, target_text, re.IGNORECASE)
            if match: return match.group(1).strip()
            return "格式不匹配"
        except:
            return "N/A"

    def checkin_flow(self):
        """签到核心流程 (修复侧边栏定位)"""
        try:
            if "dashboard" not in self.page.url:
                self.page.get(f"{self.base_url}/user/dashboard")
                time.sleep(3)

            # ==========================================
            # 4. 点击侧边栏“每日签到” (修复重点)
            # ==========================================
            logger.info("4. 寻找并点击 [每日签到]...")
            
            # 策略1: 使用 data-section 属性 (最稳)
            sidebar = self.page.ele('@data-section=checkin')
            
            # 策略2: 使用模糊文本包含 (text: 而不是 text=)
            if not sidebar:
                logger.info("属性定位失败，尝试模糊文本定位...")
                sidebar = self.page.ele('text:每日签到')
            
            # 策略3: 寻找包含该文本的链接
            if not sidebar:
                sidebar = self.page.ele('tag:a@@text:每日签到')

            if sidebar:
                # 滚动到元素可见，防止被遮挡
                # self.page.scroll.to_ele(sidebar) 
                sidebar.click()
                logger.info(">>> 已成功点击侧边栏菜单 <<<")
                time.sleep(3) 
            else:
                logger.error("!!! 严重错误: 彻底无法找到侧边栏按钮，无法继续 !!!")
                # 打印一下页面HTML结构帮助调试 (可选)
                # logger.info(self.page.html[:1000]) 
                return False

            # ==========================================
            # 逻辑分支：判断是否需要签到
            # ==========================================
            try:
                close = self.page.ele('@aria-label=Close') or self.page.ele('.ant-modal-close')
                if close: close.click()
            except: pass

            logger.info("检查签到按钮状态...")
            action_btn = self.page.ele('text:签到') or self.page.ele('text:Check in') or self.page.ele('text:已签到')
            
            if action_btn:
                btn_text = action_btn.text
                if "已" in btn_text:
                    self.stats["status"] = "今日已签到"
                    logger.info("状态：检测到今日已签到，跳过点击")
                else:
                    logger.info("状态：未签到，开始签到流程")
                    logger.info("执行前置验证检查...")
                    self.handle_turnstile()
                    
                    logger.info("点击 [签到] 按钮...")
                    action_btn.click()
                    time.sleep(3)
                    self.handle_turnstile()
                    
                    self.stats["status"] = "今日签到成功"
                    logger.info("签到动作完成")
            else:
                if "已签到" in self.page.html:
                    self.stats["status"] = "今日已签到 (无按钮)"
                else:
                    self.stats["status"] = "异常：未找到签到按钮"

            # ==========================================
            # 数据读取
            # ==========================================
            logger.info("开始读取数据...")
            time.sleep(2)
            
            self.stats["today_reward"] = self.get_stat_value("今日奖励")
            self.stats["total_traffic"] = self.get_stat_value("累计获得")
            self.stats["total_days"] = self.get_stat_value("累计签到")
            self.stats["streak_days"] = self.get_stat_value("连续签到")
            
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
