import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/theme.dart';
import '../services/discovery_service.dart';
import '../state/providers.dart';

/// Connection screen — warm, minimal, matches the dashboard's dark canvas.
class ConnectScreen extends ConsumerStatefulWidget {
  const ConnectScreen({super.key});

  @override
  ConsumerState<ConnectScreen> createState() => _ConnectScreenState();
}

class _ConnectScreenState extends ConsumerState<ConnectScreen>
    with SingleTickerProviderStateMixin {
  final _hostController = TextEditingController();
  final _portController = TextEditingController(text: '8766');
  final _discovery = DiscoveryService();
  late AnimationController _pulseController;

  bool _connecting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 3000),
    )..repeat(reverse: true);
    _discovery.startScan();
  }

  @override
  void dispose() {
    _hostController.dispose();
    _portController.dispose();
    _pulseController.dispose();
    _discovery.dispose();
    super.dispose();
  }

  Future<void> _connect() async {
    final host = _hostController.text.trim();
    final port = int.tryParse(_portController.text.trim()) ?? 8766;

    if (host.isEmpty) {
      setState(() => _error = 'Server IP is required.');
      return;
    }

    setState(() { _connecting = true; _error = null; });

    final manager = ref.read(connectionManagerProvider);
    final success = await manager.connect(host: host, port: port);

    if (mounted) {
      setState(() {
        _connecting = false;
        _error = success ? null : 'Could not connect. Is the server running?';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    // Default accent (jarvis gold) since we're not connected yet
    const accent = Color(0xFFE8C070);

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [JarvisColors.canvasStart, JarvisColors.canvasEnd],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(32),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  // Orb as logo — small breathing circle
                  AnimatedBuilder(
                    animation: _pulseController,
                    builder: (context, _) {
                      final scale = 1.0 + (_pulseController.value * 0.05);
                      final opacity = 0.4 + (_pulseController.value * 0.2);
                      return Transform.scale(
                        scale: scale,
                        child: Container(
                          width: 80, height: 80,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            border: Border.all(
                              color: accent.withValues(alpha: 0.2),
                              width: 1.5,
                            ),
                            gradient: RadialGradient(
                              center: const Alignment(-0.3, -0.3),
                              colors: [
                                accent.withValues(alpha: opacity * 0.2),
                                accent.withValues(alpha: opacity * 0.05),
                                Colors.transparent,
                              ],
                            ),
                            boxShadow: [
                              BoxShadow(
                                color: accent.withValues(alpha: 0.1),
                                blurRadius: 30,
                                spreadRadius: 5,
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                  const SizedBox(height: 24),

                  const Text(
                    'Connect to Jarvis',
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w600,
                      color: JarvisColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Enter the server address\nto connect.',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 13,
                      color: JarvisColors.textTertiary,
                    ),
                  ),
                  const SizedBox(height: 36),

                  // Discovered servers
                  StreamBuilder<List<DiscoveredServer>>(
                    stream: _discovery.servers,
                    builder: (context, snapshot) {
                      final servers = snapshot.data ?? [];
                      if (servers.isEmpty) return const SizedBox.shrink();
                      return Column(
                        children: [
                          ...servers.map((s) => Container(
                                margin: const EdgeInsets.only(bottom: 8),
                                decoration: frostedGlass(borderRadius: 14),
                                child: ListTile(
                                  leading: Container(
                                    width: 8, height: 8,
                                    decoration: BoxDecoration(
                                      shape: BoxShape.circle,
                                      color: JarvisColors.success,
                                    ),
                                  ),
                                  title: Text(s.name, style: const TextStyle(fontSize: 14)),
                                  subtitle: Text('${s.host}:${s.port}',
                                      style: const TextStyle(fontSize: 12, fontFamily: 'JetBrains Mono')),
                                  onTap: () {
                                    _hostController.text = s.host;
                                    _portController.text = s.port.toString();
                                  },
                                ),
                              )),
                          const SizedBox(height: 16),
                        ],
                      );
                    },
                  ),

                  // Server IP + Port
                  Row(
                    children: [
                      Expanded(
                        flex: 3,
                        child: TextField(
                          controller: _hostController,
                          decoration: const InputDecoration(
                            hintText: '192.168.1.100',
                            labelText: 'Server IP',
                          ),
                          keyboardType: TextInputType.url,
                          style: const TextStyle(
                            fontFamily: 'JetBrains Mono', fontSize: 14,
                          ),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        flex: 1,
                        child: TextField(
                          controller: _portController,
                          decoration: const InputDecoration(labelText: 'Port'),
                          keyboardType: TextInputType.number,
                          style: const TextStyle(
                            fontFamily: 'JetBrains Mono', fontSize: 14,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),

                  // Error
                  if (_error != null) ...[
                    Text(
                      _error!,
                      style: const TextStyle(color: JarvisColors.error, fontSize: 13),
                    ),
                    const SizedBox(height: 14),
                  ],

                  // Connect button
                  SizedBox(
                    width: double.infinity,
                    child: GestureDetector(
                      onTap: _connecting ? null : _connect,
                      child: Container(
                        height: 48,
                        decoration: BoxDecoration(
                          color: _connecting
                              ? accent.withValues(alpha: 0.1)
                              : accent.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(14),
                          border: Border.all(
                            color: accent.withValues(alpha: 0.3),
                          ),
                        ),
                        child: Center(
                          child: _connecting
                              ? SizedBox(
                                  width: 18, height: 18,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    color: accent.withValues(alpha: 0.7),
                                  ),
                                )
                              : Text(
                                  'Connect',
                                  style: TextStyle(
                                    fontSize: 14,
                                    fontWeight: FontWeight.w600,
                                    color: accent,
                                  ),
                                ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
