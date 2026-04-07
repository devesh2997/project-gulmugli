import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'state/providers.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Create the Riverpod container so we can try auto-reconnect before
  // the widget tree builds.
  final container = ProviderContainer();

  // Try to reconnect using saved credentials.
  // If this fails (no saved creds, or server unreachable), the app
  // shows the connect screen instead.
  final manager = container.read(connectionManagerProvider);
  await manager.tryReconnect();

  runApp(
    UncontrolledProviderScope(
      container: container,
      child: const JarvisApp(),
    ),
  );
}
