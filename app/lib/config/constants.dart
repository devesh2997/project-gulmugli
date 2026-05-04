/// App-wide constants — default ports, timeouts, etc.
///
/// All magic numbers live here. The actual server address comes from
/// discovery or user input, stored in SharedPreferences.
library;

/// Default API port (matches config.yaml → api.port)
const int kDefaultApiPort = 8766;

/// mDNS service type for auto-discovery.
///
/// MUST match the server's `assistant.protocol_id` config (which builds
/// `_<protocol_id>._tcp.local.` in jarvis/assistant/api/discovery.py),
/// AND the iOS Info.plist NSBonjourServices entry. All three values are
/// the same string in different syntaxes — change one and you must
/// change all three or discovery silently breaks.
///
/// See jarvis/assistant/core/branding.py for the full rationale.
const String kMdnsServiceType = '_gulmugli._tcp';

/// WebSocket reconnect timing
const Duration kWsReconnectInitial = Duration(seconds: 1);
const Duration kWsReconnectMax = Duration(seconds: 30);
const double kWsReconnectMultiplier = 2.0;

/// REST request timeout
const Duration kRestTimeout = Duration(seconds: 15);

/// Long-running request timeout (chat, music play)
const Duration kLongRestTimeout = Duration(seconds: 30);

/// SharedPreferences keys
const String kPrefServerHost = 'server_host';
const String kPrefServerPort = 'server_port';
const String kPrefApiToken = 'api_token';
