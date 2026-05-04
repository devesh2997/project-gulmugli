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
  /// Subscription to the current `_channel.stream`. Tracked so we can cancel
  /// it before opening a new channel on reconnect — without this, a flapping
  /// network leaks one StreamSubscription per reconnect attempt and the
  /// broadcast controller ends up with multiple listeners receiving the
  /// same `_disconnected` events.
  StreamSubscription? _channelSub;
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

  /// Force an immediate reconnect, bypassing any scheduled backoff timer.
  ///
  /// Used by the app-lifecycle observer when the user foregrounds the app
  /// after iOS suspended the socket. The default reconnect timer might be
  /// 30s out; we don't want the user staring at stale state.
  void forceReconnect() {
    if (_disposed) return;
    _reconnectTimer?.cancel();
    _reconnectDelay = kWsReconnectInitial; // start fresh
    // Tear down any old socket so onError/onDone don't double-trigger.
    _channelSub?.cancel();
    _channelSub = null;
    try {
      _channel?.sink.close();
    } catch (_) {/* socket might already be closed */}
    _channel = null;
    _connected = false;
    _doConnect();
  }

  /// Send a JSON message (action) to the server.
  void send(Map<String, dynamic> message) {
    if (_disposed) return;
    if (_channel != null && _connected) {
      try {
        _channel!.sink.add(jsonEncode(message));
      } catch (_) {
        // Sink may have closed between the connected-check and the add.
        // Failing silently here matches the rest of the WS surface; the
        // next message attempt will see _connected=false and skip.
      }
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
    _channelSub?.cancel();
    _channelSub = null;
    try {
      _channel?.sink.close();
    } catch (_) {/* already closed */}
    _channel = null;
    _controller.close();
  }

  void _doConnect() {
    if (_disposed) return;

    // Cancel any prior subscription before opening a new socket. Without
    // this, every reconnect leaks a StreamSubscription tied to the old
    // (closed) channel and the broadcast controller fans `_disconnected`
    // events to N stale listeners.
    _channelSub?.cancel();
    _channelSub = null;

    final uri = Uri.parse('ws://$host:$port/ws?token=$token');
    try {
      _channel = WebSocketChannel.connect(uri);

      _channelSub = _channel!.stream.listen(
        (data) {
          if (!_connected) {
            _connected = true;
            _reconnectDelay = kWsReconnectInitial; // Reset on success
            // Emit a synthetic connection event
            _controller.add({'type': '_connected'});
          }

          if (data is! String) {
            // Server only ever sends text frames (JSON). A binary frame
            // here is either a debugging artifact or a protocol mismatch
            // — log it (when in debug mode) but don't crash. Production
            // dashboards have no devtools open so the print is dead bytes;
            // wrap in assertion for free elision in release.
            assert(() {
              // ignore: avoid_print
              print('WsClient: ignoring non-string frame ${data.runtimeType}');
              return true;
            }());
            return;
          }

          try {
            final json = jsonDecode(data) as Map<String, dynamic>;
            _controller.add(json);
          } catch (e) {
            assert(() {
              // ignore: avoid_print
              print('WsClient: malformed JSON: $e — first 200 chars: '
                  '${data.length > 200 ? "${data.substring(0, 200)}…" : data}');
              return true;
            }());
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
