/// App-wide constants — default ports, timeouts, etc.
///
/// All magic numbers live here. The actual server address comes from
/// discovery or user input, stored in SharedPreferences.
library;

/// Default API port (matches config.yaml → api.port)
const int kDefaultApiPort = 8766;

/// mDNS service type for auto-discovery
const String kMdnsServiceType = '_jarvis._tcp';

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
