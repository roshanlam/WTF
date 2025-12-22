import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'auth_provider.dart';
import 'login_screen.dart';
import 'home_screen.dart';

void main() {
  runApp(const FreeFoodTracker());
}

class FreeFoodTracker extends StatelessWidget {
  const FreeFoodTracker({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => AuthProvider(const FlutterSecureStorage()),
      child: MaterialApp(
        title: 'Free Food Tracker',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          primaryColor: const Color(0xFF881C1C), // UMass Maroon
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF881C1C),
          ),
          appBarTheme: const AppBarTheme(
            backgroundColor: Color(0xFF881C1C),
            foregroundColor: Colors.white,
          ),
        ),
        home: const AuthChecker(),
      ),
    );
  }
}

// Simple widget to check auth state
class AuthChecker extends StatelessWidget {
  const AuthChecker({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Consumer<AuthProvider>(
      builder: (context, auth, child) {
        // Show loading while checking auth
        if (auth.isLoading) {
          return const Scaffold(
            body: Center(
              child: CircularProgressIndicator(),
            ),
          );
        }
        
        // Show home if authenticated, otherwise show login
        if (auth.isAuthenticated) {
          return const HomeScreen();
        } else {
          return const LoginScreen();
        }
      },
    );
  }
}