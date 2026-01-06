#!/usr/bin/env python3
"""
ICMP9 DrissionPage 最终完整版
功能：
1. 登录成功后截图
2. 签到逻辑修正：未签到时，先执行 CF 验证，再点击按钮
3. 签到完成后截图
4. Telegram 通知：包含详细文字报告 + 2张现场截图
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
        self.screenshots = [] # 存储截图路径
        
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

    def take_screenshot(self, name_suffix):
        """截图辅助函数"""
        try:
            # 简单的文件命名
            safe_name = self.email.split('@')[0]
            filename = f"{safe_name}_{name_suffix}.png"
            self.page.get_screenshot(path=filename, full_page=True)
            logger.info(f"📸 已保存截图: {filename}")
            return filename
        except Exception as e:
            logger.error(f"截图失败: {e}")
            return None

    def handle_turnstile(self):
        """处理验证码"""
        try:
            iframe = self.page.ele('css:iframe[src*="cloudflare"]', timeout=5)
            if iframe:
                frame_doc = self.page.get_frame(iframe)
                if frame_doc:
                    frame_doc.ele('tag:body').click()
                    cb = frame_doc.ele('@type=checkbox')
                    if cb: cb.click()
                    time.sleep(3)
        except: pass

    def login(self):
        """登录逻辑"""
        try:
            logger.info("1. 访问登录页...")
            self.page.get(f"{self.base_url}/user/login")
            time.sleep(3)
            
            self.handle_turnstile()
            
            logger.info("2. 输入账号信息...")
            self.page.ele('#username').input(self.email)
            self.page.ele('css:input[type="password"]').input(self.password)
            
            logger.info("3. 点击登录...")
            self.handle_turnstile()
            self.page.ele('css:button[type="submit"]').click()
            
            logger.info("4. 等待跳转...")
            time.sleep(5)
            
            login_success = False
            if "dashboard" in self.page.url:
                login_success = True
            elif "login" in self.page.url:
                logger.info("⚠️ 尝试二次点击...")
                self.handle_turnstile()
                time.sleep(2)
                self.page.ele('css:button[type="submit"]').click()
                time.sleep(5)
                if "dashboard" in self.page.url:
                    login_success = True

            if login_success:
                logger.info("✅ 登录成功")
                # [截图1] 登录成功
                shot = self.take_screenshot("登录成功截图")
                if shot: self.screenshots.append(shot)
                return True
                
            return False

        except Exception as e:
            logger.error(f"登录出错: {e}")
            return False

    def get_id_text(self, ele_id, unit=""):
        try:
            ele = self.page.ele(f'#{ele_id}', timeout=2)
            return f"{ele.text.strip()} {unit}" if ele else "未找到"
        except: return "N/A"

    def checkin_flow(self):
        """签到流程"""
        try:
            if "dashboard" not in self.page.url:
                self.page.get(f"{self.base_url}/user/dashboard")
                time.sleep(5)

            # 1. 清理弹窗
            logger.info("清理弹窗...")
            try:
                self.page.run_js("document.querySelectorAll('.ant-modal-mask, .ant-modal-wrap, .modal-backdrop').forEach(m => m.remove())")
                pop = self.page.ele('text=我知道了')
                if pop: pop.click()
            except: pass
            time.sleep(1)

            # 2. 点击侧边栏
            logger.info("点击 [每日签到]...")
            nav = self.page.ele('@data-section=checkin')
            if nav:
                self.page.run_js('arguments[0].click()', nav)
                time.sleep(3)
            else:
                menu = self.page.ele('.navbar-toggler')
                if menu:
                    menu.click()
                    time.sleep(1)
                    self.page.ele('@data-section=checkin').click()
                    time.sleep(3)

            # 3. 签到逻辑
            logger.info("检测签到状态...")
            btn = self.page.ele('#checkin-btn')
            if btn:
                if "已" in btn.text or btn.attr('disabled'):
                    self.stats["status"] = "今日已签到"
                    logger.info("状态: 已签到")
                else:
                    logger.info("状态: 未签到，准备签到")
                    # 未签到时，先验证，再点击
                    self.handle_turnstile()
                    self.page.run_js('arguments[0].click()', btn)
                    time.sleep(5)
                    self.handle_turnstile()
                    
                    self.stats["status"] = "今日签到成功"
                    logger.info("状态: 签到成功")
            else:
                self.stats["status"] = "未找到按钮"

            # 4. 读取数据
            logger.info("读取数据...")
            self.stats["today_reward"] = self.get_id_text("today-reward", "GB")
            self.stats["total_traffic"] = self.get_id_text("total-checkin-traffic", "GB")
            self.stats["total_days"] = self.get_id_text("total-checkins", "天")
            self.stats["streak_days"] = self.get_id_text("continuous-days", "天")
            
            logger.info(f"结果: {self.stats}")
            
            # [截图2] 签到状态/数据读取后
            shot = self.take_screenshot("签到状态截图")
            if shot: self.screenshots.append(shot)
            
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
            # 返回三个值：结果、状态、截图列表
            return True, self.stats, self.screenshots
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

    def send_photo(self, file_path, caption=None):
        """发送单张图片"""
        if not os.path.exists(file_path): return
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
        try:
            with open(file_path, 'rb') as f:
                data = {'chat_id': self.chat_id}
                if caption:
                    data['caption'] = caption
                requests.post(url, data=data, files={'photo': f})
                logger.info(f"已发送图片: {file_path}")
        except Exception as e:
            logger.error(f"发送图片失败: {e}")

    def send_notify(self, results):
        if not self.bot_token or not self.chat_id: return
        
        # 1. 发送文字报告 (使用你指定的格式)
        msg = "✈️ <b>ICMP9 签到报告</b>\n"
        msg += "-" * 20 + "\n"
        
        # 注意这里解包了 4 个变量
        for email, success, stats, screenshots in results:
            # 邮箱脱敏
            try:
                name_part = email.split('@')[0]
                if len(name_part) > 3:
                    mask_email = name_part[:3] + "***"
                else:
                    mask_email = name_part + "***"
            except:
                mask_email = email

            # 基础状态
            msg += f"👤 {mask_email}\n"
            msg += f"STATUS: {stats['status']}\n"
            
            # 只有成功或已签到才显示详细数据
            if "成功" in stats['status'] or "已" in stats['status']:
                msg += f"🎁 今日奖励: {stats['today_reward']}\n"
                msg += f"📊 累计获得: {stats['total_traffic']}\n"
                msg += f"🗓 累计签到: {stats['total_days']}\n"
                msg += f"🔥 连续签到: {stats['streak_days']}\n"
            else:
                pass
                
            msg += "-" * 20 + "\n"
        
        # 发送文字消息请求
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage", 
                json={"chat_id": self.chat_id, "text": msg, "parse_mode": "HTML"}
            )
            logger.info("Telegram 文字通知已发送")
        except Exception as e:
            logger.error(f"发送文字通知失败: {e}")

        # 2. 发送截图 (遍历 results 中的 screenshots)
        logger.info("开始发送截图...")
        for email, success, stats, screenshots in results:
            if screenshots:
                for shot_path in screenshots:
                    # 提取文件名里的描述，例如 "签到状态截图"
                    try:
                        desc = shot_path.split('_', 1)[1].replace('.png', '')
                        # Caption: "lyc*** 签到状态截图"
                        caption = f"{email.split('@')[0][:3]}*** {desc}"
                    except:
                        caption = "Checkin Screenshot"
                    
                    self.send_photo(shot_path, caption)

    def run_all(self):
        results = []
        for acc in self.accounts:
            task = ICMP9Checkin(acc['email'], acc['password'])
            # run() 返回 3 个值，加上 email 组成 tuple
            success, stats, screenshots = task.run()
            results.append((acc['email'], success, stats, screenshots))
        self.send_notify(results)

if __name__ == "__main__":
    MultiAccountManager().run_all()
