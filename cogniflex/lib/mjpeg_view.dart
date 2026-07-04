import 'dart:async';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

class MjpegView extends StatefulWidget {
  final String streamUrl;
  const MjpegView({super.key, required this.streamUrl});

  @override
  State<MjpegView> createState() => _MjpegViewState();
}

class _MjpegViewState extends State<MjpegView> {
  Uint8List? _currentFrame;
  StreamSubscription<List<int>>? _sub;
  http.Client? _client;
  final List<int> _buffer = [];

  @override
  void initState() {
    super.initState();
    _connect();
  }

  void _connect() async {
    _client = http.Client();
    try {
      final request = http.Request('GET', Uri.parse(widget.streamUrl));
      final response = await _client!.send(request);
      _sub = response.stream.listen(_onData,
          onError: (_) => _scheduleReconnect(),
          onDone: _scheduleReconnect,
          cancelOnError: true);
    } catch (_) {
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    _sub?.cancel();
    _client?.close();
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) _connect();
    });
  }

  void _onData(List<int> chunk) {
    _buffer.addAll(chunk);
    while (true) {
      final start = _findMarker(_buffer, 0xFF, 0xD8);
      if (start == -1) {
        if (_buffer.length > 500000) _buffer.clear();
        break;
      }
      final end = _findMarker(_buffer, 0xFF, 0xD9, start + 2);
      if (end == -1) break;
      final frameBytes = Uint8List.fromList(_buffer.sublist(start, end + 2));
      _buffer.removeRange(0, end + 2);
      if (mounted) setState(() => _currentFrame = frameBytes);
    }
  }

  int _findMarker(List<int> data, int b1, int b2, [int from = 0]) {
    for (var i = from; i < data.length - 1; i++) {
      if (data[i] == b1 && data[i + 1] == b2) return i;
    }
    return -1;
  }

  @override
  void dispose() {
    _sub?.cancel();
    _client?.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_currentFrame == null) {
      return const Center(
          child: Text('Connecting to camera…',
              style: TextStyle(color: Colors.white38)));
    }
    return Image.memory(_currentFrame!, gaplessPlayback: true, fit: BoxFit.cover);
  }
}