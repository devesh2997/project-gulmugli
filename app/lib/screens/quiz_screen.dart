import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../state/providers.dart';

/// Quiz screen — interactive trivia game.
///
/// Start a quiz, answer questions by tapping options,
/// get hints, and see your score.
class QuizScreen extends ConsumerStatefulWidget {
  const QuizScreen({super.key});

  @override
  ConsumerState<QuizScreen> createState() => _QuizScreenState();
}

class _QuizScreenState extends ConsumerState<QuizScreen> {
  String _category = 'general';
  String _difficulty = 'medium';
  bool _starting = false;

  static const _categories = [
    'general',
    'bollywood',
    'music',
    'geography',
    'tech',
    'movies',
    'food',
    'cricket',
  ];

  void _startQuiz() {
    final api = ref.read(connectionManagerProvider).api;
    if (api == null) return;

    setState(() => _starting = true);
    api.quizStart(
      category: _category,
      difficulty: _difficulty,
    ).then((_) {
      if (mounted) setState(() => _starting = false);
    }).catchError((_) {
      if (mounted) setState(() => _starting = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    final quiz = ref.watch(assistantStateProvider).quiz;
    final api = ref.watch(connectionManagerProvider).api;
    final active = quiz?.active ?? false;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Quiz'),
        actions: [
          if (active)
            TextButton(
              onPressed: () => api?.quizQuit(),
              child: const Text('Quit'),
            ),
        ],
      ),
      body: active ? _ActiveQuiz(data: quiz!.data, api: api) : _QuizSetup(
        category: _category,
        difficulty: _difficulty,
        starting: _starting,
        onCategoryChanged: (v) => setState(() => _category = v),
        onDifficultyChanged: (v) => setState(() => _difficulty = v),
        onStart: _startQuiz,
      ),
    );
  }
}

class _QuizSetup extends StatelessWidget {
  final String category;
  final String difficulty;
  final bool starting;
  final ValueChanged<String> onCategoryChanged;
  final ValueChanged<String> onDifficultyChanged;
  final VoidCallback onStart;

  const _QuizSetup({
    required this.category,
    required this.difficulty,
    required this.starting,
    required this.onCategoryChanged,
    required this.onDifficultyChanged,
    required this.onStart,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.quiz, size: 64, color: Colors.white24),
            const SizedBox(height: 24),
            Text('Start a Quiz', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 32),

            // Category
            DropdownButtonFormField<String>(
              initialValue: category,
              decoration: const InputDecoration(labelText: 'Category'),
              items: _QuizScreenState._categories
                  .map((c) => DropdownMenuItem(
                        value: c,
                        child: Text(c[0].toUpperCase() + c.substring(1)),
                      ))
                  .toList(),
              onChanged: (v) => onCategoryChanged(v ?? 'general'),
            ),
            const SizedBox(height: 16),

            // Difficulty
            DropdownButtonFormField<String>(
              initialValue: difficulty,
              decoration: const InputDecoration(labelText: 'Difficulty'),
              items: ['easy', 'medium', 'hard']
                  .map((d) => DropdownMenuItem(
                        value: d,
                        child: Text(d[0].toUpperCase() + d.substring(1)),
                      ))
                  .toList(),
              onChanged: (v) => onDifficultyChanged(v ?? 'medium'),
            ),
            const SizedBox(height: 32),

            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: starting ? null : onStart,
                child: starting
                    ? const SizedBox(
                        width: 20, height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Start Quiz'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ActiveQuiz extends StatelessWidget {
  final Map<String, dynamic> data;
  final dynamic api;

  const _ActiveQuiz({required this.data, required this.api});

  @override
  Widget build(BuildContext context) {
    final question = data['question']?.toString() ?? data['text']?.toString() ?? '';
    final options = (data['options'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [];
    final questionNum = data['question_number'] ?? data['current'] ?? 0;
    final total = data['total'] ?? 10;
    final score = data['score'] ?? 0;
    final result = data['result']?.toString();
    final reaction = data['reaction']?.toString();

    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        // Progress
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('Question $questionNum / $total',
                style: const TextStyle(color: Colors.white54)),
            Text('Score: $score',
                style: const TextStyle(color: Colors.white54, fontWeight: FontWeight.w600)),
          ],
        ),
        const SizedBox(height: 8),
        LinearProgressIndicator(
          value: total > 0 ? questionNum / total : 0,
          backgroundColor: Colors.white12,
        ),
        const SizedBox(height: 24),

        // Result from last answer
        if (result != null) ...[
          Card(
            color: result == 'correct'
                ? Colors.green.withValues(alpha: 0.15)
                : Colors.red.withValues(alpha: 0.15),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  Icon(
                    result == 'correct' ? Icons.check_circle : Icons.cancel,
                    color: result == 'correct' ? Colors.green : Colors.red,
                    size: 32,
                  ),
                  if (reaction != null) ...[
                    const SizedBox(height: 8),
                    Text(reaction, textAlign: TextAlign.center,
                        style: const TextStyle(fontStyle: FontStyle.italic)),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
        ],

        // Question
        Text(
          question,
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 24),

        // Options
        ...options.map((option) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: SizedBox(
                width: double.infinity,
                child: OutlinedButton(
                  onPressed: () => api?.quizAnswer(option),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.all(16),
                    alignment: Alignment.centerLeft,
                  ),
                  child: Text(option),
                ),
              ),
            )),
        const SizedBox(height: 16),

        // Hint button
        Center(
          child: TextButton.icon(
            onPressed: () => api?.quizHint(),
            icon: const Icon(Icons.lightbulb_outline, size: 18),
            label: const Text('Hint'),
          ),
        ),
      ],
    );
  }
}
