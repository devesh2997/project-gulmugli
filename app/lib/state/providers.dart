import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/assistant_state.dart';
import '../services/connection_manager.dart';
import 'assistant_notifier.dart';

/// Global connection manager — singleton across the app.
final connectionManagerProvider = Provider<ConnectionManager>((ref) {
  final manager = ConnectionManager();
  ref.onDispose(() => manager.dispose());
  return manager;
});

/// Connection status stream.
final connectionStatusProvider = StreamProvider<ConnectionStatus>((ref) {
  return ref.watch(connectionManagerProvider).statusStream;
});

/// The core assistant state — driven by WebSocket messages.
final assistantStateProvider =
    StateNotifierProvider<AssistantNotifier, AssistantState>((ref) {
  final manager = ref.watch(connectionManagerProvider);
  return AssistantNotifier(manager);
});

// ── Derived providers (select slices of state) ──────────────

final assistantActivityProvider = Provider<String>((ref) {
  return ref.watch(assistantStateProvider).state;
});

final nowPlayingProvider = Provider<NowPlaying?>((ref) {
  return ref.watch(assistantStateProvider).nowPlaying;
});

final lightsProvider = Provider<LightsState?>((ref) {
  return ref.watch(assistantStateProvider).lights;
});

final personalityProvider = Provider<String>((ref) {
  return ref.watch(assistantStateProvider).personalityId;
});

final personalitiesProvider = Provider<List<PersonalityInfo>>((ref) {
  return ref.watch(assistantStateProvider).personalities;
});

final volumeProvider = Provider<int>((ref) {
  return ref.watch(assistantStateProvider).volume;
});

final transcriptProvider = Provider<List<TranscriptEntry>>((ref) {
  return ref.watch(assistantStateProvider).transcript;
});

final sleepModeProvider = Provider<bool>((ref) {
  return ref.watch(assistantStateProvider).sleepMode;
});

final timersProvider = Provider<List<TimerInfo>>((ref) {
  return ref.watch(assistantStateProvider).timers;
});

final remindersProvider = Provider<List<ReminderInfo>>((ref) {
  return ref.watch(assistantStateProvider).reminders;
});

final weatherProvider = Provider<WeatherData?>((ref) {
  return ref.watch(assistantStateProvider).weather;
});
