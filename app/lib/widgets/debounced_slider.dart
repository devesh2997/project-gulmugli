import 'dart:async';

import 'package:flutter/material.dart';

/// A Material [Slider] that doesn't spam its `onChanged` callback while
/// the user is dragging.
///
/// Why this exists:
///   The default [Slider] fires `onChanged` on every drag tick (~60 Hz).
///   When the callback talks to a network device — Tuya bulbs, the
///   JARVIS volume API, etc. — that's 30-60 redundant requests per
///   second of drag. The Tuya broker rate-limits or queues badly under
///   that load; the network has retransmits; the UI lags as the device
///   tries to apply each intermediate value.
///
/// What this widget does:
///   - Tracks the drag visually via local state, no network calls
///   - On `onChangeEnd` (release), fires `onCommit(finalValue)` once
///   - Optional `intermediateInterval`: if you want the device to
///     update _while_ dragging (for smoother feedback), it'll fire
///     `onCommit` at most once per `intermediateInterval` while the
///     drag is in progress. Default null (only fires on release).
///   - Falls back to firing `onCommit(externalValue)` on prop change,
///     so external state updates (WS broadcast says brightness=70)
///     correctly reflect on the slider while NOT in mid-drag.
///
/// Drop-in replacement for [Slider] when the parent passed
/// `onChanged: (v) => api.foo(v)` and wants debounce.
class DebouncedSlider extends StatefulWidget {
  final double value;
  final double min;
  final double max;
  final int? divisions;
  final ValueChanged<double> onCommit;

  /// Optional formatter for the slider's label. If null, label is hidden.
  final String Function(double)? labelFormat;

  /// Optional throttle for committing intermediate values during drag.
  /// e.g. `Duration(milliseconds: 250)` will fire `onCommit` at most
  /// 4× per second while the user keeps dragging. Default: null
  /// (commit only on release).
  final Duration? intermediateInterval;

  const DebouncedSlider({
    super.key,
    required this.value,
    required this.onCommit,
    this.min = 0,
    this.max = 100,
    this.divisions,
    this.labelFormat,
    this.intermediateInterval,
  });

  @override
  State<DebouncedSlider> createState() => DebouncedSliderState();
}

class DebouncedSliderState extends State<DebouncedSlider> {
  double? _localValue;
  Timer? _intermediateTimer;
  bool _dragging = false;

  /// The value to render: while dragging, the user's draft; otherwise,
  /// the parent-supplied truth. This lets external state updates
  /// (server says "brightness now 70") propagate when the user isn't
  /// actively touching the slider.
  double get _displayValue => _dragging ? _localValue! : widget.value;

  @override
  void didUpdateWidget(DebouncedSlider oldWidget) {
    super.didUpdateWidget(oldWidget);
    // If we're not dragging, keep our local copy in sync so when the
    // user next touches it, the starting position matches reality.
    if (!_dragging) {
      _localValue = widget.value;
    }
  }

  @override
  void dispose() {
    _intermediateTimer?.cancel();
    super.dispose();
  }

  void _handleChanged(double v) {
    setState(() {
      _localValue = v;
      _dragging = true;
    });
    if (widget.intermediateInterval != null) {
      _intermediateTimer ??= Timer(widget.intermediateInterval!, () {
        _intermediateTimer = null;
        if (_dragging && _localValue != null) {
          widget.onCommit(_localValue!);
        }
      });
    }
  }

  void _handleEnd(double v) {
    _intermediateTimer?.cancel();
    _intermediateTimer = null;
    setState(() {
      _localValue = v;
      _dragging = false;
    });
    widget.onCommit(v);
  }

  @override
  Widget build(BuildContext context) {
    return Slider(
      value: _displayValue.clamp(widget.min, widget.max),
      min: widget.min,
      max: widget.max,
      divisions: widget.divisions,
      label: widget.labelFormat?.call(_displayValue),
      onChanged: _handleChanged,
      onChangeEnd: _handleEnd,
    );
  }
}

