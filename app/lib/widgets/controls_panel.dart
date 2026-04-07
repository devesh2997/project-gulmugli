import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../config/theme.dart';
import '../state/providers.dart';

/// Controls panel — slides in from right, quick access to features.
///
/// Grid of control tiles: Music, Lights, Quiz, Weather, Timer, etc.
/// Each tile navigates to its full screen or triggers an action.
class ControlsPanel extends ConsumerWidget {
  final Color accent;
  const ControlsPanel({super.key, required this.accent});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final lights = ref.watch(lightsProvider);
    final sleepMode = ref.watch(sleepModeProvider);
    final manager = ref.read(connectionManagerProvider);
    final api = manager.api;

    return SafeArea(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 12),
            child: Text(
              'CONTROLS',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                letterSpacing: 0.12,
                color: accent.withValues(alpha: 0.7),
              ),
            ),
          ),

          Expanded(
            child: GridView.count(
              crossAxisCount: 2,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              mainAxisSpacing: 10,
              crossAxisSpacing: 10,
              childAspectRatio: 1.4,
              children: [
                _ControlTile(
                  icon: Icons.music_note,
                  label: 'Music',
                  accent: accent,
                  onTap: () => context.push('/music'),
                ),
                _ControlTile(
                  icon: Icons.lightbulb_outline,
                  label: 'Lights',
                  accent: accent,
                  active: lights?.on ?? false,
                  onTap: () => context.push('/lights'),
                  onLongPress: () =>
                      api?.lightControl(lights?.on == true ? 'off' : 'on'),
                ),
                _ControlTile(
                  icon: Icons.quiz,
                  label: 'Quiz',
                  accent: accent,
                  onTap: () => context.push('/quiz'),
                ),
                _ControlTile(
                  icon: Icons.cloud_outlined,
                  label: 'Weather',
                  accent: accent,
                  onTap: () => context.push('/weather'),
                ),
                _ControlTile(
                  icon: Icons.nightlight,
                  label: sleepMode ? 'Wake Up' : 'Sleep',
                  accent: accent,
                  active: sleepMode,
                  onTap: () {
                    final action = sleepMode ? 'wake' : 'sleep';
                    manager.ws?.sendAction('text_input', params: {'text': action});
                  },
                ),
                _ControlTile(
                  icon: Icons.settings,
                  label: 'Settings',
                  accent: accent,
                  onTap: () => context.push('/settings'),
                ),
                _ControlTile(
                  icon: Icons.spa_outlined,
                  label: 'Ambient',
                  accent: accent,
                  onTap: () {
                    // Quick ambient toggle
                    api?.ambient('start', sound: 'rain');
                  },
                  onLongPress: () => api?.ambient('stop'),
                ),
                _ControlTile(
                  icon: Icons.auto_stories,
                  label: 'Story',
                  accent: accent,
                  onTap: () {
                    api?.story('start');
                  },
                ),
              ],
            ),
          ),

          // Volume slider
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
            child: _VolumeSlider(accent: accent),
          ),
        ],
      ),
    );
  }
}

class _ControlTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color accent;
  final bool active;
  final VoidCallback onTap;
  final VoidCallback? onLongPress;

  const _ControlTile({
    required this.icon,
    required this.label,
    required this.accent,
    this.active = false,
    required this.onTap,
    this.onLongPress,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      onLongPress: onLongPress,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        decoration: BoxDecoration(
          color: active
              ? accent.withValues(alpha: 0.12)
              : JarvisColors.cardBg,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: active
                ? accent.withValues(alpha: 0.3)
                : JarvisColors.borderSubtle,
          ),
        ),
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Icon(
              icon,
              size: 24,
              color: active ? accent : JarvisColors.textSecondary,
            ),
            Text(
              label,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w500,
                color: active ? accent : JarvisColors.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _VolumeSlider extends ConsumerWidget {
  final Color accent;
  const _VolumeSlider({required this.accent});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final volume = ref.watch(volumeProvider);
    final manager = ref.read(connectionManagerProvider);

    return Row(
      children: [
        Icon(
          volume == 0 ? Icons.volume_off : Icons.volume_up,
          size: 16, color: JarvisColors.textTertiary,
        ),
        Expanded(
          child: SliderTheme(
            data: SliderTheme.of(context).copyWith(
              activeTrackColor: accent.withValues(alpha: 0.6),
              thumbColor: accent,
            ),
            child: Slider(
              value: volume.toDouble(),
              min: 0, max: 100,
              onChanged: (v) => manager.api?.setVolume(v.round()),
            ),
          ),
        ),
        Text(
          '$volume',
          style: const TextStyle(
            fontSize: 11, color: JarvisColors.textTertiary,
            fontFamily: 'JetBrains Mono',
          ),
        ),
      ],
    );
  }
}
