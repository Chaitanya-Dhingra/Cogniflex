import 'package:flutter/material.dart';
import 'countdown_screen.dart';

class GameInfoScreen extends StatelessWidget {
  final String gameName;

  const GameInfoScreen({super.key, required this.gameName});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(gameName),
        backgroundColor: const Color.fromARGB(255, 20, 193, 241),
      ),
      body: Padding(
        padding: EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              "Objective",
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            SizedBox(height: 10),
            Text(
              "Improve hand coordination and reaction speed.",
              style: TextStyle(fontSize: 16),
            ),
            Spacer(),
            SizedBox(
              width: double.infinity,
              height: 50,
              child: ElevatedButton(
                onPressed: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (context) =>
                      CountdownScreen(gameName: gameName),
                      ),
                      );
                      },
                child: Text("START"),
              ),
            ),
          ],
        ),
      ),
    );
  }
}