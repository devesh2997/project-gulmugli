import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/theme.dart';
import '../state/providers.dart';

/// Text input bar — matches the dashboard transcript input style.
///
/// Frosted glass input with subtle border, send button with accent color.
class TextInputBar extends ConsumerStatefulWidget {
  const TextInputBar({super.key});

  @override
  ConsumerState<TextInputBar> createState() => _TextInputBarState();
}

class _TextInputBarState extends ConsumerState<TextInputBar> {
  final _controller = TextEditingController();
  bool _hasText = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _send() {
    final text = _controller.text.trim();
    if (text.isEmpty) return;

    ref.read(connectionManagerProvider).ws?.sendAction(
      'text_input',
      params: {'text': text},
    );

    _controller.clear();
    setState(() => _hasText = false);
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 8, 8, 12),
      child: Row(
        children: [
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: JarvisColors.cardBg,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: JarvisColors.borderSubtle),
              ),
              child: TextField(
                controller: _controller,
                style: const TextStyle(
                  fontSize: 14, color: JarvisColors.textPrimary,
                ),
                decoration: const InputDecoration(
                  hintText: 'Message Jarvis...',
                  hintStyle: TextStyle(color: JarvisColors.textTertiary),
                  border: InputBorder.none,
                  contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                ),
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _send(),
                onChanged: (v) => setState(() => _hasText = v.trim().isNotEmpty),
              ),
            ),
          ),
          const SizedBox(width: 6),
          GestureDetector(
            onTap: _hasText ? _send : null,
            child: Container(
              width: 40, height: 40,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _hasText
                    ? JarvisColors.textSecondary
                    : JarvisColors.cardBg,
              ),
              child: Icon(
                Icons.arrow_upward,
                size: 18,
                color: _hasText
                    ? JarvisColors.canvasBase
                    : JarvisColors.textTertiary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
