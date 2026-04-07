import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/assistant_state.dart';
import '../state/providers.dart';

/// Full music screen — now playing, controls, search.
///
/// Shows album art, title/artist, progress bar, playback controls,
/// and a search bar for playing new songs.
class MusicScreen extends ConsumerStatefulWidget {
  const MusicScreen({super.key});

  @override
  ConsumerState<MusicScreen> createState() => _MusicScreenState();
}

class _MusicScreenState extends ConsumerState<MusicScreen> {
  final _searchController = TextEditingController();
  bool _searching = false;

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _playSong() {
    final query = _searchController.text.trim();
    if (query.isEmpty) return;

    final api = ref.read(connectionManagerProvider).api;
    if (api == null) return;

    setState(() => _searching = true);

    api.musicPlay(query).then((_) {
      if (mounted) {
        setState(() => _searching = false);
        _searchController.clear();
      }
    }).catchError((_) {
      if (mounted) setState(() => _searching = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    final nowPlaying = ref.watch(nowPlayingProvider);
    final api = ref.watch(connectionManagerProvider).api;

    return Scaffold(
      appBar: AppBar(title: const Text('Music')),
      body: Column(
        children: [
          // Now Playing section
          Expanded(
            child: nowPlaying != null
                ? _NowPlayingView(nowPlaying: nowPlaying, api: api)
                : const Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.music_off, size: 64, color: Colors.white24),
                        SizedBox(height: 16),
                        Text(
                          'Nothing playing',
                          style: TextStyle(color: Colors.white38, fontSize: 16),
                        ),
                      ],
                    ),
                  ),
          ),

          // Search bar
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _searchController,
                    decoration: const InputDecoration(
                      hintText: 'Search for a song...',
                      prefixIcon: Icon(Icons.search, color: Colors.white38),
                    ),
                    textInputAction: TextInputAction.search,
                    onSubmitted: (_) => _playSong(),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  onPressed: _searching ? null : _playSong,
                  icon: _searching
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.play_circle_fill, size: 40),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _NowPlayingView extends StatelessWidget {
  final NowPlaying nowPlaying;
  final dynamic api; // ApiClient?

  const _NowPlayingView({required this.nowPlaying, required this.api});

  @override
  Widget build(BuildContext context) {
    final duration = nowPlaying.duration ?? 0;
    final position = nowPlaying.position ?? 0;

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          // Album art
          Container(
            width: 240,
            height: 240,
            decoration: BoxDecoration(
              color: const Color(0xFF6C63FF).withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(20),
            ),
            child: nowPlaying.artUrl != null
                ? ClipRRect(
                    borderRadius: BorderRadius.circular(20),
                    child: Image.network(
                      nowPlaying.artUrl!,
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) =>
                          const Icon(Icons.album, size: 80, color: Colors.white24),
                    ),
                  )
                : const Icon(Icons.album, size: 80, color: Colors.white24),
          ),
          const SizedBox(height: 32),

          // Title
          Text(
            nowPlaying.title,
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
            textAlign: TextAlign.center,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 8),

          // Artist
          Text(
            nowPlaying.artist,
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                  color: Colors.white54,
                ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),

          // Progress bar
          if (duration > 0) ...[
            Slider(
              value: position.clamp(0, duration),
              max: duration,
              onChanged: (v) => api?.musicSeek(v),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(_formatTime(position), style: const TextStyle(color: Colors.white38, fontSize: 12)),
                  Text(_formatTime(duration), style: const TextStyle(color: Colors.white38, fontSize: 12)),
                ],
              ),
            ),
          ],
          const SizedBox(height: 16),

          // Controls
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              IconButton(
                icon: const Icon(Icons.skip_previous, size: 36),
                onPressed: () => api?.musicControl('skip'), // TODO: previous
              ),
              const SizedBox(width: 16),
              IconButton(
                icon: Icon(
                  nowPlaying.paused ? Icons.play_circle_fill : Icons.pause_circle_filled,
                  size: 56,
                ),
                onPressed: () {
                  final action = nowPlaying.paused ? 'resume' : 'pause';
                  api?.musicControl(action);
                },
              ),
              const SizedBox(width: 16),
              IconButton(
                icon: const Icon(Icons.skip_next, size: 36),
                onPressed: () => api?.musicControl('skip'),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Stop
          TextButton.icon(
            onPressed: () => api?.musicControl('stop'),
            icon: const Icon(Icons.stop, size: 18),
            label: const Text('Stop'),
          ),
        ],
      ),
    );
  }

  String _formatTime(double seconds) {
    final m = seconds ~/ 60;
    final s = (seconds % 60).toInt();
    return '${m.toString().padLeft(2, '0')}:${s.toString().padLeft(2, '0')}';
  }
}
