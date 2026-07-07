#!/usr/bin/env python3
"""Local Lubuntu launcher for Vangrapf VK Tunnel Proxy."""
from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
PYTHON = VENV / "bin" / "python"
PIP = VENV / "bin" / "pip"
NODE_BIN = ROOT / "node_modules" / ".bin" / "vk-tunnel"
DEFAULT_PORT = int(os.environ.get("PORT", "5000"))
SERVICE_NAME = "vangrapf-proxy-vk-tunnel.service"
PROJECT_NAME = "Vangrapf VK Tunnel Proxy"
URL_RE = re.compile(r"https?://[^\s'\"]+")


def run(cmd: list[str], *, cwd: Path = ROOT, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    print("$", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, env=env)


def _tkinter_available() -> bool:
    try:
        import tkinter  # noqa: F401
    except Exception:
        return False
    return True


def _venv_available() -> bool:
    try:
        import venv
    except Exception:
        return False
    return hasattr(venv, "EnvBuilder")


def ensure_system_packages() -> None:
    missing_bins = [name for name in ("python3", "curl", "node", "npm") if shutil.which(name) is None]
    needs_tk = not _tkinter_available()
    needs_venv = not _venv_available()
    if missing_bins or needs_tk or needs_venv:
        if shutil.which("apt-get") is None:
            raise RuntimeError("apt-get не найден. Установите python3 python3-venv python3-tk curl nodejs npm вручную.")
        run(["sudo", "apt-get", "update"])
        run(["sudo", "apt-get", "install", "-y", "python3", "python3-venv", "python3-tk", "curl", "nodejs", "npm"])


def ensure_python_env() -> None:
    if not PYTHON.exists():
        run(["python3", "-m", "venv", str(VENV)])
    run([str(PYTHON), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
    run([str(PIP), "install", "--upgrade", "-r", str(ROOT / "requirements.txt")])


def ensure_vk_tunnel() -> None:
    run(["npm", "install"])


def install_all() -> None:
    ensure_system_packages()
    ensure_python_env()
    ensure_vk_tunnel()


def service_text() -> str:
    return f"""[Unit]
Description=Vangrapf VK Tunnel Proxy
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory={ROOT}
ExecStart={PYTHON} {ROOT / 'scripts' / 'vangrapf_local.py'} --no-gui
Restart=always
RestartSec=5
Environment=PORT={DEFAULT_PORT}

[Install]
WantedBy=default.target
"""


def enable_autostart() -> None:
    user_dir = Path.home() / ".config" / "systemd" / "user"
    user_dir.mkdir(parents=True, exist_ok=True)
    service = user_dir / SERVICE_NAME
    service.write_text(service_text())
    run(["systemctl", "--user", "daemon-reload"])
    run(["systemctl", "--user", "enable", "--now", SERVICE_NAME])
    # keep user service alive after graphical logout when supported
    run(["loginctl", "enable-linger", os.environ.get("USER", "")], check=False)


class ProcessGroup:
    def __init__(self, on_line):
        self.on_line = on_line
        self.children: list[subprocess.Popen] = []
        self.public_url = ""

    def start(self, port: int, skip_install: bool = False) -> None:
        if any(proc.poll() is None for proc in self.children):
            self.on_line("[info] Proxy/VK Tunnel уже запущены.")
            return
        if not skip_install:
            install_all()
        env = os.environ.copy()
        env["PORT"] = str(port)
        proxy = subprocess.Popen([str(PYTHON), str(ROOT / "main.py")], cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, preexec_fn=os.setsid)
        self.children.append(proxy)
        threading.Thread(target=self._reader, args=(proxy, "proxy"), daemon=True).start()
        self._wait_health(port)
        tunnel_cmd = [str(NODE_BIN)] if NODE_BIN.exists() else ["npx", "--yes", "@vkontakte/vk-tunnel"]
        tunnel_cmd += ["--insecure=1", "--http-protocol=http", "--ws-protocol=ws", "--host=127.0.0.1", f"--port={port}"]
        tunnel = subprocess.Popen(tunnel_cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=sys.stdin, preexec_fn=os.setsid)
        self.children.append(tunnel)
        threading.Thread(target=self._reader, args=(tunnel, "vk-tunnel"), daemon=True).start()

    def _wait_health(self, port: int) -> None:
        for _ in range(60):
            try:
                urlopen(f"http://127.0.0.1:{port}/health", timeout=1).read()
                self.on_line(f"[ok] Локальный proxy: http://127.0.0.1:{port}")
                return
            except Exception:
                time.sleep(0.5)
        self.on_line("[warn] Proxy не ответил на /health за 30 секунд, tunnel всё равно запускается.")

    def _reader(self, proc: subprocess.Popen, name: str) -> None:
        assert proc.stdout
        for line in proc.stdout:
            self.on_line(f"[{name}] {line.rstrip()}")
            for url in URL_RE.findall(line):
                if "vk" in url or "tunnel" in url:
                    self.public_url = url.rstrip("/.,)")
                    self.on_line(f"[PUBLIC_URL] {self.public_url}")

    def stop(self) -> None:
        for proc in self.children:
            if proc.poll() is None:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)


def cli(args) -> int:
    group = ProcessGroup(print)
    try:
        group.start(args.port, args.skip_install)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        group.stop()
        return 0


def gui(args) -> int:
    import tkinter as tk
    from tkinter import messagebox, scrolledtext

    root = tk.Tk()
    root.title(PROJECT_NAME)
    log = scrolledtext.ScrolledText(root, width=105, height=32)
    log.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
    status = tk.StringVar(value="Нажмите старт. Логин VK Tunnel выполняется вручную в открывшемся окне/терминале.")
    tk.Label(root, textvariable=status).pack(fill=tk.X, padx=8)
    group = ProcessGroup(lambda line: root.after(0, append, line))

    def append(line: str) -> None:
        log.insert(tk.END, line + "\n")
        log.see(tk.END)
        if line.startswith("[PUBLIC_URL]"):
            public_url = line.split(" ", 1)[1]
            status.set("Ссылка proxy: " + public_url)
            root.clipboard_clear()
            root.clipboard_append(public_url)

    def start() -> None:
        start_btn.config(state=tk.DISABLED)

        def worker() -> None:
            try:
                group.start(args.port, args.skip_install)
            except Exception as exc:
                root.after(0, append, f"[error] {exc}")
                root.after(0, lambda: start_btn.config(state=tk.NORMAL))

        threading.Thread(target=worker, daemon=True).start()

    def autostart() -> None:
        try:
            install_all()
            enable_autostart()
            messagebox.showinfo("Автозапуск", "Автозапуск включён через systemd --user.")
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))

    buttons = tk.Frame(root)
    buttons.pack(pady=8)
    start_btn = tk.Button(buttons, text="Старт / обновить и запустить", command=start)
    start_btn.pack(side=tk.LEFT, padx=4)
    tk.Button(buttons, text="Добавить в автозапуск", command=autostart).pack(side=tk.LEFT, padx=4)
    tk.Button(buttons, text="Выход", command=lambda: (group.stop(), root.destroy())).pack(side=tk.LEFT, padx=4)
    root.protocol("WM_DELETE_WINDOW", lambda: (group.stop(), root.destroy()))
    root.mainloop()
    return 0


def parse_args():
    parser = argparse.ArgumentParser(description="Vangrapf local Lubuntu launcher")
    parser.add_argument("--no-gui", action="store_true", help="запуск без GUI")
    parser.add_argument("--skip-install", action="store_true", help="не обновлять зависимости перед стартом")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--install-only", action="store_true")
    parser.add_argument("--enable-autostart", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    ns = parse_args()
    if ns.install_only:
        install_all()
        sys.exit(0)
    if ns.enable_autostart:
        install_all()
        enable_autostart()
        sys.exit(0)
    if not ns.no_gui and not ns.skip_install:
        ensure_system_packages()
    sys.exit(cli(ns) if ns.no_gui else gui(ns))
