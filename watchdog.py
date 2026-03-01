import os
import time
import subprocess
import requests
import json
import logging

# ==========================================
# 🧠 ClawDoctor - "不死之身" 哨兵系统 (v2.1)
# 大脑: Claude Opus 4.6 (OpenRouter)
# 职责: 监控、诊断、自愈、配置回滚
# 新增: 财务探针 + 配置健康探针
# ==========================================

API_KEY = os.environ.get("CLAWDOCTOR_API_KEY", "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")
MODEL = "anthropic/claude-opus-4.6"
BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

OPENCLAW_HOME = "/home/ubuntu/.openclaw"
CONFIG_FILE = f"{OPENCLAW_HOME}/openclaw.json"
LKG_CONFIG = f"{OPENCLAW_HOME}/openclaw.json.lkg"
LOG_FILE = f"{OPENCLAW_HOME}/clawdoctor.log"

# 财务探针：要检查余额的服务商（格式：名称 + 查询URL + 请求头）
CREDIT_PROBES = [
    {
        "name": "OpenRouter",
        "url": "https://openrouter.ai/api/v1/credits",
        "headers": {"Authorization": f"Bearer {API_KEY}"},
        "low_threshold": 1.0  # 低于 $1 预警
    }
]

logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s - [ClawDoctor] - %(message)s')


def send_feishu_alert(message, level="INFO"):
    """通过飞书发送紧急告警"""
    logging.info(f"【哨兵告警 - {level}】: {message}")
    # 通过 openclaw 的 message 工具发送（如果主程序还活着）
    try:
        cmd = f'openclaw message send --channel feishu --to "ou_22bed63232b902401047fb589c17a62f" --message "{message}"'
        subprocess.run(cmd, shell=True, timeout=10)
    except Exception:
        pass  # 主程序挂了就只记日志


def check_openclaw_status():
    """探针1：检查 OpenClaw 进程状态"""
    try:
        result = subprocess.run(
            ["openclaw", "gateway", "status"],
            capture_output=True, text=True, timeout=10
        )
        if "running" in result.stdout.lower():
            return True, "Running"
        return False, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def check_config_health():
    """探针2：检查配置文件健康状态"""
    try:
        result = subprocess.run(
            ["openclaw", "doctor"],
            capture_output=True, text=True, timeout=15
        )
        output = result.stdout + result.stderr
        if "Invalid config" in output or "Unrecognized key" in output:
            return False, output
        return True, "Config OK"
    except Exception as e:
        return False, str(e)


def check_api_credits():
    """探针3：检查 API 余额是否充足"""
    issues = []
    for probe in CREDIT_PROBES:
        try:
            resp = requests.get(
                probe["url"],
                headers=probe["headers"],
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                # OpenRouter 返回格式: {"data": {"total_credits": X, "usage": Y}}
                total = data.get("data", {}).get("total_credits", 0)
                usage = data.get("data", {}).get("usage", 0)
                remaining = total - usage
                if remaining < probe["low_threshold"]:
                    issues.append(f"{probe['name']} 余额不足！剩余 ${remaining:.2f}，请教主尽快充值！")
            elif resp.status_code in (402, 429):
                issues.append(f"{probe['name']} 返回 {resp.status_code}，账户可能已断粮或限流！")
        except Exception as e:
            logging.warning(f"财务探针 {probe['name']} 检查失败: {e}")
    return issues


def ask_opus_doctor(error_msg):
    """把错误信息丢给 Claude Opus 诊断"""
    send_feishu_alert("🚨 【系统告警】OpenClaw 连续巡检异常，哨兵正在介入...", "ERROR")
    prompt = f"""我是 OpenClaw 的本地监控哨兵。主程序现在挂了或状态异常。

【报错信息】:
{error_msg}

请以 JSON 格式回复，包含 'analysis'（分析） 和 'actions'（修复指令列表）。"""
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
        send_feishu_alert(f"🩹 【自愈进度】{diagnosis['analysis']}。正在执行修复...", "INFO")
        for action in diagnosis['actions']:
            logging.info(f"执行: {action}")
            subprocess.run(action, shell=True)
        subprocess.run(["systemctl", "--user", "restart", "openclaw-gateway"], shell=False)
        send_feishu_alert("✅ 【自愈成功】系统已恢复运行！", "SUCCESS")
    except Exception as e:
        msg = f"❌ 【修复失败】{str(e)}。教主速来亲自主刀！"
        logging.error(msg)
        send_feishu_alert(msg, "CRITICAL")


def main():
    logging.info("ClawDoctor v2.1 哨兵已上线。新增：财务探针 + 配置健康探针")
    fail_count = 0
    credit_check_counter = 0  # 每10轮（约10分钟）检查一次余额

    while True:
        # === 探针1：进程状态 ===
        is_ok, msg = check_openclaw_status()
        if is_ok:
            if os.path.exists(CONFIG_FILE):
                subprocess.run(["cp", CONFIG_FILE, LKG_CONFIG])
            fail_count = 0
        else:
            fail_count += 1
            logging.warning(f"状态监控: 异常 (第 {fail_count} 次)")
            if fail_count >= 3:
                logging.error("主程序连续 3 次异常，启动 Opus 会诊...")
                diagnosis = ask_opus_doctor(msg)
                if diagnosis:
                    heal_system(diagnosis)
                else:
                    logging.error("无法会诊，启动硬回滚...")
                    if os.path.exists(LKG_CONFIG):
                        subprocess.run(["cp", LKG_CONFIG, CONFIG_FILE])
                    subprocess.run(["systemctl", "--user", "restart", "openclaw-gateway"], shell=False)
                fail_count = 0

        # === 探针2：配置健康（每5轮检查一次，约5分钟）===
        if credit_check_counter % 5 == 0:
            config_ok, config_msg = check_config_health()
            if not config_ok:
                alert = f"⚠️ 【配置异常】发现 Invalid config 错误，请教主检查！详情：{config_msg[:200]}"
                logging.error(alert)
                send_feishu_alert(alert, "WARN")

        # === 探针3：财务余额（每10轮检查一次，约10分钟）===
        if credit_check_counter % 10 == 0:
            credit_issues = check_api_credits()
            for issue in credit_issues:
                logging.warning(issue)
                send_feishu_alert(f"💸 【断粮预警】{issue}", "WARN")

        credit_check_counter += 1
        time.sleep(60)


if __name__ == "__main__":
    main()
