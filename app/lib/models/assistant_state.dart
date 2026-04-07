/// Typed state models for the assistant — mirrors the WebSocket protocol.
///
/// These are the Dart equivalents of the TypeScript types in
/// dashboard/src/types/assistant.ts and the Pydantic schemas in
/// api/schemas.py.
library;

/// Overall assistant state — updated from WebSocket messages.
class AssistantState {
  final String state; // idle, listening, thinking, speaking, sleeping
  final String personalityId;
  final int volume;
  final bool sleepMode;
  final NowPlaying? nowPlaying;
  final LightsState? lights;
  final List<PersonalityInfo> personalities;
  final List<TranscriptEntry> transcript;
  final WeatherData? weather;
  final QuizState? quiz;
  final StoryState? story;
  final AmbientState? ambient;
  final List<TimerInfo> timers;
  final List<ReminderInfo> reminders;

  const AssistantState({
    this.state = 'idle',
    this.personalityId = 'jarvis',
    this.volume = 50,
    this.sleepMode = false,
    this.nowPlaying,
    this.lights,
    this.personalities = const [],
    this.transcript = const [],
    this.weather,
    this.quiz,
    this.story,
    this.ambient,
    this.timers = const [],
    this.reminders = const [],
  });

  AssistantState copyWith({
    String? state,
    String? personalityId,
    int? volume,
    bool? sleepMode,
    NowPlaying? Function()? nowPlaying,
    LightsState? Function()? lights,
    List<PersonalityInfo>? personalities,
    List<TranscriptEntry>? transcript,
    WeatherData? Function()? weather,
    QuizState? Function()? quiz,
    StoryState? Function()? story,
    AmbientState? Function()? ambient,
    List<TimerInfo>? timers,
    List<ReminderInfo>? reminders,
  }) {
    return AssistantState(
      state: state ?? this.state,
      personalityId: personalityId ?? this.personalityId,
      volume: volume ?? this.volume,
      sleepMode: sleepMode ?? this.sleepMode,
      nowPlaying: nowPlaying != null ? nowPlaying() : this.nowPlaying,
      lights: lights != null ? lights() : this.lights,
      personalities: personalities ?? this.personalities,
      transcript: transcript ?? this.transcript,
      weather: weather != null ? weather() : this.weather,
      quiz: quiz != null ? quiz() : this.quiz,
      story: story != null ? story() : this.story,
      ambient: ambient != null ? ambient() : this.ambient,
      timers: timers ?? this.timers,
      reminders: reminders ?? this.reminders,
    );
  }
}

class NowPlaying {
  final String title;
  final String artist;
  final String? album;
  final String? artUrl;
  final String? videoId;
  final double? duration;
  final double? position;
  final bool paused;

  const NowPlaying({
    required this.title,
    required this.artist,
    this.album,
    this.artUrl,
    this.videoId,
    this.duration,
    this.position,
    this.paused = false,
  });

  factory NowPlaying.fromJson(Map<String, dynamic> json) {
    final data = json['data'] as Map<String, dynamic>? ?? json;
    return NowPlaying(
      title: data['title']?.toString() ?? '',
      artist: data['artist']?.toString() ?? '',
      album: data['album']?.toString(),
      artUrl: data['art_url']?.toString(),
      videoId: data['video_id']?.toString(),
      duration: (data['duration'] as num?)?.toDouble(),
      position: (data['position'] as num?)?.toDouble(),
      paused: json['paused'] as bool? ?? false,
    );
  }
}

class LightsState {
  final bool on;
  final String color;
  final int brightness;
  final String? scene;

  const LightsState({
    this.on = false,
    this.color = '#ffffff',
    this.brightness = 100,
    this.scene,
  });

  factory LightsState.fromJson(Map<String, dynamic> json) => LightsState(
        on: json['on'] as bool? ?? false,
        color: json['color']?.toString() ?? '#ffffff',
        brightness: json['brightness'] as int? ?? 100,
        scene: json['scene']?.toString(),
      );
}

class PersonalityInfo {
  final String id;
  final String displayName;
  final String description;
  final String avatarType;

  const PersonalityInfo({
    required this.id,
    required this.displayName,
    this.description = '',
    this.avatarType = 'orb',
  });

  factory PersonalityInfo.fromJson(Map<String, dynamic> json) =>
      PersonalityInfo(
        id: json['id']?.toString() ?? '',
        displayName: json['display_name']?.toString() ?? '',
        description: json['description']?.toString() ?? '',
        avatarType: json['avatar_type']?.toString() ?? 'orb',
      );
}

class TranscriptEntry {
  final String text;
  final String role; // user, assistant
  final DateTime timestamp;

  const TranscriptEntry({
    required this.text,
    required this.role,
    required this.timestamp,
  });
}

class WeatherData {
  final double temperature;
  final double feelsLike;
  final int humidity;
  final double windSpeed;
  final String condition;
  final String description;

  const WeatherData({
    required this.temperature,
    required this.feelsLike,
    required this.humidity,
    required this.windSpeed,
    required this.condition,
    required this.description,
  });

  factory WeatherData.fromJson(Map<String, dynamic> json) => WeatherData(
        temperature: (json['temperature'] as num?)?.toDouble() ?? 0,
        feelsLike: (json['feels_like'] as num?)?.toDouble() ?? 0,
        humidity: json['humidity'] as int? ?? 0,
        windSpeed: (json['wind_speed'] as num?)?.toDouble() ?? 0,
        condition: json['condition']?.toString() ?? '',
        description: json['description']?.toString() ?? '',
      );
}

class QuizState {
  final bool active;
  final Map<String, dynamic> data;

  const QuizState({this.active = false, this.data = const {}});
}

class StoryState {
  final bool active;
  final Map<String, dynamic> data;

  const StoryState({this.active = false, this.data = const {}});
}

class AmbientState {
  final bool active;
  final String? sound;
  final int volume;

  const AmbientState({this.active = false, this.sound, this.volume = 30});

  factory AmbientState.fromJson(Map<String, dynamic> json) => AmbientState(
        active: json['active'] as bool? ?? false,
        sound: json['sound']?.toString(),
        volume: json['volume'] as int? ?? 30,
      );
}

class TimerInfo {
  final String id;
  final String label;
  final String type; // timer, alarm
  final int remainingSeconds;

  const TimerInfo({
    required this.id,
    required this.label,
    required this.type,
    required this.remainingSeconds,
  });

  factory TimerInfo.fromJson(Map<String, dynamic> json) => TimerInfo(
        id: json['id']?.toString() ?? '',
        label: json['label']?.toString() ?? '',
        type: json['type']?.toString() ?? 'timer',
        remainingSeconds: json['remaining_seconds'] as int? ?? 0,
      );
}

class ReminderInfo {
  final String id;
  final String text;
  final String? remindAt;

  const ReminderInfo({
    required this.id,
    required this.text,
    this.remindAt,
  });

  factory ReminderInfo.fromJson(Map<String, dynamic> json) => ReminderInfo(
        id: json['id']?.toString() ?? '',
        text: json['text']?.toString() ?? '',
        remindAt: json['remind_at']?.toString(),
      );
}
