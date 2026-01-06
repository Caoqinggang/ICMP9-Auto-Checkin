#!/usr/bin/env python3
"""
ICMP9 DrissionPage 自动签到脚本 (最终逻辑修正版)
流程：
1. 打开 https://icmp9.com/user/login 登录
2. 登录成功跳转至 /user/dashboard
3. 点击侧边栏 [每日签到]
4. 两种情况处理：
   - 未签到：过人机验证 -> 点击签到 -> 抓取数据
   - 已签到：直接抓取数据
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
        self.base_url = "https://icmp9.com"
        # 初始化数据容器
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
        # GitHub Actions 环境配置
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
        处理 Cloudflare 验证
        循环检测 5 秒，如果有验证框则点击
        """
        try:
            start_time = time.time()
            while time.time() - start_time < 5:
                # 查找 Cloudflare iframe
                iframe = self.page.get_frame('@src^https://challenges.cloudflare.com')
                if iframe:
                    # 尝试点击 checkbox 或 body
                    btn = iframe.ele('tag:input') or iframe.ele('@type=checkbox') or iframe.ele('text=Verify you are human')
                    if btn:
                        logger.info("检测到 Cloudflare 验证，正在点击...")
                        btn.click()
                        time.sleep(3) # 点击后等待加载
                        return True
                time.sleep(0.5)
            return False
        except:
            return False

    def login(self):
        """步骤 1 & 2: 登录流程"""
        try:
            login_url = f"{self.base_url}/user/login"
            logger.info(f"[{self.email}] 1. 打开登录页: {login_url}")
            self.page.get(login_url)
            
            self.handle_turnstile() # 登录页可能有验证
            
            # 输入账号
            logger.info("2. 输入账号密码...")
            email_ele = self.page.ele('css:input[type="email"]') or self.page.ele('css:input[name="email"]')
            if not email_ele:
                # 尝试应对可能的页面结构差异
                email_ele = self.page.ele('@placeholder:邮箱')
            
            if not email_ele:
                logger.error("找不到邮箱输入框")
                return False
                
            email_ele.input(self.email)
            
            pass_ele = self.page.ele('css:input[type="password"]')
            pass_ele.input(self.password)
            
            # 点击登录
            login_btn = self.page.ele('css:button[type="submit"]') or self.page.ele('text:登录')
            if login_btn:
                login_btn.click()
            
            time.sleep(3)
            self.handle_turnstile() # 登录后跳转验证
            
            # 步骤 3: 验证是否到达 Dashboard
            if "dashboard" in self.page.url or "user" in self.page.url:
                logger.info("3. 登录成功，已到达 Dashboard")
                return True
            
            logger.error(f"登录失败，当前URL: {self.page.url}")
            return False
        except Exception as e:
            logger.error(f"登录异常: {e}")
            return False

    def get_stat_value(self, label_text):
        """
        通用数据抓取逻辑：
        根据标签(如'今日奖励') -> 向上找父级容器 -> 正则提取容器内的数字
        """
        try:
            # 1. 定位标签
            label_ele = self.page.ele(f'text:{label_text}')
            if not label_ele: return "未找到标签"

            # 2. 向上寻找包含数字的容器
            target_text = ""
            container = label_ele
            
            # 向上找最多4层
            for _ in range(4): 
                container = container.parent()
                if not container: break
                text = container.text
                # 如果去掉标签文字后还有数字，说明找对地方了
                clean_text = text.replace(label_text, "").strip()
                if any(char.isdigit() for char in clean_text):
                    target_text = clean_text
                    break
            
            if not target_text: return "未找到数值"

            # 3. 正则提取 (匹配数字+单位)
            pattern = r'(\d+(\.\d+)?\s*(GB|MB|KB|B|TB|天|Days?)?)'
            match = re.search(pattern, target_text, re.IGNORECASE)
            
            if match:
                return match.group(1).strip()
            return "格式不匹配"
        except:
            return "N/A"

    def checkin_flow(self):
        """步骤 4: 签到核心流程"""
        try:
            # 确保在 dashboard
            if "dashboard" not in self.page.url:
                self.page.get(f"{self.base_url}/user/dashboard")
                time.sleep(3)

            # ==========================================
            # 4. 点击侧边栏“每日签到”
            # ==========================================
            logger.info("4. 寻找并点击 [每日签到]...")
            sidebar = self.page.ele('text=每日签到') or self.page.ele('@@text=每日签到')
            
            if sidebar:
                sidebar.click()
                logger.info("已点击侧边栏，等待弹窗/页面加载...")
                time.sleep(3) 
            else:
                logger.warning("未找到侧边栏按钮，尝试直接检测页面内容")

            # ==========================================
            # 逻辑分支：判断是否需要签到
            # ==========================================
            
            # 关闭可能的公告弹窗 (干扰项)
            try:
                close = self.page.ele('@aria-label=Close') or self.page.ele('.ant-modal-close')
                if close: close.click()
            except: pass

            logger.info("检查签到按钮状态...")
            # 寻找主要的签到操作按钮
            action_btn = self.page.ele('text:签到') or self.page.ele('text:Check in') or self.page.ele('text:已签到')
            
            if action_btn:
                btn_text = action_btn.text
                
                # --- 情况 (2): 今日已签到 ---
                if "已" in btn_text:
                    self.stats["status"] = "今日已签到"
                    logger.info("状态：检测到今日已签到，跳过点击")
                
                # --- 情况 (1): 今日还未签到 ---
                else:
                    logger.info("状态：未签到，开始签到流程")
                    
                    # 1. 先完成人机验证 (要求)
                    logger.info("执行前置验证检查...")
                    self.handle_turnstile()
                    
                    # 2. 点击“签到”按键
                    logger.info("点击 [签到] 按钮...")
                    action_btn.click()
                    
                    # 点击后等待
                    time.sleep(3)
                    
                    # 点击后可能再次出现验证，或者结果弹窗
                    self.handle_turnstile()
                    
                    self.stats["status"] = "今日签到成功"
                    logger.info("签到动作完成")
            else:
                # 兜底：如果没有按钮，检查页面文字
                if "已签到" in self.page.html:
                    self.stats["status"] = "今日已签到 (无按钮)"
                else:
                    self.stats["status"] = "异常：未找到签到按钮"

            # ==========================================
            # 数据读取 (两种情况共用)
            # ==========================================
            logger.info("开始读取数据...")
            time.sleep(2) # 等待数据刷新
            
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
        # 优先读取单账号配置
        s_email = os.getenv('ICMP9_EMAIL', '').strip()
        s_pass = os.getenv('ICMP9_PASSWORD', '').strip()
        if s_email and s_pass:
            accounts.append({'email': s_email, 'password': s_pass})
        
        # 读取多账号配置
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
            # 状态判定
            is_ok = "已" in stats['status'] or "成功" in stats['status']
            status_icon = "✅" if is_ok else "⚠️"
            
            msg += f"👤 <b>账号:</b> {mask_email}\n"
            msg += f"{status_icon} <b>状态:</b> {stats['status']}\n"
            
            # 只有成功抓取到数据才显示详情
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
