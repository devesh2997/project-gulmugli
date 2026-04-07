import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/theme.dart';
import '../models/assistant_state.dart';
import '../state/providers.dart';
import 'text_input_bar.dart';

/// Transcript panel — slides up from bottom, shows conversation + text input.
class TranscriptPanel extends ConsumerWidget {
  final Color accent;
  const TranscriptPanel({super.key, required this.accent});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final transcript = ref.watch(transcriptProvider);

    return Column(
      children: [
        // Tab label
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Text(
            'TRANSCRIPT',
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.12,
              color: accent.withValues(alpha: 0.7),
            ),
          ),
        ),

        // Messages
        Expanded(
          child: transcript.isEmpty
              ? const Center(
                  child: Text(
                    'No messages yet.\nType below or speak to Jarvis.',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 13,
                      color: JarvisColors.textTertiary,
                    ),
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  reverse: true,
                  itemCount: transcript.length,
                  itemBuilder: (context, index) {
                    final entry = transcript[transcript.length - 1 - index];
                    return _TranscriptMessage(entry: entry, accent: accent);
                  },
                ),
        ),

        // Text input
        const TextInputBar(),
      ],
    );
  }
}

class _TranscriptMessage extends StatelessWidget {
  final TranscriptEntry entry;
  final Color accent;

  const _TranscriptMessage({required this.entry, required this.accent});

  @override
  Widget build(BuildContext context) {
    final isUser = entry.role == 'user';

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 3),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.72,
        ),
        decoration: BoxDecoration(
          color: isUser
              ? accent.withValues(alpha: 0.1)
              : JarvisColors.cardBg,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(16),
            topRight: const Radius.circular(16),
            bottomLeft: isUser ? const Radius.circular(16) : const Radius.circular(4),
            bottomRight: isUser ? const Radius.circular(4) : const Radius.circular(16),
          ),
          border: Border(
            left: isUser
                ? BorderSide.none
                : BorderSide(color: accent.withValues(alpha: 0.3), width: 3),
          ),
        ),
        child: Text(
          entry.text,
          style: const TextStyle(
            fontSize: 14,
            letterSpacing: 0.02,
            color: JarvisColors.textPrimary,
          ),
        ),
      ),
    );
  }
}
