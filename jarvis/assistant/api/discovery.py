"""
mDNS/Zeroconf service registration — makes the API discoverable on LAN.

Registers the assistant's API as `_<protocol_id>._tcp.local.` (e.g.
`_gulmugli._tcp.local.`) so the Flutter companion app can find the
server without manual IP entry.

## Why protocol_id, not the brand name

The mDNS service type is what clients on the network LOOK FOR. The
Flutter app already in users' hands has `_gulmugli._tcp` baked into
its discovery code. If we used `brand.name` here, a rebrand would
silently break every existing client install — the app would announce
itself under a new name that nothing knows to look for.

So: brand can change ("Jarvis" → "Vesper" → ...), `protocol_id` stays
"gulmugli". Same trick Apple uses with Bonjour — your AirPlay device's
display name changes, but `_airplay._tcp` doesn't.

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

from core.branding import brand
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
    Register the assistant's API as an mDNS service on the local network.

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

    # Service instance name — what shows up in mDNS browsers. Defaults to
    # the protocol id (so "gulmugli._gulmugli._tcp.local."), but can be
    # overridden if you want a friendlier instance name.
    service_name = discovery_cfg.get("service_name", brand.protocol_id)
    port = api_cfg.get("port", 8766)
    service_type = brand.mdns_service_type  # e.g. "_gulmugli._tcp.local."

    try:
        # Get the machine's LAN IP address
        ip = _get_local_ip()
        if not ip:
            log.warning("Could not determine local IP for mDNS registration.")
            return False

        _service_info = ServiceInfo(
            type_=service_type,
            name=f"{service_name}.{service_type}",
            addresses=[socket.inet_aton(ip)],
            port=port,
            properties={
                # `name` here is the brand — clients can show it in their
                # picker UI ("Found: Vesper") even though they discover via
                # the stable protocol_id.
                "name": brand.name,
                "version": "1.0.0",
                "api": f"http://{ip}:{port}",
            },
            server=f"{service_name}.local.",
        )

        _zeroconf = Zeroconf()
        _zeroconf.register_service(_service_info)

        log.info(
            "mDNS service registered: %s.%s at %s:%d",
            service_name,
            service_type,
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
