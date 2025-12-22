import 'package:flutter/foundation.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class AuthProvider extends ChangeNotifier {
  final FlutterSecureStorage _storage;
  final GoogleSignIn _googleSignIn = GoogleSignIn(
    scopes: ['email', 'profile'],
  );

  GoogleSignInAccount? _currentUser;
  bool _isAuthenticated = false;
  bool _isLoading = true;
  String? _errorMessage;

  AuthProvider(this._storage) {
    _checkSavedAuth();
  }

  // Getters
  GoogleSignInAccount? get currentUser => _currentUser;
  bool get isAuthenticated => _isAuthenticated;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  
  String? get userEmail => _currentUser?.email;
  String? get userName => _currentUser?.displayName;
  String? get userPhotoUrl => _currentUser?.photoUrl;

  // Check if user was previously signed in
  Future<void> _checkSavedAuth() async {
    _isLoading = true;
    notifyListeners();

    try {
      final savedEmail = await _storage.read(key: 'user_email');
      
      if (savedEmail != null) {
        // Try silent sign-in
        _currentUser = await _googleSignIn.signInSilently();
        if (_currentUser != null && _currentUser!.email == savedEmail) {
          _isAuthenticated = true;
          debugPrint('✅ Auto signed in: ${_currentUser!.email}');
        }
      }
    } catch (e) {
      debugPrint('❌ Auto sign-in failed: $e');
    }

    _isLoading = false;
    notifyListeners();
  }

  // Sign in with Google
  Future<bool> signInWithGoogle() async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      debugPrint('🔄 Starting Google Sign-In...');
      
      final GoogleSignInAccount? account = await _googleSignIn.signIn();
      
      if (account == null) {
        _errorMessage = 'Sign in cancelled';
        _isLoading = false;
        notifyListeners();
        return false;
      }

      debugPrint('📧 Signed in: ${account.email}');

      // Check if it's a UMass email
      if (!account.email.endsWith('@umass.edu')) {
        _errorMessage = '⚠️ Please use your @umass.edu email';
        await _googleSignIn.signOut();
        _isLoading = false;
        notifyListeners();
        return false;
      }

      // Success!
      _currentUser = account;
      _isAuthenticated = true;
      
      // Save email for next time
      await _storage.write(key: 'user_email', value: account.email);
      
      debugPrint('✅ Authentication successful!');
      
      _isLoading = false;
      notifyListeners();
      return true;

    } catch (e) {
      _errorMessage = 'Sign in failed: ${e.toString()}';
      debugPrint('❌ Sign in error: $e');
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  // Sign out
  Future<void> signOut() async {
    _isLoading = true;
    notifyListeners();

    try {
      await _googleSignIn.signOut();
      await _storage.delete(key: 'user_email');
      
      _currentUser = null;
      _isAuthenticated = false;
      _errorMessage = null;
      
      debugPrint('👋 Signed out');
    } catch (e) {
      debugPrint('❌ Sign out error: $e');
    }

    _isLoading = false;
    notifyListeners();
  }

  // Clear error
  void clearError() {
    _errorMessage = null;
    notifyListeners();
  }
}