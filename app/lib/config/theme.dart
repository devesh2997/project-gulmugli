import 'dart:ui';

import 'package:flutter/material.dart';

/// Design system matching the JARVIS React dashboard.
///
/// Warm dark aesthetic, personality-driven accents, frosted glass surfaces.
/// Every value here is ported from the dashboard's CSS tokens and design spec.

// ═══════════════════════════════════════════════════════════════
// Personality accent colors
// ═══════════════════════════════════════════════════════════════

class PersonalityColors {
  static const Map<String, Color> accent = {
    'jarvis': Color(0xFFE8C070),     // warm gold
    'devesh': Color(0xFF5CD8B8),     // vivid teal
    'girlfriend': Color(0xFFF0A0A8), // soft pink-rose
    'chandler': Color(0xFFC8A8F0),   // bright lavender
  };

  static Color accentFor(String id) =>
      accent[id] ?? const Color(0xFFE8C070);

  static Color glowFor(String id) =>
      accentFor(id).withValues(alpha: 0.21);
}

// ═══════════════════════════════════════════════════════════════
// Core palette
// ═══════════════════════════════════════════════════════════════

class JarvisColors {
  // Canvas backgrounds
  static const canvasStart = Color(0xFF0E0E11);
  static const canvasEnd = Color(0xFF141218);
  static const canvasBase = Color(0xFF050505);

  // Text hierarchy
  static const textPrimary = Color(0xCCFFFFFF);   // 80%
  static const textSecondary = Color(0x66FFFFFF);  // 40%
  static const textTertiary = Color(0x33FFFFFF);   // 20%

  // Surfaces
  static const panelBg = Color(0xE0100E16);        // rgba(16, 14, 22, 0.88)
  static const cardBg = Color(0x0AFFFFFF);          // rgba(255,255,255, 0.04)
  static const pillBg = Color(0x0DFFFFFF);          // rgba(255,255,255, 0.05)
  static const borderSubtle = Color(0x14FFFFFF);    // rgba(255,255,255, 0.08)

  // Semantic
  static const success = Color(0xFF4ADE80);
  static const warning = Color(0xFFFACC15);
  static const error = Color(0xFFF87171);
}

// ═══════════════════════════════════════════════════════════════
// Theme
// ═══════════════════════════════════════════════════════════════

class JarvisTheme {
  static ThemeData get dark {
    return ThemeData(
      brightness: Brightness.dark,
      useMaterial3: true,
      fontFamily: 'Inter',
      scaffoldBackgroundColor: JarvisColors.canvasBase,
      colorScheme: ColorScheme.fromSeed(
        seedColor: const Color(0xFFE8C070),
        brightness: Brightness.dark,
        surface: JarvisColors.canvasStart,
      ),
      cardTheme: CardThemeData(
        color: JarvisColors.cardBg,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: const BorderSide(color: JarvisColors.borderSubtle),
        ),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        titleTextStyle: TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.12,
          color: JarvisColors.textPrimary,
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: JarvisColors.cardBg,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: JarvisColors.borderSubtle),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: JarvisColors.borderSubtle),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: JarvisColors.textSecondary),
        ),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        hintStyle: const TextStyle(color: JarvisColors.textTertiary),
        labelStyle: const TextStyle(color: JarvisColors.textSecondary),
      ),
      textTheme: const TextTheme(
        displayLarge: TextStyle(
          fontSize: 42, fontWeight: FontWeight.w200,
          letterSpacing: 0.02, fontFamily: 'JetBrains Mono',
          color: JarvisColors.textPrimary,
        ),
        headlineSmall: TextStyle(
          fontSize: 20, fontWeight: FontWeight.w600,
          color: JarvisColors.textPrimary,
        ),
        titleMedium: TextStyle(
          fontSize: 14, fontWeight: FontWeight.w600,
          letterSpacing: 0.02, color: JarvisColors.textPrimary,
        ),
        bodyMedium: TextStyle(
          fontSize: 14, fontWeight: FontWeight.w400,
          letterSpacing: 0.02, color: JarvisColors.textPrimary,
        ),
        bodySmall: TextStyle(
          fontSize: 12, fontWeight: FontWeight.w400,
          color: JarvisColors.textSecondary,
        ),
        labelSmall: TextStyle(
          fontSize: 11, fontWeight: FontWeight.w600,
          letterSpacing: 0.12, color: JarvisColors.textSecondary,
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
        ),
      ),
      sliderTheme: SliderThemeData(
        activeTrackColor: JarvisColors.textSecondary,
        inactiveTrackColor: JarvisColors.borderSubtle,
        thumbColor: JarvisColors.textPrimary,
        overlayColor: JarvisColors.textTertiary,
        trackHeight: 3,
        thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 6),
      ),
    );
  }
}

/// Frosted glass decoration used by panels, cards, overlays.
BoxDecoration frostedGlass({
  Color? tint,
  double borderRadius = 24,
  Color borderColor = JarvisColors.borderSubtle,
}) {
  return BoxDecoration(
    color: tint ?? JarvisColors.panelBg,
    borderRadius: BorderRadius.circular(borderRadius),
    border: Border.all(color: borderColor),
  );
}
