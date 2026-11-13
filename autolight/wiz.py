"""UDP client for Philips WiZ smart bulbs (local network control, no cloud/app needed).

WiZ bulbs run a small control server on UDP port 38899 and accept plain JSON
commands. This is the same protocol the official WiZ app uses when it talks
to a bulb on your LAN.
"""
from __future__ import annotations

import json
import socket
import time

WIZ_PORT = 38899
DISCOVERY_TIMEOUT = 2.0


def _broadcast_addrs() -> set[str]:
    """Best-effort guess at this machine's subnet broadcast address(es).

    On Windows with multiple adapters (VPN, Hyper-V, virtual switches, ...),
    a plain 255.255.255.255 send can go out the wrong interface. Targeting
    the actual wifi subnet's broadcast address (e.g. 192.168.1.255) is more
    reliable.
    """
    addrs = {"255.255.255.255"}
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # no packet sent; just picks the outbound-facing local IP
        local_ip = s.getsockname()[0]
        s.close()
        octets = local_ip.split(".")
        if len(octets) == 4:
            addrs.add(".".join(octets[:3]) + ".255")
    except OSError:
        pass
    return addrs


def discover(timeout: float = DISCOVERY_TIMEOUT) -> list[dict]:
    """Broadcast a getPilot request and collect replies from WiZ bulbs on the LAN."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(timeout)

    payload = json.dumps({"method": "getPilot", "params": {}}).encode()
    for addr in _broadcast_addrs():
        sock.sendto(payload, (addr, WIZ_PORT))

    found: dict[str, dict] = {}
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        sock.settimeout(remaining)
        try:
            data, (ip, _) = sock.recvfrom(1024)
        except socket.timeout:
            break
        try:
            reply = json.loads(data.decode())
        except ValueError:
            continue
        if ip not in found:
            found[ip] = reply.get("result", {})
    sock.close()
    return [{"ip": ip, "info": info} for ip, info in found.items()]


class WizBulb:
    """Fire-and-forget UDP controller for a single WiZ bulb, with send-rate limiting.

    WiZ bulbs can drop/lag on commands sent too fast over wifi, so writes are
    capped to `min_interval` seconds apart and deduplicated frame-to-frame.
    """

    def __init__(self, ip: str, port: int = WIZ_PORT, min_interval: float = 1 / 15):
        self.ip = ip
        self.port = port
        self.min_interval = min_interval
        self._last_sent = 0.0
        self._last_payload: dict | None = None
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def get_pilot(self, timeout: float = 1.0) -> dict | None:
        self._sock.settimeout(timeout)
        try:
            self._sock.sendto(json.dumps({"method": "getPilot", "params": {}}).encode(), (self.ip, self.port))
            data, _ = self._sock.recvfrom(1024)
            return json.loads(data.decode()).get("result")
        except (socket.timeout, ValueError, OSError):
            return None
        finally:
            self._sock.settimeout(None)

    def set_state(self, on: bool) -> None:
        self._send({"state": on}, force=True)

    def set_color(self, r: int, g: int, b: int, dimming: int) -> None:
        """Set RGB (0-255 each) and brightness (10-100). Rate-limited & deduplicated."""
        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g)))
        b = max(0, min(255, int(b)))
        dimming = max(10, min(100, int(dimming)))
        # Explicit c/w=0 forces full-color mode; otherwise some firmware blends
        # in a leftover white channel from a previous "white light" state.
        self._send({"state": True, "r": r, "g": g, "b": b, "c": 0, "w": 0, "dimming": dimming})

    def _send(self, params: dict, force: bool = False) -> None:
        now = time.monotonic()
        if not force:
            if now - self._last_sent < self.min_interval:
                return
            if params == self._last_payload:
                return
        payload = json.dumps({"method": "setPilot", "params": params}).encode()
        self._sock.sendto(payload, (self.ip, self.port))
        self._last_sent = now
        self._last_payload = params

    def close(self) -> None:
        self._sock.close()
