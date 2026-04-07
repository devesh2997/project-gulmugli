import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/assistant_state.dart';
import '../state/providers.dart';

/// Weather screen — current conditions and forecast.
class WeatherScreen extends ConsumerStatefulWidget {
  const WeatherScreen({super.key});

  @override
  ConsumerState<WeatherScreen> createState() => _WeatherScreenState();
}

class _WeatherScreenState extends ConsumerState<WeatherScreen> {
  bool _loading = false;
  Map<String, dynamic>? _forecast;

  @override
  void initState() {
    super.initState();
    _fetchWeather();
  }

  Future<void> _fetchWeather() async {
    setState(() => _loading = true);
    try {
      final api = ref.read(connectionManagerProvider).api;
      if (api != null) {
        _forecast = await api.weatherForecast();
      }
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    final weather = ref.watch(weatherProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Weather'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loading ? null : _fetchWeather,
          ),
        ],
      ),
      body: _loading && weather == null
          ? const Center(child: CircularProgressIndicator())
          : weather == null
              ? const Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.cloud_off, size: 64, color: Colors.white24),
                      SizedBox(height: 16),
                      Text('Weather data unavailable',
                          style: TextStyle(color: Colors.white38)),
                    ],
                  ),
                )
              : _WeatherView(weather: weather, forecast: _forecast),
    );
  }
}

class _WeatherView extends StatelessWidget {
  final WeatherData weather;
  final Map<String, dynamic>? forecast;

  const _WeatherView({required this.weather, this.forecast});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        // Current conditions
        Center(
          child: Column(
            children: [
              Icon(_weatherIcon(weather.condition), size: 80, color: Colors.white70),
              const SizedBox(height: 16),
              Text(
                '${weather.temperature.round()}°',
                style: Theme.of(context).textTheme.displayMedium?.copyWith(
                      fontWeight: FontWeight.w300,
                    ),
              ),
              Text(
                weather.description,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      color: Colors.white54,
                    ),
              ),
              const SizedBox(height: 8),
              Text(
                'Feels like ${weather.feelsLike.round()}°',
                style: const TextStyle(color: Colors.white38),
              ),
            ],
          ),
        ),
        const SizedBox(height: 32),

        // Details
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _DetailItem(icon: Icons.water_drop, label: 'Humidity', value: '${weather.humidity}%'),
                _DetailItem(icon: Icons.air, label: 'Wind', value: '${weather.windSpeed} km/h'),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),

        // Forecast
        if (forecast != null && forecast!['forecast'] is List) ...[
          Text('Forecast', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          ...(forecast!['forecast'] as List).map((day) {
            final d = day as Map<String, dynamic>;
            return Card(
              child: ListTile(
                leading: Icon(_weatherIcon(d['condition']?.toString() ?? ''), color: Colors.white54),
                title: Text(d['date']?.toString() ?? ''),
                subtitle: Text(d['description']?.toString() ?? ''),
                trailing: Text(
                  '${(d['temp_min'] as num?)?.round() ?? '?'}° / ${(d['temp_max'] as num?)?.round() ?? '?'}°',
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ),
            );
          }),
        ],
      ],
    );
  }

  IconData _weatherIcon(String condition) {
    switch (condition.toLowerCase()) {
      case 'sunny':
      case 'clear':
        return Icons.wb_sunny;
      case 'partly_cloudy':
        return Icons.cloud_queue;
      case 'cloudy':
        return Icons.cloud;
      case 'rain':
        return Icons.water_drop;
      case 'thunderstorm':
        return Icons.thunderstorm;
      case 'snow':
        return Icons.ac_unit;
      case 'fog':
        return Icons.foggy;
      case 'clear_night':
        return Icons.nightlight;
      default:
        return Icons.cloud;
    }
  }
}

class _DetailItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const _DetailItem({required this.icon, required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Icon(icon, color: Colors.white38, size: 24),
        const SizedBox(height: 4),
        Text(value, style: const TextStyle(fontWeight: FontWeight.w600)),
        Text(label, style: const TextStyle(color: Colors.white38, fontSize: 12)),
      ],
    );
  }
}
