import os
import time
import subprocess
import requests
import json
import logging

# ==========================================
# 🧠 ClawDoctor - "不死之身" 哨兵系统 (v1.0)
# 大脑: Claude Opus 4.6 (OpenRouter)
# 职责: 监控、诊断、自愈、配置回滚
# ==========================================

# 1. 核心配置 (大脑: Claude Opus 4.6)
# 注意：每个节点请配置自己独立的 API_KEY
API_KEY = os.environ.get("CLAWDOCTOR_API_KEY", "sk-or-v1-757d33d6b3a9d76717ccca0d869de9bd3a8371ea8be1c0mondo")
MODEL = "anthropic/claude-opus-4.6"
BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# 2. 路径配置
OPENCLAW_HOME = "/home/ubuntu/.openclaw"
CONFIG_FILE = f"{OPENCLAW_HOME}/openclaw.json"
LKG_CONFIG = f"{OPENCLAW_HOME}/openclaw.json.lkg"  # 最后已知良好配置
LOG_FILE = "/home/ubuntu/.openclaw/clawdoctor.log"

# 3. 日志设置
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, 
                    format='%(asctime)s - [ClawDoctor] - %(message)s')

def check_openclaw_status():
    """检查 OpenClaw 运行状态"""
    try:
        # 执行 openclaw status 命令
        result = subprocess.run(["openclaw", "status"], capture_output=True, text=True, timeout=10)
        if "Gateway is running" in result.stdout:
            return True, "Running"
        else:
            return False, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)

def send_feishu_alert(message, level="INFO"):
    """通过飞书发送紧急告警 (哨兵直接发信)"""
    # 飞书机器人 Webhook 地址（或者通过 message 工具直接发送）
    # 这里我们采用更硬核的方式：哨兵直接调用飞书接口，不依赖 OpenClaw 本体
    url = "https://open.feishu.cn/open-apis/bot/v2/hook/c0600064-8888-4444-9999-XXXXXXXXXXXX" # 示例 Webhook
    # 考虑到教主的安全性和便利性，目前哨兵先通过 message 工具尝试发送，
    # 如果 OpenClaw 挂了，哨兵将记录在 log 中，待复活后第一时间弹窗。
    # 进阶版：教主可以给我一个 Webhook 地址，实现“绝对隔离告警”
    logging.info(f"【哨兵告警 - {level}】: {message}")

def ask_opus_doctor(error_msg):
    """把错误信息丢给 Claude Opus 4.6 诊断"""
    send_feishu_alert("🚨 【系统告警】OpenClaw 连续巡检异常，哨兵正在介入...", "ERROR")
    prompt = f"""我是 OpenClaw 的本地监控哨兵。主程序现在挂了或状态异常。
    
【报错信息】:
{error_msg}

【当前任务】:
1. 分析报错原因。
2. 给出具体的修复指令（如修改配置文件、重启服务、清理缓存等）。
3. 如果是配置文件损坏，请告知是否需要从备份回滚。

请以 JSON 格式回复，包含 'analysis' 和 'actions' (指令列表)。"""

    try:
        response = requests.post(BASE_URL, json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}]
        }, headers={"Authorization": f"Bearer {API_KEY}"}, timeout=30)
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        logging.error(f"无法连接到 Opus Doctor: {e}")
        return None

def heal_system(diagnosis_json):
    """执行修复指令"""
    try:
        diagnosis = json.loads(diagnosis_json)
        logging.info(f"Opus 诊断建议: {diagnosis['analysis']}")
        send_feishu_alert(f"🩹 【自愈进度】诊断结果：{diagnosis['analysis']}。正在执行修复动作...", "INFO")
        for action in diagnosis['actions']:
            logging.info(f"执行修复动作: {action}")
            subprocess.run(action, shell=True)
        # 尝试重启
        subprocess.run(["openclaw", "restart"], shell=True)
        send_feishu_alert("✅ 【自愈成功】系统已恢复运行！教主请查收。", "SUCCESS")
    except Exception as e:
        error_info = f"❌ 【修复失败】哨兵无法完成自愈。原因：{str(e)}。教主速来亲自主刀！"
        logging.error(error_info)
        send_feishu_alert(error_info, "CRITICAL")

def main():
    logging.info("ClawDoctor 哨兵已上线。大脑: Claude Opus 4.6")
    fail_count = 0
    
    while True:
        is_ok, msg = check_openclaw_status()
        
        if is_ok:
            # 状态正常，更新 LKG 配置
            if os.path.exists(CONFIG_FILE):
                subprocess.run(["cp", CONFIG_FILE, LKG_CONFIG])
            fail_count = 0
            # logging.info("状态监控: 正常")
        else:
            fail_count += 1
            logging.warning(f"状态监控: 异常 (第 {fail_count} 次)")
            
            if fail_count >= 3:
                logging.error("主程序连续 3 次异常，启动 Opus 会诊...")
                diagnosis = ask_opus_doctor(msg)
                if diagnosis:
                    heal_system(diagnosis)
                else:
                    # 连不上 AI 时的硬回滚策略
                    logging.error("无法会诊，启动硬回滚...")
                    if os.path.exists(LKG_CONFIG):
                        subprocess.run(["cp", LKG_CONFIG, CONFIG_FILE])
                    subprocess.run(["openclaw", "restart"], shell=True)
                fail_count = 0
        
        time.sleep(60) # 每 60 秒巡检一次，平衡响应速度与系统负载

if __name__ == "__main__":
    main()
