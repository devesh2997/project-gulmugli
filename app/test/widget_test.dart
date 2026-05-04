import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jarvis_companion/app.dart';

void main() {
  testWidgets('App renders the connect screen when not connected', (tester) async {
    await tester.pumpWidget(
      const ProviderScope(child: JarvisApp()),
    );
    // The connect screen has an animated breathing-orb pulse that loops
    // every 3 seconds, so `pumpAndSettle()` would time out waiting for
    // animations to stop. Pump a few frames to lay out the static text
    // and stop there.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    // Title text on the connect screen. Lower-case "Jarvis" — must match
    // the actual UI string (was capitalized in an earlier version of this
    // test and silently failing). If the connect screen copy ever changes,
    // update both.
    expect(find.text('Connect to Jarvis'), findsOneWidget);

    // The Server IP label is also reliably present and proves the form
    // rendered, not just the title.
    expect(find.text('Server IP'), findsOneWidget);
  });
}
