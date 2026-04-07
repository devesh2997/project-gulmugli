import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/theme.dart';
import '../models/assistant_state.dart';
import '../state/providers.dart';

/// Compact music bar — matches the dashboard's floating MusicPlayer.
///
/// Frosted glass bar with personality accent tint, showing title/artist
/// and play/pause + skip controls. Tap to open full music screen.
class CompactMusicBar extends ConsumerWidget {
  final NowPlaying nowPlaying;
  final Color accent;
  final VoidCallback? onTap;

  const CompactMusicBar({
    super.key,
    required this.nowPlaying,
    required this.accent,
    this.onTap,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final manager = ref.read(connectionManagerProvider);

    return GestureDetector(
      onTap: onTap,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(14),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
          child: Container(
            height: 56,
            padding: const EdgeInsets.symmetric(horizontal: 14),
            decoration: BoxDecoration(
              color: accent.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: JarvisColors.borderSubtle),
            ),
            child: Row(
              children: [
                // Album art
                Container(
                  width: 36, height: 36,
                  decoration: BoxDecoration(
                    color: accent.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: nowPlaying.artUrl != null
                      ? ClipRRect(
                          borderRadius: BorderRadius.circular(8),
                          child: Image.network(
                            nowPlaying.artUrl!,
                            fit: BoxFit.cover,
                            errorBuilder: (_, __, ___) => Icon(
                              Icons.music_note, size: 18,
                              color: accent.withValues(alpha: 0.5),
                            ),
                          ),
                        )
                      : Icon(
                          Icons.music_note, size: 18,
                          color: accent.withValues(alpha: 0.5),
                        ),
                ),
                const SizedBox(width: 12),

                // Title + artist
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        nowPlaying.title,
                        style: const TextStyle(
                          fontSize: 13, fontWeight: FontWeight.w500,
                          color: JarvisColors.textPrimary,
                        ),
                        maxLines: 1, overflow: TextOverflow.ellipsis,
                      ),
                      Text(
                        nowPlaying.artist,
                        style: const TextStyle(
                          fontSize: 11,
                          color: JarvisColors.textSecondary,
                        ),
                        maxLines: 1, overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),

                // Controls
                _BarButton(
                  icon: nowPlaying.paused ? Icons.play_arrow : Icons.pause,
                  onTap: () => manager.api?.musicControl(
                    nowPlaying.paused ? 'resume' : 'pause',
                  ),
                ),
                _BarButton(
                  icon: Icons.skip_next,
                  onTap: () => manager.api?.musicControl('skip'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _BarButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;

  const _BarButton({required this.icon, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.all(6),
        child: Icon(icon, size: 22, color: JarvisColors.textPrimary),
      ),
    );
  }
}
