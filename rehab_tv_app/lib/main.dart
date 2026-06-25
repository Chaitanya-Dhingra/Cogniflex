import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

void main() {
  runApp(const RehabApp());
}

class RehabApp extends StatelessWidget {
  const RehabApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Rehab Games',
      theme: ThemeData.dark(),
      home: const LoginPage(),
    );
  }
}

class LoginPage extends StatelessWidget {
  const LoginPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Login")),
      body: Center(
        child: ElevatedButton(
          child: const Text("Login"),
          onPressed: () {
            Navigator.push(
              context,
              MaterialPageRoute(builder: (context) => const GameMenu()),
            );
          },
        ),
      ),
    );
  }
}

class GameMenu extends StatelessWidget {
  const GameMenu({super.key});

  Future<void> startGame(String name) async {
  final url = Uri.parse("http://10.0.2.2:8000/start-game?name=$name");

  print("Sending request to: $url");

  try {
    final response = await http.get(url);

    print("Status: ${response.statusCode}");
    print("Body: ${response.body}");

  } catch (e) {
    print("Network error: $e");
  }
}

  Widget gameButton(String title) {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: ElevatedButton(
        style: ElevatedButton.styleFrom(
          minimumSize: const Size(300, 80),
        ),
        onPressed: () {
          startGame(title);
        },
        child: Text(title, style: const TextStyle(fontSize: 24)),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Rehabilitation Games")),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            gameButton("Apple"),
            gameButton("Puzzle"),
            gameButton("Rock"),
            gameButton("Wall"),
          ],
        ),
      ),
    );
  }
}