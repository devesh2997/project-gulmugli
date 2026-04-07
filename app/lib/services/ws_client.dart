import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:web_socket_channel/web_socket_channel.dart';

import '../config/constants.dart';

/// WebSocket client with auto-reconnect for real-time state updates.
///
/// Connects to the JARVIS API WebSocket at ws://host:port/ws?token=<token>.
/// Receives state broadcasts from FaceUI and emits them as a stream.
/// Handles disconnection with exponential backoff reconnection.
class WsClient {
  final String host;
  final int port;
  final String token;

  WebSocketChannel? _channel;
  final _controller = StreamController<Map<String, dynamic>>.broadcast();
  Timer? _reconnectTimer;
  Duration _reconnectDelay = kWsReconnectInitial;
  bool _disposed = false;
  bool _connected = false;

  /// Stream of parsed JSON messages from the server.
  Stream<Map<String, dynamic>> get messages => _controller.stream;

  /// Whether the WebSocket is currently connected.
  bool get isConnected => _connected;

  WsClient({required this.host, required this.port, required this.token});

  /// Connect to the WebSocket server.
  void connect() {
    if (_disposed) return;
    _doConnect();
  }

  /// Send a JSON message (action) to the server.
  void send(Map<String, dynamic> message) {
    if (_channel != null && _connected) {
      _channel!.sink.add(jsonEncode(message));
    }
  }

  /// Send a UI action (same format as dashboard).
  void sendAction(String action, {Map<String, dynamic>? params}) {
    send({
      'action': action,
      if (params != null) 'params': params,
    });
  }

  /// Disconnect and clean up.
  void dispose() {
    _disposed = true;
    _reconnectTimer?.cancel();
    _channel?.sink.close();
    _controller.close();
  }

  void _doConnect() {
    if (_disposed) return;

    final uri = Uri.parse('ws://$host:$port/ws?token=$token');
    try {
      _channel = WebSocketChannel.connect(uri);

      _channel!.stream.listen(
        (data) {
          if (!_connected) {
            _connected = true;
            _reconnectDelay = kWsReconnectInitial; // Reset on success
            // Emit a synthetic connection event
            _controller.add({'type': '_connected'});
          }

          try {
            final json = jsonDecode(data as String) as Map<String, dynamic>;
            _controller.add(json);
          } catch (_) {
            // Ignore malformed messages
          }
        },
        onError: (error) {
          _connected = false;
          _controller.add({'type': '_disconnected', 'error': error.toString()});
          _scheduleReconnect();
        },
        onDone: () {
          _connected = false;
          _controller.add({'type': '_disconnected'});
          _scheduleReconnect();
        },
        cancelOnError: false,
      );
    } catch (e) {
      _connected = false;
      _controller.add({'type': '_disconnected', 'error': e.toString()});
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    if (_disposed) return;
    _reconnectTimer?.cancel();

    _reconnectTimer = Timer(_reconnectDelay, () {
      _doConnect();
    });

    // Exponential backoff with jitter
    final nextDelay = _reconnectDelay * kWsReconnectMultiplier;
    final jitter = Duration(
      milliseconds: Random().nextInt(1000),
    );
    _reconnectDelay = Duration(
      milliseconds: min(
        nextDelay.inMilliseconds + jitter.inMilliseconds,
        kWsReconnectMax.inMilliseconds,
      ),
    );
  }
}
