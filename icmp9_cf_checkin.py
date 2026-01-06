#!/usr/bin/env python3
"""
ICMP9 DrissionPage 自动签到脚本 (最终逻辑版)
流程：
1. 登录 -> 点击侧边栏[每日签到]
2. 自动检测并通过 Cloudflare 人机验证
3. 判断按钮状态：
   - 若未签到：点击签到 -> 等待结果
   - 若已签到：跳过点击
4. 抓取：今日奖励、累计获得、累计签到、连续签到
5. 发送 Telegram 通知
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
        self.stats = {
            "status": "未知",
            "today_reward": "0 MB", 
            "total_traffic": "0 GB", 
            "total_days": "0 天",    
            "streak_days": "0 天"    
        }
        
    def init_browser(self):
        """初始化浏览器 (Xvfb模式兼容)"""
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
        """
        专门处理 Cloudflare 验证
        会在 5 秒内尝试寻找并点击验证框
        """
        try:
            # 查找 Cloudflare iframe
            # 这里的逻辑是：如果页面上有验证框，就点它；没有就跳过
            start_time = time.time()
            while time.time() - start_time < 5:
                iframe = self.page.get_frame('@src^https://challenges.cloudflare.com')
                if iframe:
                    logger.info("检测到人机验证，正在尝试通过...")
                    # 尝试点击 checkbox 或 body
                    btn = iframe.ele('tag:input') or iframe.ele('@type=checkbox') or iframe.ele('text=Verify you are human')
                    if btn:
                        btn.click()
                        time.sleep(2) # 点击后等待一下让CF反应
                        logger.info("已点击验证框")
                        return True
                time.sleep(0.5)
            return False
        except Exception as e:
            # 验证过程出错不应阻断流程，可能只是因为没有验证框
            return False

    def login(self):
        """登录流程"""
        try:
            logger.info(f"[{self.email}] 打开登录页...")
            self.page.get('https://icmp9.com/user')
            self.handle_turnstile() # 登录页可能有验证
            
            # 输入账号
            email_ele = self.page.ele('css:input[type="username"]') or self.page.ele('css:input[name="username"]')
            if not email_ele:
                logger.error("找不到邮箱输入框，可能被拦截")
                return False
                
            email_ele.input(self.email)
            self.page.ele('css:input[type="password"]').input(self.password)
            
            # 点击登录
            self.page.ele('css:button[type="submit"]').click()
            time.sleep(3)
            self.handle_turnstile() # 登录后跳转可能有验证
            
            # 验证登录
            if "dashboard" in self.page.url or "user" in self.page.url:
                logger.info("登录成功")
                return True
            return False
        except Exception as e:
            logger.error(f"登录异常: {e}")
            return False

    def get_stat_value(self, label_text):
        """
        根据标签文本(如'今日奖励')抓取数值
        使用正则提取，防止提取到多余文字
        """
        try:
            # 1. 定位标签
            label_ele = self.page.ele(f'text:{label_text}')
            if not label_ele: return "未找到"

            # 2. 向上找容器 (Card)
            container = label_ele.parent(2)
            if not container: return "定位失败"

            # 3. 清洗文本
            full_text = container.text
            text_without_label = full_text.replace(label_text, "").strip()
            
            # 4. 正则匹配 (数字 + 可选单位)
            # 匹配示例: "5.06 GB", "10 天", "68.37"
            pattern = r'(\d+(\.\d+)?\s*(GB|MB|KB|B|TB|天|Days?)?)'
            match = re.search(pattern, text_without_label, re.IGNORECASE)
            
            if match:
                return match.group(1).strip()
            
            # 保底策略
            lines = text_without_label.split('\n')
            for line in lines:
                if any(c.isdigit() for c in line) and len(line) < 20:
                    return line.strip()
            return "提取失败"
        except:
            return "N/A"

    def checkin(self):
        """签到主流程"""
        try:
            # 确保在 dashboard
            if "dashboard" not in self.page.url:
                self.page.get("https://icmp9.com/dashboard")
                time.sleep(3)
            
            # ==========================================
            # 1. 点击侧边栏 [每日签到]
            # ==========================================
            logger.info("点击侧边栏 [每日签到]...")
            sidebar_menu = self.page.ele('text=每日签到') or self.page.ele('@@text=每日签到')
            
            if sidebar_menu:
                sidebar_menu.click()
                time.sleep(3) # 等待右侧加载
            else:
                logger.warning("未找到侧边栏按钮，尝试直接寻找内容")

            # ==========================================
            # 2. 核心：处理人机验证 (情况1: 签到前验证)
            # ==========================================
            # 在判断按钮之前，先跑一次验证，防止验证框遮挡按钮或阻止加载
            self.handle_turnstile()

            # 关闭可能的弹窗
            try:
                close = self.page.ele('@aria-label=Close') or self.page.ele('.ant-modal-close')
                if close: close.click()
            except: pass

            # ==========================================
            # 3. 判断按钮状态 (情况1 vs 情况2)
            # ==========================================
            logger.info("检查签到按钮状态...")
            
            # 查找大按钮
            btn = self.page.ele('text:签到') or self.page.ele('text:Check in') or self.page.ele('text:已签到')
            
            status_text = "未知"
            if btn:
                btn_text = btn.text
                if "已" in btn_text:
                    # --- 情况2: 今日已签到 ---
                    self.stats["status"] = "今日已签到"
                    logger.info("状态：今日已签到，直接读取数据")
                else:
                    # --- 情况1: 今日未签到 ---
                    logger.info("状态：未签到，准备点击...")
                    
                    # 再次确保没有验证框遮挡
                    self.handle_turnstile()
                    
                    # 点击签到
                    btn.click()
                    time.sleep(3) # 等待结果弹窗或状态改变
                    
                    # 点击后可能还会出现验证
                    self.handle_turnstile()
                    
                    self.stats["status"] = "今日签到成功"
                    logger.info("操作：签到点击完成")
            else:
                # 假如没有按钮，检查页面文字
                if "已签到" in self.page.html:
                    self.stats["status"] = "今日已签到"
                else:
                    self.stats["status"] = "未找到签到按钮"
                    logger.warning("异常：未找到按钮")

            # ==========================================
            # 4. 读取数据 (所有情况共用)
            # ==========================================
            logger.info("正在抓取统计数据...")
            time.sleep(2) # 确保数据已刷新
            
            self.stats["today_reward"] = self.get_stat_value("今日奖励")
            self.stats["total_traffic"] = self.get_stat_value("累计获得")
            self.stats["total_days"] = self.get_stat_value("累计签到")
            self.stats["streak_days"] = self.get_stat_value("连续签到")
            
            logger.info(f"抓取结果: {self.stats}")
            return True

        except Exception as e:
            err_msg = f"出错: {str(e)[:50]}"
            self.stats["status"] = err_msg
            logger.error(err_msg)
            return False

    def run(self):
        self.init_browser()
        try:
            if self.login():
                self.checkin()
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
        single_email = os.getenv('ICMP9_EMAIL', '').strip()
        single_pass = os.getenv('ICMP9_PASSWORD', '').strip()
        if single_email and single_pass:
            accounts.append({'email': single_email, 'password': single_pass})
        
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
            mask_email = email.split('@')[0][:3] + "***@" + email.split('@')[1]
            status_icon = "✅" if "已" in stats['status'] or "成功" in stats['status'] else "⚠️"
            
            msg += f"👤 <b>账号:</b> {mask_email}\n"
            msg += f"{status_icon} <b>状态:</b> {stats['status']}\n"
            msg += f"\n"
            msg += f"🎁 <b>今日奖励:</b> {stats['today_reward']}\n"
            msg += f"📊 <b>累计获得:</b> {stats['total_traffic']}\n"
            msg += f"🗓 <b>累计签到:</b> {stats['total_days']}\n"
            msg += f"🔥 <b>连续签到:</b> {stats['streak_days']}\n"
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
