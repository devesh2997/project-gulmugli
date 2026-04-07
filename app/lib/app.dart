import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'config/theme.dart';
import 'screens/connect_screen.dart';
import 'screens/home_screen.dart';
import 'screens/lights_screen.dart';
import 'screens/music_screen.dart';
import 'screens/quiz_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/weather_screen.dart';
import 'services/connection_manager.dart';
import 'state/providers.dart';

/// Root app widget — handles routing based on connection state.
///
/// The GoRouter is created once and uses [refreshListenable] to react
/// to connection-status changes. This avoids recreating the router on
/// every build, which would lose navigation state and history.
class JarvisApp extends ConsumerStatefulWidget {
  const JarvisApp({super.key});

  @override
  ConsumerState<JarvisApp> createState() => _JarvisAppState();
}

class _JarvisAppState extends ConsumerState<JarvisApp> {
  /// Notifier that the router listens to — fires whenever connection
  /// status changes so redirect logic re-evaluates.
  final _refreshNotifier = _ConnectionRefreshNotifier();

  late final GoRouter _router = GoRouter(
    initialLocation: '/connect',
    refreshListenable: _refreshNotifier,
    routes: [
      GoRoute(
        path: '/connect',
        builder: (context, state) => const ConnectScreen(),
      ),
      GoRoute(
        path: '/home',
        builder: (context, state) => const HomeScreen(),
      ),
      GoRoute(
        path: '/music',
        builder: (context, state) => const MusicScreen(),
      ),
      GoRoute(
        path: '/lights',
        builder: (context, state) => const LightsScreen(),
      ),
      GoRoute(
        path: '/quiz',
        builder: (context, state) => const QuizScreen(),
      ),
      GoRoute(
        path: '/weather',
        builder: (context, state) => const WeatherScreen(),
      ),
      GoRoute(
        path: '/settings',
        builder: (context, state) => const SettingsScreen(),
      ),
    ],
    redirect: (context, state) {
      final connected = _refreshNotifier.connected;
      final loc = state.matchedLocation;
      if (connected && loc == '/connect') return '/home';
      if (!connected && loc != '/connect') return '/connect';
      return null;
    },
  );

  @override
  void dispose() {
    _router.dispose();
    _refreshNotifier.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Watch the connection status and push changes into the notifier
    // so the GoRouter re-evaluates its redirect.
    final statusAsync = ref.watch(connectionStatusProvider);
    final connected = statusAsync.whenOrNull(
          data: (s) => s == ConnectionStatus.connected,
        ) ??
        false;
    _refreshNotifier.connected = connected;

    return MaterialApp.router(
      title: 'JARVIS',
      theme: JarvisTheme.dark,
      routerConfig: _router,
      debugShowCheckedModeBanner: false,
    );
  }
}

/// [ChangeNotifier] bridge: GoRouter's [refreshListenable] fires redirect
/// whenever [connected] is updated.
class _ConnectionRefreshNotifier extends ChangeNotifier {
  bool _connected = false;

  bool get connected => _connected;

  set connected(bool value) {
    if (_connected != value) {
      _connected = value;
      notifyListeners();
    }
  }
}
