import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../state/providers.dart';

/// Settings screen — assistant config + app connection management.
///
/// Mirrors the dashboard settings panel. Shows dynamic settings
/// fetched from the backend's config_manager.
class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  List<dynamic>? _settings;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    try {
      final api = ref.read(connectionManagerProvider).api;
      if (api != null) {
        final settings = await api.getSettings();
        if (mounted) setState(() { _settings = settings; _loading = false; });
      }
    } catch (e) {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(assistantStateProvider);
    final manager = ref.watch(connectionManagerProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Connection info
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Connection', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  _InfoRow('Server', '${manager.host}:${manager.port}'),
                  _InfoRow('Status', state.state),
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton(
                      onPressed: () async {
                        await manager.forget();
                      },
                      child: const Text('Disconnect & Forget'),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Personality switcher
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Personality', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  RadioGroup<String>(
                    groupValue: state.personalityId,
                    onChanged: (String? v) {
                      if (v != null) manager.api?.switchPersonality(v);
                    },
                    child: Column(
                      children: state.personalities.map((p) => RadioListTile<String>(
                            title: Text(p.displayName),
                            subtitle: Text(p.description),
                            value: p.id,
                          )).toList(),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Volume
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Volume', style: Theme.of(context).textTheme.titleMedium),
                  Slider(
                    value: state.volume.toDouble(),
                    min: 0,
                    max: 100,
                    divisions: 20,
                    label: '${state.volume}',
                    onChanged: (v) => manager.api?.setVolume(v.round()),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Dynamic settings from backend
          if (_loading)
            const Center(child: Padding(
              padding: EdgeInsets.all(24),
              child: CircularProgressIndicator(),
            ))
          else if (_settings != null && _settings!.isNotEmpty) ...[
            Text('Assistant Settings',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            ..._settings!.map((s) {
              final setting = s as Map<String, dynamic>;
              return _SettingTile(setting: setting, api: manager.api);
            }),
          ],

          const SizedBox(height: 32),

          // App info
          Center(
            child: Text(
              'JARVIS Companion v1.0.0',
              style: TextStyle(color: Colors.white24, fontSize: 12),
            ),
          ),
          const SizedBox(height: 16),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;

  const _InfoRow(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Colors.white54)),
          Text(value),
        ],
      ),
    );
  }
}

class _SettingTile extends StatelessWidget {
  final Map<String, dynamic> setting;
  final dynamic api;

  const _SettingTile({required this.setting, required this.api});

  @override
  Widget build(BuildContext context) {
    final path = setting['path']?.toString() ?? '';
    final label = setting['label']?.toString() ?? path;
    final type = setting['type']?.toString() ?? 'text';
    final value = setting['value'];

    if (type == 'bool' || type == 'checkbox') {
      return SwitchListTile(
        title: Text(label),
        value: value == true,
        onChanged: (v) => api?.updateSetting(path, v),
      );
    }

    return ListTile(
      title: Text(label),
      trailing: Text(value?.toString() ?? '', style: const TextStyle(color: Colors.white54)),
    );
  }
}
