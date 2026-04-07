import 'dart:async';

import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../config/constants.dart';
import 'api_client.dart';
import 'ws_client.dart';

/// Connection state for the UI.
enum ConnectionStatus {
  disconnected,
  connecting,
  connected,
}

/// Orchestrates server discovery, connection, and reconnection.
///
/// Manages the lifecycle of [ApiClient] and [WsClient].
/// Persists connection info (host, port) in SharedPreferences.
///
/// Auth is currently disabled during development — only the host
/// and port are needed to connect. Token is optional.
class ConnectionManager {
  ApiClient? _apiClient;
  WsClient? _wsClient;

  String? _host;
  int _port = kDefaultApiPort;

  final _statusController = StreamController<ConnectionStatus>.broadcast();

  /// Stream of connection status changes.
  Stream<ConnectionStatus> get statusStream => _statusController.stream;

  /// Current connection status.
  ConnectionStatus _status = ConnectionStatus.disconnected;
  ConnectionStatus get status => _status;

  /// The API client (null if not connected).
  ApiClient? get api => _apiClient;

  /// The WebSocket client (null if not connected).
  WsClient? get ws => _wsClient;

  /// Server info.
  String? get host => _host;
  int get port => _port;

  /// Try to connect using saved server address.
  Future<bool> tryReconnect() async {
    final prefs = await SharedPreferences.getInstance();
    final host = prefs.getString(kPrefServerHost);
    final port = prefs.getInt(kPrefServerPort) ?? kDefaultApiPort;

    if (host == null) return false;

    return connect(host: host, port: port);
  }

  /// Connect to a JARVIS server.
  ///
  /// Token is optional — auth is disabled during development.
  /// Only the health check needs to pass for a successful connection.
  Future<bool> connect({
    required String host,
    required int port,
    String? token,
  }) async {
    _setStatus(ConnectionStatus.connecting);

    final baseUrl = 'http://$host:$port';
    final client = ApiClient(baseUrl: baseUrl, token: token);

    try {
      // Health check — confirms server is reachable
      await client.healthCheck();

      // Success — store connection
      _host = host;
      _port = port;
      _apiClient = client;

      // Persist for next launch
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(kPrefServerHost, host);
      await prefs.setInt(kPrefServerPort, port);
      if (token != null) await prefs.setString(kPrefApiToken, token);

      // Start WebSocket (no token needed in dev mode)
      _wsClient?.dispose();
      _wsClient = WsClient(host: host, port: port, token: token ?? '');
      _wsClient!.connect();

      // Listen for WS disconnect to update status
      _wsClient!.messages.listen((msg) {
        if (msg['type'] == '_connected') {
          _setStatus(ConnectionStatus.connected);
        } else if (msg['type'] == '_disconnected') {
          _setStatus(ConnectionStatus.connecting); // auto-reconnecting
        }
      });

      _setStatus(ConnectionStatus.connected);
      return true;
    } on DioException {
      _setStatus(ConnectionStatus.disconnected);
      return false;
    } catch (_) {
      _setStatus(ConnectionStatus.disconnected);
      return false;
    }
  }

  /// Disconnect from the server.
  void disconnect() {
    _wsClient?.dispose();
    _wsClient = null;
    _apiClient = null;
    _setStatus(ConnectionStatus.disconnected);
  }

  /// Clear saved connection info.
  Future<void> forget() async {
    disconnect();
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(kPrefServerHost);
    await prefs.remove(kPrefServerPort);
    await prefs.remove(kPrefApiToken);
  }

  void dispose() {
    _wsClient?.dispose();
    _statusController.close();
  }

  void _setStatus(ConnectionStatus s) {
    if (_status != s) {
      _status = s;
      _statusController.add(s);
    }
  }
}
