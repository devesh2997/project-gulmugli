import 'dart:async';

import 'package:nsd/nsd.dart';

import '../config/constants.dart';

/// Discovered JARVIS server on the local network.
class DiscoveredServer {
  final String name;
  final String host;
  final int port;

  const DiscoveredServer({
    required this.name,
    required this.host,
    required this.port,
  });

  @override
  String toString() => '$name ($host:$port)';

  @override
  bool operator ==(Object other) =>
      other is DiscoveredServer &&
      other.name == name &&
      other.host == host &&
      other.port == port;

  @override
  int get hashCode => Object.hash(name, host, port);
}

/// mDNS service discovery — finds JARVIS servers on the LAN.
///
/// Uses the `nsd` package to discover `_jarvis._tcp` services advertised
/// by the JARVIS API server (`api/discovery.py`). The server registers as
/// `jarvis._jarvis._tcp.local.` at port 8766 by default.
///
/// Platform requirements (configured in this repo):
///   - **iOS**: requires `NSBonjourServices` in Info.plist with the entry
///     `_jarvis._tcp`. Without it the OS silently blocks browsing — no
///     error, no log, no devices.
///   - **Android**: requires `CHANGE_WIFI_MULTICAST_STATE` permission so
///     the nsd plugin can hold a multicast lock. Discovery degrades to
///     "no results" without this.
///
/// Failure modes handled gracefully:
///   - The `nsd` package raises if the platform doesn't support mDNS at all
///     (some old Android versions, restrictive corporate WiFi). We catch
///     and log; the user falls back to manual IP entry.
///   - "Service lost" events update the list as servers go offline.
class DiscoveryService {
  final _serversController = StreamController<List<DiscoveredServer>>.broadcast();
  final List<DiscoveredServer> _found = [];
  Discovery? _discovery;
  bool _scanning = false;

  /// Stream of discovered servers (emits on each change).
  Stream<List<DiscoveredServer>> get servers => _serversController.stream;

  /// Whether a scan is currently active.
  bool get isScanning => _scanning;

  /// Currently discovered servers.
  List<DiscoveredServer> get currentServers => List.unmodifiable(_found);

  /// Start scanning for JARVIS servers via mDNS.
  ///
  /// Idempotent: calling startScan twice without an intervening stopScan
  /// is a no-op (the existing scan keeps running).
  Future<void> startScan() async {
    if (_scanning) return;
    _scanning = true;
    _found.clear();
    _serversController.add(List.of(_found));

    try {
      // autoResolve resolves host + port together with the discovery event,
      // so we don't need a separate resolve() call before showing the
      // server in the UI list. ipLookupType.any prefers IPv4 but accepts
      // IPv6 — fine for our use case (Jetson is IPv4 on home routers).
      _discovery = await startDiscovery(
        kMdnsServiceType,
        autoResolve: true,
        ipLookupType: IpLookupType.any,
      );
      _discovery!.addServiceListener(_onService);
    } catch (e) {
      // Common causes: missing NSBonjourServices on iOS, permission denied
      // on Android, network unsupported. The connect screen still works
      // via manual IP entry — discovery is a UX nicety, not a hard
      // requirement. We don't surface this to the user; failure here
      // just means the auto-discovered list stays empty.
      _scanning = false;
      // Log only in debug builds — keep release output clean.
      assert(() {
        // ignore: avoid_print
        print('DiscoveryService: startDiscovery failed: $e');
        return true;
      }());
    }
  }

  void _onService(Service service, ServiceStatus status) {
    final host = service.host;
    final port = service.port;
    if (host == null || port == null) return;

    final server = DiscoveredServer(
      name: service.name ?? 'JARVIS',
      host: host,
      port: port,
    );

    if (status == ServiceStatus.found) {
      // Replace any existing entry with the same name (re-resolve) and
      // append. List equality on DiscoveredServer means duplicate add
      // attempts are quietly deduped.
      _found.removeWhere((s) => s.name == server.name);
      _found.add(server);
    } else if (status == ServiceStatus.lost) {
      _found.removeWhere((s) => s.name == server.name);
    }

    _serversController.add(List.of(_found));
  }

  /// Stop scanning and free OS resources. According to nsd's docs the
  /// underlying multicast lock + socket are non-trivial cost on Android,
  /// so we always call this on dispose.
  Future<void> stopScan() async {
    _scanning = false;
    final d = _discovery;
    _discovery = null;
    if (d == null) return;
    try {
      d.removeServiceListener(_onService);
      await stopDiscovery(d);
    } catch (_) {
      // Best-effort — if the platform never started discovery (because
      // startScan threw), stopDiscovery may also throw.
    }
  }

  void dispose() {
    // ignore: discarded_futures — best-effort cleanup, OK to fire and forget
    stopScan();
    _serversController.close();
  }
}
