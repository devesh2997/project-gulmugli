import 'dart:ui';

import 'package:flutter/material.dart';

import '../config/theme.dart';

/// Direction a panel slides in from.
enum SlideDirection { bottom, left, right }

/// Frosted glass slide panel — matches the dashboard's SlidePanel component.
///
/// Slides in from bottom/left/right with a backdrop blur, personality-
/// accent edge glow, and drag handle. Swipe down or tap backdrop to close.
class SlidePanel extends StatefulWidget {
  final SlideDirection direction;
  final Color accent;
  final VoidCallback onClose;
  final Widget child;

  const SlidePanel({
    super.key,
    required this.direction,
    required this.accent,
    required this.onClose,
    required this.child,
  });

  @override
  State<SlidePanel> createState() => _SlidePanelState();
}

class _SlidePanelState extends State<SlidePanel>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<Offset> _slideAnimation;
  late Animation<double> _fadeAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 350),
    );

    final begin = switch (widget.direction) {
      SlideDirection.bottom => const Offset(0, 1),
      SlideDirection.left => const Offset(-1, 0),
      SlideDirection.right => const Offset(1, 0),
    };

    _slideAnimation = Tween<Offset>(begin: begin, end: Offset.zero)
        .animate(CurvedAnimation(parent: _controller, curve: Curves.easeOutCubic));

    _fadeAnimation = Tween<double>(begin: 0, end: 0.4)
        .animate(CurvedAnimation(parent: _controller, curve: Curves.easeOut));

    _controller.forward();
  }

  Future<void> _dismiss() async {
    await _controller.reverse();
    widget.onClose();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.of(context).size;
    final isBottom = widget.direction == SlideDirection.bottom;

    return Stack(
      children: [
        // Backdrop
        GestureDetector(
          onTap: _dismiss,
          onVerticalDragEnd: (d) {
            if (d.velocity.pixelsPerSecond.dy > 200) _dismiss();
          },
          child: AnimatedBuilder(
            animation: _fadeAnimation,
            builder: (context, _) => Container(
              color: Colors.black.withValues(alpha: _fadeAnimation.value),
            ),
          ),
        ),

        // Panel
        Positioned(
          bottom: isBottom ? 0 : null,
          top: isBottom ? null : 0,
          left: isBottom ? 0 : (widget.direction == SlideDirection.right ? null : 0),
          right: isBottom ? 0 : (widget.direction == SlideDirection.left ? null : 0),
          width: isBottom ? null : size.width * 0.85,
          height: isBottom ? size.height * 0.7 : size.height,
          child: SlideTransition(
            position: _slideAnimation,
            child: GestureDetector(
              onVerticalDragEnd: isBottom
                  ? (d) { if (d.velocity.pixelsPerSecond.dy > 200) _dismiss(); }
                  : null,
              child: ClipRRect(
                borderRadius: BorderRadius.only(
                  topLeft: isBottom || widget.direction == SlideDirection.right
                      ? const Radius.circular(24) : Radius.zero,
                  topRight: isBottom || widget.direction == SlideDirection.left
                      ? const Radius.circular(24) : Radius.zero,
                ),
                child: BackdropFilter(
                  filter: ImageFilter.blur(sigmaX: 28, sigmaY: 28),
                  child: Container(
                    decoration: BoxDecoration(
                      color: JarvisColors.panelBg,
                      border: Border(
                        top: isBottom
                            ? BorderSide(color: widget.accent.withValues(alpha: 0.3), width: 1)
                            : BorderSide.none,
                        left: widget.direction == SlideDirection.right
                            ? BorderSide(color: widget.accent.withValues(alpha: 0.3), width: 1)
                            : BorderSide.none,
                        right: widget.direction == SlideDirection.left
                            ? BorderSide(color: widget.accent.withValues(alpha: 0.3), width: 1)
                            : BorderSide.none,
                      ),
                    ),
                    child: Column(
                      children: [
                        // Drag handle
                        if (isBottom)
                          Padding(
                            padding: const EdgeInsets.only(top: 12, bottom: 4),
                            child: Container(
                              width: 44, height: 4,
                              decoration: BoxDecoration(
                                color: widget.accent.withValues(alpha: 0.5),
                                borderRadius: BorderRadius.circular(2),
                              ),
                            ),
                          ),
                        Expanded(child: widget.child),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
