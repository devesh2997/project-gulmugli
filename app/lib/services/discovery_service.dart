import 'dart:async';

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
}

/// mDNS service discovery — finds JARVIS servers on the LAN.
///
/// Uses the `nsd` package to discover `_jarvis._tcp` services.
/// Falls back gracefully if mDNS is unavailable (e.g., on some Android
/// versions or restrictive networks).
///
/// Usage:
///   final discovery = DiscoveryService();
///   discovery.servers.listen((servers) => print(servers));
///   await discovery.startScan();
///   // ... later
///   await discovery.stopScan();
class DiscoveryService {
  final _serversController = StreamController<List<DiscoveredServer>>.broadcast();
  final List<DiscoveredServer> _found = [];
  bool _scanning = false;

  /// Stream of discovered servers (emits on each change).
  Stream<List<DiscoveredServer>> get servers => _serversController.stream;

  /// Whether a scan is currently active.
  bool get isScanning => _scanning;

  /// Currently discovered servers.
  List<DiscoveredServer> get currentServers => List.unmodifiable(_found);

  /// Start scanning for JARVIS servers via mDNS.
  ///
  /// The actual nsd integration will be wired up when the app runs on
  /// a device. For now this provides the interface and a manual-entry fallback.
  Future<void> startScan() async {
    _scanning = true;
    _found.clear();

    // TODO: Wire up nsd package for actual mDNS discovery:
    //
    // final discovery = NsdDiscovery.forType(kMdnsServiceType);
    // discovery.addServiceListener((service) {
    //   _found.add(DiscoveredServer(
    //     name: service.name,
    //     host: service.host,
    //     port: service.port,
    //   ));
    //   _serversController.add(List.of(_found));
    // });
    // await discovery.start();

    // For now, emit empty list (user will enter IP manually)
    _serversController.add(List.of(_found));
  }

  /// Stop scanning.
  Future<void> stopScan() async {
    _scanning = false;
  }

  void dispose() {
    stopScan();
    _serversController.close();
  }
}
