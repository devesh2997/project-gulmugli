import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../config/constants.dart';
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
  final _tokenController = TextEditingController();
  final _discovery = DiscoveryService();
  late AnimationController _pulseController;

  bool _connecting = false;
  bool _showTokenField = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 3000),
    )..repeat(reverse: true);
    _discovery.startScan();
    // Pre-fill last-known IP/port/token so the user doesn't have to retype
    // after every reconnect attempt or app reinstall. Async — fires after
    // first build, populates if a value exists. Empty defaults are fine.
    _loadSavedConnection();
  }

  Future<void> _loadSavedConnection() async {
    final prefs = await SharedPreferences.getInstance();
    if (!mounted) return;
    final host = prefs.getString(kPrefServerHost);
    final port = prefs.getInt(kPrefServerPort);
    final token = prefs.getString(kPrefApiToken);
    if (host != null && _hostController.text.isEmpty) {
      _hostController.text = host;
    }
    if (port != null && port != 8766) {
      _portController.text = port.toString();
    }
    if (token != null && token.isNotEmpty) {
      _tokenController.text = token;
    }
  }

  @override
  void dispose() {
    _hostController.dispose();
    _portController.dispose();
    _tokenController.dispose();
    _pulseController.dispose();
    _discovery.dispose();
    super.dispose();
  }

  Future<void> _connect() async {
    final host = _hostController.text.trim();
    final port = int.tryParse(_portController.text.trim()) ?? 8766;
    final token = _tokenController.text.trim().isEmpty
        ? null
        : _tokenController.text.trim();

    if (host.isEmpty) {
      setState(() => _error = 'Server IP is required.');
      return;
    }

    setState(() { _connecting = true; _error = null; });

    final manager = ref.read(connectionManagerProvider);
    final success = await manager.connect(host: host, port: port, token: token);

    if (mounted) {
      setState(() {
        _connecting = false;
        _error = success
            ? null
            : 'Could not connect. Check the address, make sure JARVIS is running, '
                'and (if auth is enabled on the server) verify the token.';
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

                  // Token row — collapsed by default. Most users won't need
                  // to enter one (token is server-generated; the dev shares
                  // it once and we persist it). The "Use a token" link
                  // expands the field for first-time pairing.
                  if (!_showTokenField) ...[
                    const SizedBox(height: 8),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: TextButton(
                        onPressed: () =>
                            setState(() => _showTokenField = true),
                        style: TextButton.styleFrom(
                          padding: EdgeInsets.zero,
                          minimumSize: const Size(0, 0),
                          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        ),
                        child: Text(
                          'Use a token',
                          style: TextStyle(
                            fontSize: 12,
                            color: accent.withValues(alpha: 0.7),
                          ),
                        ),
                      ),
                    ),
                  ] else ...[
                    const SizedBox(height: 12),
                    TextField(
                      controller: _tokenController,
                      decoration: const InputDecoration(
                        labelText: 'API token',
                        hintText: 'paste from server log',
                      ),
                      style: const TextStyle(
                        fontFamily: 'JetBrains Mono', fontSize: 13,
                      ),
                    ),
                  ],

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
