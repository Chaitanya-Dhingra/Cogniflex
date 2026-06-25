import 'package:flutter/material.dart';
import 'dart:async';
import 'game_screen.dart';

/// Shows a countdown, then pushes GameScreen which opens the WebSocket.
/// The old HTTP /start-game call is replaced by the WS command sent from
/// GameScreen itself, so this file is now purely a countdown UI.
class CountdownScreen extends StatefulWidget {
  final String gameName;

  const CountdownScreen({super.key, required this.gameName});

  @override
  State<CountdownScreen> createState() => _CountdownScreenState();
}

class _CountdownScreenState extends State<CountdownScreen> {
  int _seconds = 3;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _startCountdown();
  }

  void _startCountdown() {
    _timer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (_seconds <= 1) {
        t.cancel();
        _launchGame();
      } else {
        setState(() => _seconds--);
      }
    });
  }

  void _launchGame() {
    if (!mounted) return;
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (_) => GameScreen(gameName: widget.gameName),
      ),
    );
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text(
              'Get Ready!',
              style: TextStyle(
                fontSize: 32,
                color: Colors.white,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              widget.gameName,
              style: const TextStyle(color: Colors.white54, fontSize: 18),
            ),
            const SizedBox(height: 48),
            Text(
              '$_seconds',
              style: const TextStyle(
                fontSize: 80,
                color: Colors.greenAccent,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ),
    );
  }
}