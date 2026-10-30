#!/usr/bin/env python3
"""Build and flash one WiFi Fall Guard board without editing menuconfig by hand.

Run it from an ESP-IDF terminal (idf.py must be on PATH):

    python flash_node.py tx --port COM3
    python flash_node.py rx 0 --port COM4
    python flash_node.py rx 1 --port COM5 --server-ip 192.168.4.2 --hz 100
    python flash_node.py rx 5 --build-only          # just compile, no board needed

Each board gets its own build folder (build/tx, build/rx0, build/rx1, ...), so
the node id and other settings never leak from one board to the next and a
second flash of the same node is fast.
"""
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def overlay_lines(args):
    """sdkconfig lines that override the project's Kconfig defaults."""
    lines = []
    if args.role == "rx":
        lines.append(f"CONFIG_WFG_NODE_ID={args.node_id}")
        if args.server_ip:
            lines.append(f'CONFIG_WFG_SERVER_IP="{args.server_ip}"')
        if args.hz:
            lines.append(f"CONFIG_WFG_PING_HZ={args.hz}")
        if args.ssid:
            lines.append(f'CONFIG_WFG_WIFI_SSID="{args.ssid}"')
        if args.password is not None:
            lines.append(f'CONFIG_WFG_WIFI_PASSWORD="{args.password}"')
    else:
        if args.ssid:
            lines.append(f'CONFIG_WFG_AP_SSID="{args.ssid}"')
        if args.password is not None:
            lines.append(f'CONFIG_WFG_AP_PASSWORD="{args.password}"')
        if args.channel:
            lines.append(f"CONFIG_WFG_AP_CHANNEL={args.channel}")
    return lines


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("role", choices=["tx", "rx"], help="tx = transmitter (csi_tx), rx = receiver (csi_rx)")
    p.add_argument("node_id", nargs="?", type=int, help="receiver node id 0..255 (rx only)")
    p.add_argument("--port", help="serial port, e.g. COM4 or /dev/ttyACM0 (default: auto-detect)")
    p.add_argument("--server-ip", help="laptop / Raspberry Pi address (rx, default 192.168.4.2)")
    p.add_argument("--hz", type=int, help="CSI sampling rate (rx, default 100)")
    p.add_argument("--ssid", help="WiFi name (default WFG-NET)")
    p.add_argument("--password", help="WiFi password (default wfg12345)")
    p.add_argument("--channel", type=int, help="WiFi channel (tx, default 6)")
    p.add_argument("--build-only", action="store_true", help="compile only, do not flash")
    p.add_argument("--no-monitor", action="store_true", help="do not open the serial monitor after flashing")
    args = p.parse_args(argv)

    if args.role == "rx":
        if args.node_id is None or not 0 <= args.node_id <= 255:
            p.error("rx needs a node id between 0 and 255, e.g.: python flash_node.py rx 3")
        name, project = f"rx{args.node_id}", "csi_rx"
    else:
        if args.node_id is not None:
            p.error("tx takes no node id")
        name, project = "tx", "csi_tx"

    if shutil.which("idf.py") is None and shutil.which("idf.py.exe") is None:
        sys.exit("idf.py not found: open the 'ESP-IDF 5.3 PowerShell/CMD' terminal (or run export.sh) first")

    project_dir = os.path.join(HERE, project)
    build_dir = os.path.join(HERE, "build", name)
    os.makedirs(build_dir, exist_ok=True)
    overlay = os.path.join(build_dir, "node.defaults")
    with open(overlay, "w", encoding="utf-8") as f:
        f.write("\n".join(overlay_lines(args)) + "\n")
    sdkconfig = os.path.join(build_dir, "sdkconfig")
    if os.path.exists(sdkconfig):
        os.remove(sdkconfig)  # defaults are only applied to a fresh sdkconfig

    def fwd(path):
        return path.replace("\\", "/")

    cmd = ["idf.py", "-C", project_dir, "-B", build_dir,
           f"-DIDF_TARGET=esp32s3",
           f"-DSDKCONFIG={fwd(sdkconfig)}",
           f"-DSDKCONFIG_DEFAULTS={fwd(os.path.join(project_dir, 'sdkconfig.defaults'))};{fwd(overlay)}"]
    if args.port:
        cmd += ["-p", args.port]
    cmd.append("build")
    if not args.build_only:
        cmd.append("flash")
        if not args.no_monitor:
            cmd.append("monitor")

    print(">", " ".join(cmd), flush=True)
    rc = subprocess.call(cmd, shell=(os.name == "nt"))
    if rc != 0:
        sys.exit(rc)

    # Check that the overrides really landed in the generated config.
    with open(sdkconfig, encoding="utf-8") as f:
        config = set(line.strip() for line in f)
    missing = [line for line in overlay_lines(args) if line not in config]
    if missing:
        sys.exit("settings not applied: " + ", ".join(missing))
    print(f"OK: {name} ({project}) " + ("built" if args.build_only else "flashed"))


if __name__ == "__main__":
    main()
