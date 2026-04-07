import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../config/theme.dart';

/// Animated orb avatar matching the dashboard's AvatarOrb component.
///
/// Multi-layer glowing sphere with state-driven animations:
/// - idle: gentle breathing pulse
/// - listening: vertical elongation + sonar rings
/// - thinking: rotation + warm color shift
/// - speaking: sharp rhythmic pulse
/// - sleeping: very slow dim breathing
///
/// Each state has distinct scale, opacity, glow, and timing.
class AvatarWidget extends StatefulWidget {
  final String state;
  final String personalityId;

  const AvatarWidget({
    super.key,
    required this.state,
    this.personalityId = 'jarvis',
  });

  @override
  State<AvatarWidget> createState() => _AvatarWidgetState();
}

class _AvatarWidgetState extends State<AvatarWidget>
    with TickerProviderStateMixin {
  late AnimationController _breatheController;
  late AnimationController _glowController;
  late AnimationController _rotateController;

  @override
  void initState() {
    super.initState();
    _breatheController = AnimationController(vsync: this);
    _glowController = AnimationController(vsync: this);
    _rotateController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    );
    _applyState();
  }

  @override
  void didUpdateWidget(AvatarWidget old) {
    super.didUpdateWidget(old);
    if (old.state != widget.state || old.personalityId != widget.personalityId) {
      _applyState();
    }
  }

  void _applyState() {
    final cfg = _configFor(widget.state);

    _breatheController.duration = cfg.breatheDuration;
    _breatheController.repeat(reverse: true);

    _glowController.duration = Duration(
      milliseconds: (cfg.breatheDuration.inMilliseconds * 1.2).round(),
    );
    _glowController.repeat(reverse: true);

    if (widget.state == 'thinking') {
      _rotateController.repeat();
    } else {
      _rotateController.stop();
      _rotateController.value = 0;
    }
  }

  @override
  void dispose() {
    _breatheController.dispose();
    _glowController.dispose();
    _rotateController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final accent = PersonalityColors.accentFor(widget.personalityId);
    final cfg = _configFor(widget.state);
    final screenWidth = MediaQuery.of(context).size.width;
    final orbSize = (screenWidth * 0.35).clamp(120.0, 280.0);

    return SizedBox(
      width: orbSize * 2,
      height: orbSize * 2,
      child: AnimatedBuilder(
        animation: Listenable.merge([
          _breatheController,
          _glowController,
          _rotateController,
        ]),
        builder: (context, _) {
          final breathe = _breatheController.value;
          final glow = _glowController.value;
          final rotate = _rotateController.value * math.pi * 2;

          final scale = cfg.scale + (breathe * 0.06 * cfg.scale);
          final opacity = cfg.opacity - (breathe * 0.09 * cfg.opacity);
          final glowOpacity = cfg.glowOpacity + (glow * 0.15);
          final glowScale = cfg.glowScale + (glow * 0.25);

          // Warm shift for thinking state
          final orbColor = widget.state == 'thinking'
              ? Color.lerp(accent, const Color(0xFFFFA03C), 0.6)!
              : accent;

          return Stack(
            alignment: Alignment.center,
            children: [
              // Layer 1: Outer glow
              Transform.scale(
                scale: glowScale,
                child: Container(
                  width: orbSize * 1.8,
                  height: orbSize * 1.8,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: orbColor.withValues(alpha: glowOpacity * 0.5),
                        blurRadius: orbSize * 0.3,
                        spreadRadius: orbSize * 0.05,
                      ),
                    ],
                  ),
                ),
              ),

              // Layer 2: Sonar rings (listening only)
              if (widget.state == 'listening') ...[
                _SonarRing(accent: accent, size: orbSize, delay: 0),
                _SonarRing(accent: accent, size: orbSize, delay: 0.5),
              ],

              // Layer 3: Speaking ripple
              if (widget.state == 'speaking')
                _SpeakingRipple(accent: accent, size: orbSize),

              // Layer 4: Core orb
              Transform.scale(
                scale: scale,
                child: Transform.rotate(
                  angle: widget.state == 'thinking' ? rotate : 0,
                  child: Container(
                    width: orbSize,
                    height: orbSize,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: orbColor.withValues(alpha: cfg.borderGlow),
                        width: 1.5,
                      ),
                      gradient: RadialGradient(
                        center: const Alignment(-0.3, -0.3),
                        radius: 0.85,
                        colors: [
                          orbColor.withValues(alpha: opacity * 0.25),
                          orbColor.withValues(alpha: opacity * 0.12),
                          orbColor.withValues(alpha: opacity * 0.04),
                          Colors.transparent,
                        ],
                        stops: const [0.0, 0.4, 0.7, 1.0],
                      ),
                    ),
                  ),
                ),
              ),

              // Layer 5: Inner highlight
              Transform.scale(
                scale: scale,
                child: Transform.rotate(
                  angle: widget.state == 'thinking' ? -rotate * 0.7 : 0,
                  child: Container(
                    width: orbSize * 0.4,
                    height: orbSize * 0.4,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: RadialGradient(
                        colors: [
                          orbColor.withValues(alpha: opacity * 0.3),
                          Colors.transparent,
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

/// Per-state animation configuration — matches dashboard exactly.
class _OrbConfig {
  final double scale;
  final double opacity;
  final double glowOpacity;
  final double glowScale;
  final double borderGlow;
  final Duration breatheDuration;

  const _OrbConfig({
    required this.scale,
    required this.opacity,
    required this.glowOpacity,
    required this.glowScale,
    required this.borderGlow,
    required this.breatheDuration,
  });
}

_OrbConfig _configFor(String state) {
  switch (state) {
    case 'listening':
      return const _OrbConfig(
        scale: 1.15, opacity: 0.95, glowOpacity: 0.65,
        glowScale: 1.5, borderGlow: 0.35,
        breatheDuration: Duration(milliseconds: 1400),
      );
    case 'thinking':
      return const _OrbConfig(
        scale: 0.92, opacity: 0.8, glowOpacity: 0.45,
        glowScale: 1.3, borderGlow: 0.2,
        breatheDuration: Duration(milliseconds: 1000),
      );
    case 'speaking':
      return const _OrbConfig(
        scale: 1.12, opacity: 1.0, glowOpacity: 0.7,
        glowScale: 1.6, borderGlow: 0.4,
        breatheDuration: Duration(milliseconds: 600),
      );
    case 'sleeping':
      return const _OrbConfig(
        scale: 0.85, opacity: 0.15, glowOpacity: 0.03,
        glowScale: 0.8, borderGlow: 0.02,
        breatheDuration: Duration(milliseconds: 6000),
      );
    default: // idle
      return const _OrbConfig(
        scale: 1.0, opacity: 0.6, glowOpacity: 0.2,
        glowScale: 1.0, borderGlow: 0.12,
        breatheDuration: Duration(milliseconds: 4000),
      );
  }
}

/// Sonar ring animation for listening state.
class _SonarRing extends StatefulWidget {
  final Color accent;
  final double size;
  final double delay;

  const _SonarRing({
    required this.accent,
    required this.size,
    this.delay = 0,
  });

  @override
  State<_SonarRing> createState() => _SonarRingState();
}

class _SonarRingState extends State<_SonarRing>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    );
    Future.delayed(
      Duration(milliseconds: (widget.delay * 1500).round()),
      () { if (mounted) _controller.repeat(); },
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        final scale = 1.0 + (_controller.value * 1.2);
        final opacity = (1.0 - _controller.value) * 0.3;
        return Transform.scale(
          scale: scale,
          child: Container(
            width: widget.size,
            height: widget.size,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(
                color: widget.accent.withValues(alpha: opacity),
                width: 1.5,
              ),
            ),
          ),
        );
      },
    );
  }
}

/// Ripple ring for speaking state.
class _SpeakingRipple extends StatefulWidget {
  final Color accent;
  final double size;

  const _SpeakingRipple({required this.accent, required this.size});

  @override
  State<_SpeakingRipple> createState() => _SpeakingRippleState();
}

class _SpeakingRippleState extends State<_SpeakingRipple>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        final scale = 1.0 + (_controller.value * 0.8);
        final opacity = (1.0 - _controller.value) * 0.25;
        return Transform.scale(
          scale: scale,
          child: Container(
            width: widget.size * 0.8,
            height: widget.size * 0.8,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(
                color: widget.accent.withValues(alpha: opacity),
                width: 2,
              ),
            ),
          ),
        );
      },
    );
  }
}
