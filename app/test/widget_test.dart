import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:jarvis_companion/app.dart';

void main() {
  testWidgets('App renders connect screen when not connected', (tester) async {
    await tester.pumpWidget(
      const ProviderScope(child: JarvisApp()),
    );
    await tester.pumpAndSettle();
    expect(find.text('Connect to JARVIS'), findsOneWidget);
  });
}
