# ClawDoctor 🦾

The autonomous watchdog and self-healing system for OpenClaw agents.

## Description
ClawDoctor keeps your OpenClaw instance alive by monitoring its health and using Claude Opus 4.6 to diagnose and fix errors automatically.

## Requirements
- OpenRouter API Key (Claude Opus 4.6 access)
- Python 3.8+

## Configuration
Set the following environment variable:
`CLAWDOCTOR_API_KEY`: Your OpenRouter API Key.

## Usage
Run the sentinel in the background:
`nohup python3 watchdog.py &`
