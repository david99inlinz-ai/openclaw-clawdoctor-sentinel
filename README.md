# ClawDoctor Sentinel 🦾

**The Immortal Guardian for OpenClaw Agents.**

ClawDoctor is an autonomous watchdog system designed to keep your OpenClaw instance alive forever. It monitors process health, diagnoses errors using high-level AI (Claude Opus 4.6), and performs self-healing or configuration rollbacks.

## 🚀 Features
- **Real-time Monitoring**: Checks `openclaw status` every 60 seconds.
- **AI Diagnostics**: Uses Claude Opus 4.6 to analyze error logs and suggest fixes.
- **Self-Healing**: Automatically executes recovery commands.
- **LKG Rollback**: Reverts to the "Last Known Good" configuration if the current one is corrupted.
- **Atomic Reliability**: Designed for the "Change Young" initiative.

## 📦 Installation (Coming soon to ClawHub)
Currently, you can run it as a standalone sentinel:
```bash
export CLAWDOCTOR_API_KEY='your_openrouter_key'
nohup python3 watchdog.py &
```

---

# ClawDoctor 哨兵 🦾

**OpenClaw 数字生命的“不死”守护者。**

ClawDoctor 是一个自主的“看门狗”系统，旨在让你的 OpenClaw 实例永久在线。它监控进程健康，使用高级 AI (Claude Opus 4.6) 诊断错误，并执行自我修复或配置回滚。

## 🚀 核心功能
- **实时监测**：每 60 秒巡检一次系统状态。
- **AI 会诊**：当系统崩溃时，调动 Claude Opus 4.6 分析日志。
- **自主修复**：根据诊断结果自动执行修复指令。
- **黄金备份回滚**：如果配置文件损坏，自动回滚至“最后已知良好状态”。
- **极低占用**：静默运行，几乎不消耗系统资源。

## 🛠️ 安装说明
目前可作为独立哨兵运行：
```bash
export CLAWDOCTOR_API_KEY='你的OpenRouter_Key'
nohup python3 watchdog.py &
```
