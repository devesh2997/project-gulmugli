import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../state/providers.dart';

/// Light control screen — on/off, color, brightness, scenes.
class LightsScreen extends ConsumerWidget {
  const LightsScreen({super.key});

  static const _presetColors = [
    ('White', '#ffffff'),
    ('Warm', '#FFD700'),
    ('Red', '#FF0000'),
    ('Orange', '#FF8C00'),
    ('Pink', '#FF69B4'),
    ('Purple', '#8B00FF'),
    ('Blue', '#0000FF'),
    ('Cyan', '#00FFFF'),
    ('Green', '#00FF00'),
    ('Yellow', '#FFFF00'),
  ];

  static const _scenes = [
    ('Romantic', 'romantic', Icons.favorite),
    ('Movie', 'movie', Icons.movie),
    ('Party', 'party', Icons.celebration),
    ('Reading', 'reading', Icons.menu_book),
    ('Night', 'night', Icons.nightlight),
    ('Focus', 'focus', Icons.psychology),
  ];

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final lights = ref.watch(lightsProvider);
    final api = ref.watch(connectionManagerProvider).api;

    final isOn = lights?.on ?? false;
    final brightness = lights?.brightness ?? 100;
    final currentColor = lights?.color ?? '#ffffff';

    return Scaffold(
      appBar: AppBar(title: const Text('Lights')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // On/Off toggle
          Card(
            child: SwitchListTile(
              title: Text(
                isOn ? 'Lights On' : 'Lights Off',
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
              ),
              subtitle: isOn ? Text('Brightness: $brightness%') : null,
              value: isOn,
              onChanged: (v) => api?.lightControl(v ? 'on' : 'off'),
              secondary: Icon(
                Icons.lightbulb,
                color: isOn ? Colors.amber : Colors.white24,
                size: 32,
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Brightness slider
          if (isOn) ...[
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Brightness', style: TextStyle(fontWeight: FontWeight.w600)),
                    Slider(
                      value: brightness.toDouble(),
                      min: 1,
                      max: 100,
                      divisions: 99,
                      label: '$brightness%',
                      onChanged: (v) =>
                          api?.lightControl('brightness', value: v.round().toString()),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Color presets
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Color', style: TextStyle(fontWeight: FontWeight.w600)),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 10,
                      runSpacing: 10,
                      children: _presetColors.map((c) {
                        final (name, hex) = c;
                        final color = _hexToColor(hex);
                        final selected = currentColor.toLowerCase() == hex.toLowerCase();
                        return GestureDetector(
                          onTap: () => api?.lightControl('color', value: hex),
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Container(
                                width: 44,
                                height: 44,
                                decoration: BoxDecoration(
                                  color: color,
                                  shape: BoxShape.circle,
                                  border: selected
                                      ? Border.all(color: Colors.white, width: 3)
                                      : Border.all(color: Colors.white24, width: 1),
                                  boxShadow: selected
                                      ? [BoxShadow(color: color.withValues(alpha: 0.5), blurRadius: 8)]
                                      : null,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                name,
                                style: TextStyle(
                                  fontSize: 11,
                                  color: selected ? Colors.white : Colors.white54,
                                ),
                              ),
                            ],
                          ),
                        );
                      }).toList(),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Scenes
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Scenes', style: TextStyle(fontWeight: FontWeight.w600)),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 10,
                      runSpacing: 10,
                      children: _scenes.map((s) {
                        final (name, id, icon) = s;
                        final active = lights?.scene == id;
                        return ActionChip(
                          avatar: Icon(icon, size: 18),
                          label: Text(name),
                          backgroundColor: active ? const Color(0xFF6C63FF).withValues(alpha: 0.3) : null,
                          onPressed: () => api?.lightControl('scene', value: id),
                        );
                      }).toList(),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Color _hexToColor(String hex) {
    hex = hex.replaceAll('#', '');
    if (hex.length == 6) hex = 'FF$hex';
    return Color(int.parse(hex, radix: 16));
  }
}
