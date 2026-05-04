"""
Brand identity — single source of truth for the assistant's name and the
network identifiers that derive from it.

## Why this module exists

Until v1, the literal string "Jarvis" / "JARVIS" was hard-coded in 30+
files: API titles, log messages, mDNS service types, dashboard <title>,
help text, environment variable names. Renaming the assistant required a
codebase-wide grep-and-replace, with high risk of missing a place.

This module centralizes everything brand-related into one Python class
backed by config.yaml. Future renames (Vesper → Tau → whatever) cost two
config edits and a wake-word retrain — no code changes.

## Two distinct identifiers

- **`name`** — user-facing brand. Shown in API titles, log labels,
  dashboard, voice prompts. Changes when the product rebrands.
- **`protocol_id`** — stable opaque identifier used in mDNS service
  type, internal handles, anything that clients on the network already
  know how to find. **Never user-visible.** This is decoupled from the
  brand on purpose: the Flutter companion app discovers
  `_<protocol_id>._tcp.local.` and that lookup must keep working
  across rebrands. Apple's Bonjour does this too — your AirPlay device's
  name changes, but `_airplay._tcp` doesn't.

## Usage

    from core.branding import brand

    log.info("Starting %s...", brand.name)
    title = f"{brand.name} Companion API"
    service_type = brand.mdns_service_type   # "_gulmugli._tcp.local."

The singleton `brand` reads config lazily through properties — no
caching at import time, so unit tests that monkey-patch the config dict
see fresh values without needing to reload this module.
"""

from __future__ import annotations

from core.config import config


class Brand:
    """
    Resolved brand identity from config. All values are read live from
    the config dict on each access — no module-level caching — so tests
    that mutate config see updated values immediately.
    """

    @property
    def name(self) -> str:
        """
        Display name as the user reads it: "Vesper", "Jarvis", etc.

        Used for API titles, dashboard chrome, log labels, voice prompts.
        Falls back to "Assistant" if config is missing — generic enough
        that startup never crashes on a half-configured deployment.
        """
        return config.get("assistant", {}).get("name", "Assistant")

    @property
    def name_upper(self) -> str:
        """
        All-caps form, e.g. "VESPER". Used in log lines that visually
        delineate the assistant's voice from other components, and in
        Nagios-style health-check summaries.
        """
        return self.name.upper()

    @property
    def name_lower(self) -> str:
        """
        Lowercase form, e.g. "vesper". Used in log file names, default
        wake phrases, and any other place where the name shows up as an
        identifier rather than display text.
        """
        return self.name.lower()

    @property
    def protocol_id(self) -> str:
        """
        Stable opaque network identifier. NEVER user-visible.

        This is what shows up in mDNS service types and any other place
        a client on the network already knows the lookup string. Rebrand
        the assistant and `name` changes; `protocol_id` stays the same
        so existing client installs keep discovering it.

        Defaults to "gulmugli" — the project codename. Survives any
        future brand rename ("Vesper" → "Tau" → ...) because it's tied
        to the project, not the brand.

        ## If you change this

        It must match exactly in three places (server + iOS Bonjour
        declaration + Flutter constant). Coordinate or discovery breaks
        silently:
          1. `assistant.protocol_id` in config.yaml (server)
          2. `app/ios/Runner/Info.plist → NSBonjourServices` (iOS prompt)
          3. `app/lib/config/constants.dart → kMdnsServiceType` (Flutter)
        Then rebuild the Flutter app and reinstall on every device.
        """
        return config.get("assistant", {}).get("protocol_id", "gulmugli")

    @property
    def mdns_service_type(self) -> str:
        """
        Full mDNS service type. e.g. "_gulmugli._tcp.local."

        Use this when registering with Zeroconf or constructing mDNS
        names. The Flutter companion app's discovery code reads the
        same string — they MUST match exactly.
        """
        return f"_{self.protocol_id}._tcp.local."


# Module-level singleton. Importers do `from core.branding import brand`
# and treat `brand` as a read-only namespace.
brand = Brand()
