import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/assistant_state.dart';
import '../services/connection_manager.dart';

/// Processes WebSocket messages and maintains typed assistant state.
///
/// This is the Dart equivalent of useAssistant.ts in the React dashboard.
/// Each incoming WS message type maps to a state update.
class AssistantNotifier extends StateNotifier<AssistantState> {
  final ConnectionManager _manager;
  StreamSubscription? _wsSub;
  StreamSubscription? _statusSub;

  AssistantNotifier(this._manager) : super(const AssistantState()) {
    _listenForConnection();
  }

  void _listenForConnection() {
    // When WebSocket connects/reconnects, subscribe to messages.
    _statusSub = _manager.statusStream.listen((status) {
      if (status == ConnectionStatus.connected) {
        _wsSub?.cancel();
        final ws = _manager.ws;
        if (ws != null) {
          _wsSub = ws.messages.listen(_handleMessage);
        }
      }
    });

    // Also subscribe immediately if already connected.
    final ws = _manager.ws;
    if (ws != null) {
      _wsSub = ws.messages.listen(_handleMessage);
    }
  }

  void _handleMessage(Map<String, dynamic> msg) {
    final type = msg['type'] as String?;
    if (type == null || type.startsWith('_')) return; // Internal messages

    switch (type) {
      case 'state':
        state = state.copyWith(state: msg['state'] as String?);

      case 'personality':
        state = state.copyWith(personalityId: msg['id'] as String?);

      case 'volume':
        state = state.copyWith(volume: msg['level'] as int?);

      case 'now_playing':
        state = state.copyWith(
          nowPlaying: () => NowPlaying.fromJson(msg),
        );

      case 'music_stopped':
        state = state.copyWith(nowPlaying: () => null);

      case 'music_paused':
        final current = state.nowPlaying;
        if (current != null) {
          state = state.copyWith(
            nowPlaying: () => NowPlaying(
              title: current.title,
              artist: current.artist,
              album: current.album,
              artUrl: current.artUrl,
              videoId: current.videoId,
              duration: current.duration,
              position: current.position,
              paused: msg['paused'] as bool? ?? true,
            ),
          );
        }

      case 'playback_position':
        final current = state.nowPlaying;
        if (current != null) {
          state = state.copyWith(
            nowPlaying: () => NowPlaying(
              title: current.title,
              artist: current.artist,
              album: current.album,
              artUrl: current.artUrl,
              videoId: current.videoId,
              duration: (msg['duration'] as num?)?.toDouble() ?? current.duration,
              position: (msg['position'] as num?)?.toDouble(),
              paused: current.paused,
            ),
          );
        }

      case 'lights':
        state = state.copyWith(
          lights: () => LightsState.fromJson(msg),
        );

      case 'personalities':
        final list = (msg['list'] as List<dynamic>? ?? [])
            .map((e) => PersonalityInfo.fromJson(e as Map<String, dynamic>))
            .toList();
        state = state.copyWith(personalities: list);

      case 'transcript':
        final entry = TranscriptEntry(
          text: msg['text']?.toString() ?? '',
          role: msg['role']?.toString() ?? 'assistant',
          timestamp: DateTime.now(),
        );
        // Keep last 50 transcript entries
        final updated = [...state.transcript, entry];
        if (updated.length > 50) {
          state = state.copyWith(transcript: updated.sublist(updated.length - 50));
        } else {
          state = state.copyWith(transcript: updated);
        }

      case 'sleep_mode':
        state = state.copyWith(sleepMode: msg['active'] as bool?);

      case 'weather_show':
        final data = msg['data'] as Map<String, dynamic>?;
        if (data != null) {
          state = state.copyWith(weather: () => WeatherData.fromJson(data));
        }

      case 'quiz_show':
        state = state.copyWith(
          quiz: () => QuizState(active: true, data: msg['data'] as Map<String, dynamic>? ?? {}),
        );

      case 'quiz_update':
        final current = state.quiz;
        if (current != null) {
          final update = msg['state'] is Map<String, dynamic>
              ? msg['state'] as Map<String, dynamic>
              : <String, dynamic>{};
          state = state.copyWith(
            quiz: () => QuizState(
              active: true,
              data: {...current.data, ...update},
            ),
          );
        }

      case 'quiz_close':
        state = state.copyWith(quiz: () => null);

      case 'story_mode':
        final data = msg['data'] as Map<String, dynamic>?;
        state = state.copyWith(
          story: () => data != null
              ? StoryState(active: data['active'] as bool? ?? false, data: data)
              : null,
        );

      case 'ambient':
        state = state.copyWith(ambient: () => AmbientState.fromJson(msg));

      case 'timers':
        final list = (msg['timers'] as List<dynamic>? ?? [])
            .map((e) => TimerInfo.fromJson(e as Map<String, dynamic>))
            .toList();
        state = state.copyWith(timers: list);

      case 'reminders_updated':
        final list = (msg['reminders'] as List<dynamic>? ?? [])
            .map((e) => ReminderInfo.fromJson(e as Map<String, dynamic>))
            .toList();
        state = state.copyWith(reminders: list);
    }
  }

  @override
  void dispose() {
    _statusSub?.cancel();
    _wsSub?.cancel();
    super.dispose();
  }
}
