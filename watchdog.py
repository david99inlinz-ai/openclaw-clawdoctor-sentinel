import os, sys, time, subprocess, requests, json, fcntl, signal
OPENCLAW_HOME = "/home/ubuntu/.openclaw"
CONFIG_FILE = f"{OPENCLAW_HOME}/openclaw.json"
LKG_CONFIG = f"{OPENCLAW_HOME}/openclaw.json.lkg"
LOG_FILE = f"{OPENCLAW_HOME}/clawdoctor.log"
PID_FILE = f"{OPENCLAW_HOME}/workspace/watchdog.pid"
LOCK_FILE = f"{OPENCLAW_HOME}/clawdoctor.lock"
CHECK_INTERVAL = 60
FAIL_THRESHOLD = 3
GATEWAY_PORT = 18789
SERVICE_NAME = "openclaw-gateway.service"
API_KEY = os.environ.get("CLAWDOCTOR_API_KEY", "sk-or-v1-757d33d6b3a9d76717ccca0d869de9bd3a8371ea8be1c0mondo")
MODEL = "anthropic/claude-opus-4.6"
BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} - [ClawDoctor] - {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def acquire_lock():
    global lock_fp
    lock_fp = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except IOError:
        log("另一个 ClawDoctor 实例正在运行，退出。")
        return False

def write_pid():
    os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))

def cleanup(signum=None, frame=None):
    log("ClawDoctor 哨兵下线。")
    try:
        os.remove(PID_FILE)
        os.remove(LOCK_FILE)
    except:
        pass
    sys.exit(0)

def run_cmd(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, "", str(e)

def check_health():
    code, out, _ = run_cmd(["systemctl", "--user", "is-active", SERVICE_NAME])
    if out.strip() != "active":
        return False, f"service not active: {out.strip()}"
    code, out, _ = run_cmd(["ss", "-tlnp"])
    if f":{GATEWAY_PORT}" not in out:
        return False, f"port {GATEWAY_PORT} not listening"
    kill_orphans()
    return True, "OK"

def kill_orphans():
    try:
        _, pid_out, _ = run_cmd(["systemctl", "--user", "show", SERVICE_NAME, "--property=MainPID"])
        gw_pid = pid_out.strip().split("=")[1] if "=" in pid_out else "0"
        _, pgrep_out, _ = run_cmd(["pgrep", "-f", "openclaw"])
        my_pid = str(os.getpid())
        for pid in pgrep_out.strip().split("\n"):
            pid = pid.strip()
            if not pid or pid == gw_pid or pid == my_pid:
                continue
            try:
                cmdline = open(f"/proc/{pid}/cmdline").read()
                if any(k in cmdline for k in ["gateway", "watchdog", "clawdoctor", "logs"]):
                    continue
                log(f"清理孤儿进程 pid={pid}")
                os.kill(int(pid), 9)
            except:
                pass
    except:
        pass

def run_doctor():
    log("运行 openclaw doctor --fix 尝试自愈配置...")
    run_cmd(["openclaw", "doctor", "--fix"], timeout=60)

def restart_gateway():
    log("通过 systemd 重启 gateway...")
    run_doctor()  # 在重启前先尝试修复配置
    run_cmd(["systemctl", "--user", "stop", SERVICE_NAME], timeout=30)
    time.sleep(3)
    kill_orphans()
    time.sleep(2)
    run_cmd(["systemctl", "--user", "start", SERVICE_NAME], timeout=30)
    time.sleep(5)
    code, out, _ = run_cmd(["systemctl", "--user", "is-active", SERVICE_NAME])
    if out.strip() == "active":
        log("gateway 重启成功")
        return True
    log("gateway 重启失败")
    return False

def ask_opus(error_msg):
    log("启动 Opus 会诊...")
    prompt = f"""OpenClaw Gateway service 异常。
【报错】: {error_msg}
【要求】: 只用 systemctl --user 管理，不要 openclaw restart。
回复 JSON: {{"analysis":"...","actions":["cmd1"],"need_rollback":false}}"""
    try:
        resp = requests.post(BASE_URL, json={"model": MODEL, "messages": [{"role":"user","content":prompt}]}, headers={"Authorization": f"Bearer {API_KEY}"}, timeout=60)
        data = resp.json()
        if 'choices' in data:
            return data['choices'][0]['message']['content']
        log(f"Opus API 错误: {data}")
        return None
    except Exception as e:
        log(f"Opus 连接失败: {e}")
        return None

def heal(diagnosis_raw):
    try:
        s = diagnosis_raw
        if '```json' in s:
            s = s.split('```json')[1].split('```')[0]
        elif '```' in s:
            s = s.split('```')[1].split('```')[0]
        start, end = s.find('{'), s.rfind('}') + 1
        if start >= 0 and end > start:
            s = s[start:end]
        d = json.loads(s)
        log(f"诊断: {d.get('analysis','?')}")
        if d.get('need_rollback') and os.path.exists(LKG_CONFIG):
            log("回滚配置...")
            run_cmd(["cp", LKG_CONFIG, CONFIG_FILE])
            run_cmd(["chmod", "600", CONFIG_FILE])
        bad = ["rm -rf", "dd if=", "mkfs", "> /dev/"]
        for action in d.get('actions', []):
            if any(k in action for k in bad):
                log(f"跳过危险命令: {action}")
                continue
            if "openclaw restart" in action or "openclaw start" in action:
                action = f"systemctl --user restart {SERVICE_NAME}"
            log(f"执行: {action}")
            run_cmd(action.split(), timeout=30)
        restart_gateway()
    except Exception as e:
        log(f"自愈失败: {e}")
        restart_gateway()

def hard_recovery():
    log("硬恢复...")
    if os.path.exists(LKG_CONFIG):
        run_cmd(["cp", LKG_CONFIG, CONFIG_FILE])
        run_cmd(["chmod", "600", CONFIG_FILE])
    restart_gateway()

def main():
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)
    if not acquire_lock():
        sys.exit(1)
    write_pid()
    log("ClawDoctor v2.0 哨兵已上线。大脑: Claude Opus 4.6")
    log(f"监控目标: systemd {SERVICE_NAME} (端口 {GATEWAY_PORT})")
    fail_count = 0
    while True:
        ok, msg = check_health()
        if ok:
            if fail_count > 0:
                log(f"系统恢复正常（此前异常 {fail_count} 次）")
            try:
                run_cmd(["cp", CONFIG_FILE, LKG_CONFIG])
            except:
                pass
            fail_count = 0
            log("巡检正常")
        else:
            fail_count += 1
            log(f"异常 (第 {fail_count} 次): {msg}")
            if fail_count >= FAIL_THRESHOLD:
                log("尝试重启...")
                if restart_gateway():
                    fail_count = 0
                    time.sleep(CHECK_INTERVAL)
                    continue
                try:
                    _, jlog, _ = run_cmd(["journalctl","--user","-u",SERVICE_NAME,"-n","50","--no-pager"])
                    detail = f"{msg}\n\n{jlog}"
                except:
                    detail = msg
                diag = ask_opus(detail)
                if diag:
                    heal(diag)
                else:
                    hard_recovery()
                fail_count = 0
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
