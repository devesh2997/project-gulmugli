import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/theme.dart';
import '../services/connection_manager.dart';
import '../state/providers.dart';

/// Minimal connection status indicator — a thin accent bar.
class ConnectionBanner extends ConsumerWidget {
  const ConnectionBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final statusAsync = ref.watch(connectionStatusProvider);

    return statusAsync.when(
      data: (status) {
        if (status == ConnectionStatus.connected) {
          return const SizedBox.shrink();
        }
        final reconnecting = status == ConnectionStatus.connecting;
        return Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
          color: reconnecting
              ? JarvisColors.warning.withValues(alpha: 0.15)
              : JarvisColors.error.withValues(alpha: 0.15),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (reconnecting)
                SizedBox(
                  width: 10, height: 10,
                  child: CircularProgressIndicator(
                    strokeWidth: 1.5,
                    color: JarvisColors.warning.withValues(alpha: 0.7),
                  ),
                ),
              if (reconnecting) const SizedBox(width: 8),
              Text(
                reconnecting ? 'reconnecting' : 'disconnected',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w500,
                  letterSpacing: 0.1,
                  color: reconnecting
                      ? JarvisColors.warning.withValues(alpha: 0.7)
                      : JarvisColors.error.withValues(alpha: 0.7),
                ),
              ),
            ],
          ),
        );
      },
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
    );
  }
}
