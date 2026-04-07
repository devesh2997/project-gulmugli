import 'package:dio/dio.dart';

import '../config/constants.dart';

/// HTTP client for the JARVIS REST API.
///
/// Wraps [Dio] with the base URL, auth token, and timeouts.
/// All REST calls go through this client.
class ApiClient {
  late final Dio _dio;
  String? _token;

  ApiClient({required String baseUrl, String? token}) : _token = token {
    _dio = Dio(BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: kRestTimeout,
      receiveTimeout: kRestTimeout,
    ));

    // Add auth interceptor
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) {
        if (_token != null) {
          options.headers['Authorization'] = 'Bearer $_token';
        }
        return handler.next(options);
      },
    ));
  }

  void updateToken(String token) => _token = token;
  void updateBaseUrl(String baseUrl) => _dio.options.baseUrl = baseUrl;

  // ── System ──────────────────────────────────────────────

  /// Unauthenticated health check — used to verify server is reachable.
  Future<Map<String, dynamic>> healthCheck() async {
    final resp = await _dio.get('/api/status');
    return resp.data as Map<String, dynamic>;
  }

  /// Full system status (authenticated).
  Future<Map<String, dynamic>> systemStatus() async {
    final resp = await _dio.get('/api/system/status');
    return resp.data as Map<String, dynamic>;
  }

  // ── Music ───────────────────────────────────────────────

  Future<Map<String, dynamic>> musicPlay(String query, {bool withVideo = false}) async {
    final resp = await _dio.post(
      '/api/music/play',
      data: {'query': query, 'with_video': withVideo},
      options: Options(receiveTimeout: kLongRestTimeout),
    );
    return resp.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> musicControl(String action) async {
    final resp = await _dio.post('/api/music/control', data: {'action': action});
    return resp.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> nowPlaying() async {
    final resp = await _dio.get('/api/music/now-playing');
    return resp.data as Map<String, dynamic>;
  }

  Future<void> musicSeek(double position) async {
    await _dio.post('/api/music/seek', data: {'position': position});
  }

  // ── Lights ──────────────────────────────────────────────

  Future<Map<String, dynamic>> lightControl(String action, {String? value, String? device}) async {
    final data = <String, dynamic>{'action': action};
    if (value != null) data['value'] = value;
    if (device != null) data['device'] = device;
    final resp = await _dio.post('/api/lights/control', data: data);
    return resp.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> lightState() async {
    final resp = await _dio.get('/api/lights/state');
    return resp.data as Map<String, dynamic>;
  }

  Future<List<dynamic>> lightDevices() async {
    final resp = await _dio.get('/api/lights/devices');
    return resp.data as List<dynamic>;
  }

  // ── Volume ──────────────────────────────────────────────

  Future<void> setVolume(int level) async {
    await _dio.post('/api/volume', data: {'level': level});
  }

  Future<int> getVolume() async {
    final resp = await _dio.get('/api/volume');
    return (resp.data as Map<String, dynamic>)['level'] as int;
  }

  // ── Personality ─────────────────────────────────────────

  Future<Map<String, dynamic>> listPersonalities() async {
    final resp = await _dio.get('/api/personalities');
    return resp.data as Map<String, dynamic>;
  }

  Future<void> switchPersonality(String personality) async {
    await _dio.post('/api/personality/switch', data: {'personality': personality});
  }

  // ── Chat ────────────────────────────────────────────────

  Future<Map<String, dynamic>> chat(String text) async {
    final resp = await _dio.post(
      '/api/chat',
      data: {'text': text},
      options: Options(receiveTimeout: kLongRestTimeout),
    );
    return resp.data as Map<String, dynamic>;
  }

  // ── Quiz ────────────────────────────────────────────────

  Future<Map<String, dynamic>> quizStart({
    String category = 'general',
    String difficulty = 'medium',
    int numQuestions = 10,
  }) async {
    final resp = await _dio.post('/api/quiz/start', data: {
      'category': category,
      'difficulty': difficulty,
      'num_questions': numQuestions,
    });
    return resp.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> quizAnswer(String answer) async {
    final resp = await _dio.post('/api/quiz/answer', data: {'answer': answer});
    return resp.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> quizHint() async {
    final resp = await _dio.post('/api/quiz/hint');
    return resp.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> quizQuit() async {
    final resp = await _dio.post('/api/quiz/quit');
    return resp.data as Map<String, dynamic>;
  }

  // ── Weather ─────────────────────────────────────────────

  Future<Map<String, dynamic>> weatherCurrent() async {
    final resp = await _dio.get('/api/weather/current');
    return resp.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> weatherForecast() async {
    final resp = await _dio.get('/api/weather/forecast');
    return resp.data as Map<String, dynamic>;
  }

  // ── Memory ──────────────────────────────────────────────

  Future<Map<String, dynamic>> memoryRecall(String query) async {
    final resp = await _dio.get('/api/memory/recall', queryParameters: {'q': query});
    return resp.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> memoryStats() async {
    final resp = await _dio.get('/api/memory/stats');
    return resp.data as Map<String, dynamic>;
  }

  // ── Story / Ambient ─────────────────────────────────────

  Future<Map<String, dynamic>> story(String action, {String? genre, String? topic}) async {
    final data = <String, dynamic>{'action': action};
    if (genre != null) data['genre'] = genre;
    if (topic != null) data['topic'] = topic;
    final resp = await _dio.post('/api/story', data: data);
    return resp.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> ambient(String action, {String? sound, int? volume}) async {
    final data = <String, dynamic>{'action': action};
    if (sound != null) data['sound'] = sound;
    if (volume != null) data['volume'] = volume;
    final resp = await _dio.post('/api/ambient', data: data);
    return resp.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> ambientSounds() async {
    final resp = await _dio.get('/api/ambient/sounds');
    return resp.data as Map<String, dynamic>;
  }

  // ── Settings ────────────────────────────────────────────

  Future<List<dynamic>> getSettings() async {
    final resp = await _dio.get('/api/settings');
    return resp.data as List<dynamic>;
  }

  Future<Map<String, dynamic>> updateSetting(String path, dynamic value) async {
    final resp = await _dio.post('/api/settings', data: {'path': path, 'value': value});
    return resp.data as Map<String, dynamic>;
  }
}
