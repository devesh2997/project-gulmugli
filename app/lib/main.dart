import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'state/providers.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();

  final container = ProviderContainer();

  // Kick off auto-reconnect WITHOUT awaiting. The previous version
  // awaited tryReconnect() which, on a slow or absent network, made
  // the user stare at the iOS launch image / Android splash for up to
  // 15 seconds (the Dio connectTimeout). The connect screen renders
  // immediately now; if reconnection succeeds, the GoRouter redirect
  // moves the user to /home automatically thanks to the connection
  // status notifier.
  //
  // Failure modes covered:
  //   - No saved creds → tryReconnect returns false fast → stays on /connect
  //   - Saved creds but server unreachable → connect timeouts in background,
  //     status flips to disconnected → user can edit IP and retry
  //   - Saved creds, server up → reconnect completes, redirect to /home
  final manager = container.read(connectionManagerProvider);
  // ignore: discarded_futures
  manager.tryReconnect();

  runApp(
    UncontrolledProviderScope(
      container: container,
      child: const JarvisApp(),
    ),
  );
}
