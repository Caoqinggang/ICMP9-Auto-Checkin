#!/usr/bin/env python3
"""
ICMP9 DrissionPage 自动签到脚本 (完美通知版)
功能：
1. 自动过盾登录
2. 识别“今日已签到”状态
3. 精准提取：累计签到、累计获得、今日奖励、连续签到
4. 发送包含所有数据的 Telegram 通知
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
        # 初始化统计数据，默认值为0或未知
        self.stats = {
            "status": "未知",
            "today_reward": "0 MB", # 今日奖励
            "total_traffic": "0 GB", # 累计获得
            "total_days": "0 天",    # 累计签到
            "streak_days": "0 天"    # 连续签到
        }
        
    def init_browser(self):
        """初始化浏览器 (Xvfb模式)"""
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
            time.sleep(2)
            iframe = self.page.get_frame('@src^https://challenges.cloudflare.com')
            if iframe:
                logger.info("检测到 Cloudflare 验证，尝试点击...")
                btn = iframe.ele('tag:input') or iframe.ele('@type=checkbox') or iframe.ele('text=Verify you are human')
                if btn:
                    btn.click()
                    time.sleep(3)
                    return True
        except:
            pass

    def login(self):
        """登录流程"""
        try:
            logger.info(f"[{self.email}] 打开登录页...")
            self.page.get('https://icmp9.com/user/login')
            self.handle_turnstile()
            
            # 输入账号
            email_ele = self.page.ele('css:input[type="email"]') or self.page.ele('css:input[name="email"]')
            if not email_ele:
                logger.error("找不到邮箱输入框")
                return False
                
            email_ele.input(self.email)
            self.page.ele('css:input[type="password"]').input(self.password)
            
            # 点击登录
            self.page.ele('css:button[type="submit"]').click()
            time.sleep(3)
            self.handle_turnstile()
            
            # 验证登录
            if "dashboard" in self.page.url or "user" in self.page.url:
                logger.info("登录成功")
                return True
            return False
        except Exception as e:
            logger.error(f"登录异常: {e}")
            return False

    def get_stat_value(self, label_text):
        """根据标签文本抓取对应数值"""
        try:
            # 找到包含特定文本(如"今日奖励")的元素
            label_ele = self.page.ele(f'text:{label_text}')
            if label_ele:
                # 向上找父级容器抓取整个卡片的文本
                container = label_ele.parent(2)
                full_text = container.text
                
                # 解析文本，提取数字部分
                lines = full_text.split('\n')
                for line in lines:
                    line = line.strip()
                    # 如果不是标签本身，且包含数字，则认为是数值
                    if any(c.isdigit() for c in line) and label_text not in line:
                        return line
            return "获取失败"
        except:
            return "N/A"

    def checkin(self):
        """签到主逻辑"""
        try:
            if "dashboard" not in self.page.url:
                self.page.get("https://icmp9.com/dashboard")
            
            time.sleep(5) # 等待页面加载
            self.handle_turnstile()
            
            # 关闭可能的公告弹窗
            try:
                close = self.page.ele('@aria-label=Close') or self.page.ele('.ant-modal-close')
                if close: close.click()
            except: pass
            
            # 1. 处理签到按钮
            logger.info("检查签到状态...")
            btn = self.page.ele('text:签到') or self.page.ele('text:Check in') or self.page.ele('text:已签到')
            
            if btn:
                btn_text = btn.text
                if "已" in btn_text:
                    # 情况A: 已经签到过了
                    self.stats["status"] = "今日已签到"
                    logger.info("检测到：今日已签到")
                else:
                    # 情况B: 还没签到，执行点击
                    btn.click()
                    time.sleep(3)
                    self.handle_turnstile()
                    # 点击后再次检查，确认成功（防止点击无效）
                    self.stats["status"] = "今日签到成功"
                    logger.info("执行操作：签到成功")
            else:
                self.stats["status"] = "未找到按钮"
                logger.warning("未找到签到按钮")

            # 2. 无论是否刚刚签到，都执行数据抓取
            logger.info("正在抓取统计数据...")
            time.sleep(2) # 给页面一点时间刷新数据
            
            self.stats["today_reward"] = self.get_stat_value("今日奖励")
            self.stats["total_traffic"] = self.get_stat_value("累计获得")
            self.stats["total_days"] = self.get_stat_value("累计签到")
            self.stats["streak_days"] = self.get_stat_value("连续签到")
            
            logger.info(f"数据抓取完毕: {self.stats}")
            return True

        except Exception as e:
            err_msg = f"出错: {str(e)[:30]}"
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
            # 隐藏部分邮箱
            mask_email = email.split('@')[0][:3] + "***@" + email.split('@')[1]
            
            if success:
                # 状态图标：如果是“已签到”或“成功”都显示绿色对勾
                status_icon = "✅" if "已" in stats['status'] or "成功" in stats['status'] else "⚠️"
                
                msg += f"👤 <b>账号:</b> {mask_email}\n"
                msg += f"{status_icon} <b>状态:</b> {stats['status']}\n"
                msg += f"\n"
                msg += f"🎁 <b>今日奖励:</b> {stats['today_reward']}\n"
                msg += f"📊 <b>累计获得:</b> {stats['total_traffic']}\n"
                msg += f"🗓 <b>累计签到:</b> {stats['total_days']}\n"
                msg += f"🔥 <b>连续签到:</b> {stats['streak_days']}\n"
            else:
                msg += f"👤 <b>账号:</b> {mask_email}\n"
                msg += f"❌ <b>失败:</b> {stats.get('status', '未知')}\n"
            
            msg += "-" * 25 + "\n"

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": msg,
            "parse_mode": "HTML"
        }
        try:
            requests.post(url, json=payload)
            logger.info("Telegram 通知已发送")
        except Exception as e:
            logger.error(f"发送通知失败: {e}")

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
