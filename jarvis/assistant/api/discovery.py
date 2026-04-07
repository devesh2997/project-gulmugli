"""
mDNS/Zeroconf service registration — makes the API discoverable on LAN.

Registers the JARVIS API as a `_jarvis._tcp.local.` service so the
Flutter companion app can find the server without manual IP entry.

Uses the `zeroconf` library (optional dependency). If not installed,
discovery is silently skipped — consistent with the project's graceful
degradation pattern.

Usage (from main.py):
    from api.discovery import register_service, unregister_service
    register_service(api_config)
    # ... on shutdown:
    unregister_service()
"""

import socket
from typing import Optional

from core.config import config
from core.logger import get_logger

log = get_logger("api.discovery")

# ── Guard import ────────────────────────────────────────────────
try:
    from zeroconf import ServiceInfo, Zeroconf
    HAS_ZEROCONF = True
except ImportError:
    HAS_ZEROCONF = False

_zeroconf: Optional["Zeroconf"] = None
_service_info: Optional["ServiceInfo"] = None


def register_service(api_cfg: Optional[dict] = None) -> bool:
    """
    Register the JARVIS API as an mDNS service on the local network.

    Args:
        api_cfg: The api section from config.yaml. If None, reads from config.

    Returns:
        True if registration succeeded, False otherwise.
    """
    global _zeroconf, _service_info

    if not HAS_ZEROCONF:
        log.info(
            "mDNS discovery disabled — zeroconf not installed. "
            "Install with: pip install zeroconf"
        )
        return False

    if api_cfg is None:
        api_cfg = config.get("api", {})

    discovery_cfg = api_cfg.get("discovery", {})
    if not discovery_cfg.get("enabled", True):
        log.info("mDNS discovery disabled in config.")
        return False

    service_name = discovery_cfg.get("service_name", "jarvis")
    port = api_cfg.get("port", 8766)
    assistant_name = config.get("assistant", {}).get("name", "Jarvis")

    try:
        # Get the machine's LAN IP address
        ip = _get_local_ip()
        if not ip:
            log.warning("Could not determine local IP for mDNS registration.")
            return False

        _service_info = ServiceInfo(
            type_="_jarvis._tcp.local.",
            name=f"{service_name}._jarvis._tcp.local.",
            addresses=[socket.inet_aton(ip)],
            port=port,
            properties={
                "name": assistant_name,
                "version": "1.0.0",
                "api": f"http://{ip}:{port}",
            },
            server=f"{service_name}.local.",
        )

        _zeroconf = Zeroconf()
        _zeroconf.register_service(_service_info)

        log.info(
            "mDNS service registered: %s._jarvis._tcp.local. at %s:%d",
            service_name,
            ip,
            port,
        )
        return True

    except Exception as e:
        log.warning("mDNS registration failed: %s", e)
        return False


def unregister_service() -> None:
    """Unregister the mDNS service and close Zeroconf."""
    global _zeroconf, _service_info

    if _zeroconf and _service_info:
        try:
            _zeroconf.unregister_service(_service_info)
            _zeroconf.close()
            log.info("mDNS service unregistered.")
        except Exception as e:
            log.debug("mDNS unregister error (likely already closed): %s", e)
    _zeroconf = None
    _service_info = None


def _get_local_ip() -> Optional[str]:
    """
    Get the machine's local LAN IP address.

    Uses a UDP socket trick — connects to an external address (doesn't
    actually send data) and reads the local address. Works on all platforms.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        # Doesn't actually connect — just determines the route
        s.connect(("10.254.254.254", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None
