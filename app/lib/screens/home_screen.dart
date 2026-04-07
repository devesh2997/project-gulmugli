import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../config/theme.dart';
import '../models/assistant_state.dart';
import '../state/providers.dart';
import '../widgets/avatar_widget.dart';
import '../widgets/connection_banner.dart';
import '../widgets/compact_music_bar.dart';
import '../widgets/slide_panel.dart';
import '../widgets/transcript_panel.dart';
import '../widgets/controls_panel.dart';

/// Home screen — gesture-driven canvas matching the dashboard.
///
/// The orb sits at center. Swipe gestures reveal panels:
/// - Swipe up   → Transcript panel (from bottom)
/// - Swipe left → Controls panel (from right)
/// - Swipe right → Settings
/// - Swipe down → Close any open panel
/// - Tap orb → Quick voice input (future)
///
/// The background has a subtle gradient tinted by the active personality color.
class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  _PanelState _openPanel = _PanelState.none;

  void _onPanEnd(DragEndDetails details, Axis axis) {
    final v = axis == Axis.vertical
        ? details.velocity.pixelsPerSecond.dy
        : details.velocity.pixelsPerSecond.dx;

    if (v.abs() < 200) return; // Too slow

    if (axis == Axis.vertical) {
      if (v < 0) {
        // Swipe up
        setState(() => _openPanel = _PanelState.transcript);
      } else {
        // Swipe down — close
        setState(() => _openPanel = _PanelState.none);
      }
    } else {
      if (v < 0) {
        // Swipe left → controls from right
        setState(() => _openPanel = _PanelState.controls);
      } else {
        // Swipe right → settings
        context.push('/settings');
      }
    }
  }

  void _closePanel() {
    setState(() => _openPanel = _PanelState.none);
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(assistantStateProvider);
    final nowPlaying = ref.watch(nowPlayingProvider);
    final personality = ref.watch(personalityProvider);
    final accent = PersonalityColors.accentFor(personality);
    return Scaffold(
      body: Stack(
        children: [
          // ── Layer 0: Canvas background with personality tint ──
          _CanvasBackground(accent: accent),

          // ── Layer 1: Main gesture area ──
          GestureDetector(
            onVerticalDragEnd: (d) => _onPanEnd(d, Axis.vertical),
            onHorizontalDragEnd: (d) => _onPanEnd(d, Axis.horizontal),
            behavior: HitTestBehavior.translucent,
            child: SafeArea(
              child: Column(
                children: [
                  const ConnectionBanner(),

                  // Top bar — minimal
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                    child: Row(
                      children: [
                        // Personality indicator dot
                        Container(
                          width: 8, height: 8,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: accent,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          _displayName(state, personality),
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w500,
                            color: JarvisColors.textSecondary,
                            letterSpacing: 0.02,
                          ),
                        ),
                        const Spacer(),
                        // Volume pill
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: JarvisColors.pillBg,
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(
                                state.volume == 0 ? Icons.volume_off : Icons.volume_up,
                                size: 12, color: JarvisColors.textTertiary,
                              ),
                              const SizedBox(width: 3),
                              Text(
                                '${state.volume}',
                                style: const TextStyle(
                                  fontSize: 11, color: JarvisColors.textTertiary,
                                  fontFamily: 'JetBrains Mono',
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),

                  // ── Center: Orb ──
                  Expanded(
                    child: Center(
                      child: AvatarWidget(
                        state: state.state,
                        personalityId: personality,
                      ),
                    ),
                  ),

                  // ── Clock ──
                  _Clock(),

                  const SizedBox(height: 8),

                  // ── State hint ──
                  Text(
                    _stateHint(state.state),
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0.12,
                      color: JarvisColors.textTertiary,
                    ),
                  ),

                  const SizedBox(height: 16),

                  // ── Compact music bar ──
                  if (nowPlaying != null)
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 20),
                      child: CompactMusicBar(
                        nowPlaying: nowPlaying,
                        accent: accent,
                        onTap: () => context.push('/music'),
                      ),
                    ),

                  // ── Swipe hints ──
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12, top: 8),
                    child: _SwipeHints(accent: accent),
                  ),
                ],
              ),
            ),
          ),

          // ── Layer 2: Slide panels ──

          // Transcript (from bottom)
          if (_openPanel == _PanelState.transcript)
            SlidePanel(
              direction: SlideDirection.bottom,
              accent: accent,
              onClose: _closePanel,
              child: TranscriptPanel(accent: accent),
            ),

          // Controls (from right)
          if (_openPanel == _PanelState.controls)
            SlidePanel(
              direction: SlideDirection.right,
              accent: accent,
              onClose: _closePanel,
              child: ControlsPanel(accent: accent),
            ),
        ],
      ),
    );
  }

  String _displayName(AssistantState state, String id) {
    final match = state.personalities.where((p) => p.id == id);
    return match.isNotEmpty ? match.first.displayName : id;
  }

  String _stateHint(String s) {
    switch (s) {
      case 'listening': return 'LISTENING';
      case 'thinking': return 'THINKING';
      case 'speaking': return 'SPEAKING';
      case 'sleeping': return 'SLEEPING';
      default: return 'SWIPE TO EXPLORE';
    }
  }
}

enum _PanelState { none, transcript, controls }

/// Canvas background with personality-tinted gradient.
class _CanvasBackground extends StatelessWidget {
  final Color accent;
  const _CanvasBackground({required this.accent});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [JarvisColors.canvasStart, JarvisColors.canvasEnd],
        ),
      ),
      child: Container(
        // Personality ambient glow overlay
        decoration: BoxDecoration(
          gradient: RadialGradient(
            center: Alignment.center,
            radius: 0.8,
            colors: [
              accent.withValues(alpha: 0.06),
              Colors.transparent,
            ],
          ),
        ),
      ),
    );
  }
}

/// Monospace clock matching the dashboard.
class _Clock extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return StreamBuilder(
      stream: Stream.periodic(const Duration(seconds: 1)),
      builder: (context, _) {
        final now = DateTime.now();
        final time = '${now.hour.toString().padLeft(2, '0')}:${now.minute.toString().padLeft(2, '0')}';
        return Text(
          time,
          style: const TextStyle(
            fontSize: 32,
            fontWeight: FontWeight.w200,
            letterSpacing: 0.02,
            fontFamily: 'JetBrains Mono',
            color: JarvisColors.textSecondary,
          ),
        );
      },
    );
  }
}

/// Subtle swipe direction hints at the bottom.
class _SwipeHints extends StatelessWidget {
  final Color accent;
  const _SwipeHints({required this.accent});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        _hint('←', 'settings'),
        const SizedBox(width: 16),
        _hint('↑', 'chat'),
        const SizedBox(width: 16),
        _hint('→', 'controls'),
      ],
    );
  }

  Widget _hint(String arrow, String label) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(arrow, style: TextStyle(
          fontSize: 11, color: JarvisColors.textTertiary,
          fontFamily: 'JetBrains Mono',
        )),
        const SizedBox(width: 3),
        Text(label, style: const TextStyle(
          fontSize: 9, color: JarvisColors.textTertiary,
          letterSpacing: 0.1,
        )),
      ],
    );
  }
}
