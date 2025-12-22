import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'auth_provider.dart';
import 'submit_event_page.dart';
import 'event_detail_page.dart';

// Event Model
class Event {
  final int id;
  final String title;
  final String club;
  final DateTime dateTime;
  final String location;
  final String foodType;
  final String emoji;
  final String? conditions;
  final bool isVerified;
  final String submittedBy;

  Event({
    required this.id,
    required this.title,
    required this.club,
    required this.dateTime,
    required this.location,
    required this.foodType,
    required this.emoji,
    this.conditions,
    required this.isVerified,
    required this.submittedBy,
  });

  String get formattedTime {
    final now = DateTime.now();
    final difference = dateTime.difference(now);

    if (difference.inDays == 0) {
      return 'Today at ${_formatTime(dateTime)}';
    } else if (difference.inDays == 1) {
      return 'Tomorrow at ${_formatTime(dateTime)}';
    } else if (difference.inDays < 7) {
      return '${_getDayName(dateTime)} at ${_formatTime(dateTime)}';
    } else {
      return '${dateTime.month}/${dateTime.day} at ${_formatTime(dateTime)}';
    }
  }

  String _formatTime(DateTime date) {
    final hour = date.hour > 12 ? date.hour - 12 : (date.hour == 0 ? 12 : date.hour);
    final minute = date.minute.toString().padLeft(2, '0');
    final period = date.hour >= 12 ? 'PM' : 'AM';
    return '$hour:$minute $period';
  }

  String _getDayName(DateTime date) {
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    return days[date.weekday - 1];
  }
}

class HomePage extends StatefulWidget {
  const HomePage({Key? key}) : super(key: key);

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  bool _isLoading = false;
  List<Event> _verifiedEvents = [];
  List<Event> _myPendingEvents = [];

  @override
  void initState() {
    super.initState();
    _loadEvents();
  }

  Future<void> _loadEvents() async {
    setState(() => _isLoading = true);

    // TODO: Replace with actual API call
    // Simulate API delay
    await Future.delayed(const Duration(seconds: 1));

    // Mock data - Replace with actual API call
    final auth = Provider.of<AuthProvider>(context, listen: false);
    final userEmail = auth.userEmail ?? '';

    setState(() {
      // Verified events (show to everyone)
      _verifiedEvents = [
        Event(
          id: 1,
          title: 'CS Club Meeting',
          club: 'Computer Science Club',
          dateTime: DateTime.now().add(const Duration(hours: 3)),
          location: 'CS Building Room 142',
          foodType: 'Pizza & Drinks',
          emoji: '🍕',
          isVerified: true,
          submittedBy: 'cs-club@umass.edu',
        ),
        Event(
          id: 2,
          title: 'Engineering Social',
          club: 'Engineering Society',
          dateTime: DateTime.now().add(const Duration(days: 1, hours: 2)),
          location: 'Student Union',
          foodType: 'Tacos & Snacks',
          emoji: '🌮',
          conditions: 'First 50 students',
          isVerified: true,
          submittedBy: 'eng-society@umass.edu',
        ),
        Event(
          id: 3,
          title: 'Math Department Seminar',
          club: 'Math Department',
          dateTime: DateTime.now().add(const Duration(days: 2)),
          location: 'LGRT 1634',
          foodType: 'Coffee & Cookies',
          emoji: '🍪',
          isVerified: true,
          submittedBy: 'math-dept@umass.edu',
        ),
      ];

      // My pending events (only show to submitter)
      _myPendingEvents = [
        Event(
          id: 100,
          title: 'Study Group Session',
          club: 'Personal',
          dateTime: DateTime.now().add(const Duration(hours: 5)),
          location: 'Library 3rd Floor',
          foodType: 'Snacks',
          emoji: '🍿',
          isVerified: false,
          submittedBy: userEmail,
        ),
      ];

      _isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final auth = Provider.of<AuthProvider>(context);

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: const [
            Text('🍕'),
            SizedBox(width: 8),
            Text('Free Food Tracker'),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadEvents,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _loadEvents,
        child: _isLoading
            ? const Center(child: CircularProgressIndicator())
            : SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Welcome Banner
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(20),
                      decoration: const BoxDecoration(
                        gradient: LinearGradient(
                          colors: [
                            Color(0xFF881C1C),
                            Color(0xFF5C1010),
                          ],
                        ),
                      ),
                      child: SafeArea(
                        top: false,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                if (auth.userPhotoUrl != null)
                                  CircleAvatar(
                                    backgroundImage: NetworkImage(auth.userPhotoUrl!),
                                    radius: 25,
                                  )
                                else
                                  const CircleAvatar(
                                    child: Icon(Icons.person),
                                    radius: 25,
                                  ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        'Welcome back!',
                                        style: TextStyle(
                                          color: Colors.white.withOpacity(0.9),
                                          fontSize: 14,
                                        ),
                                      ),
                                      Text(
                                        auth.userName ?? 'Student',
                                        style: const TextStyle(
                                          color: Colors.white,
                                          fontSize: 18,
                                          fontWeight: FontWeight.bold,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ),

                    // Quick Stats
                    Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: Row(
                        children: [
                          Expanded(
                            child: _buildStatCard(
                              icon: Icons.restaurant,
                              label: 'Verified Events',
                              value: '${_verifiedEvents.length}',
                              color: Colors.orange,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: _buildStatCard(
                              icon: Icons.pending,
                              label: 'My Pending',
                              value: '${_myPendingEvents.length}',
                              color: Colors.blue,
                            ),
                          ),
                        ],
                      ),
                    ),

                    // My Pending Events (only visible to submitter)
                    if (_myPendingEvents.isNotEmpty) ...[
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16.0),
                        child: Row(
                          children: [
                            const Icon(Icons.pending_actions, size: 20),
                            const SizedBox(width: 8),
                            const Text(
                              'My Pending Events',
                              style: TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: Colors.orange[100],
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: const Text(
                                'Awaiting Approval',
                                style: TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.bold,
                                  color: Colors.orange,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 12),
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16.0),
                        child: Column(
                          children: _myPendingEvents
                              .map((event) => Padding(
                                    padding: const EdgeInsets.only(bottom: 12),
                                    child: _buildEventCard(event, isPending: true),
                                  ))
                              .toList(),
                        ),
                      ),
                      const SizedBox(height: 8),
                    ],

                    // Verified Events Section
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16.0),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Row(
                            children: const [
                              Icon(Icons.verified, color: Color(0xFF881C1C), size: 20),
                              SizedBox(width: 8),
                              Text(
                                'Verified Events',
                                style: TextStyle(
                                  fontSize: 20,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                          TextButton(
                            onPressed: () {
                              // TODO: View all
                            },
                            child: const Text('View All'),
                          ),
                        ],
                      ),
                    ),

                    // Verified Event List
                    if (_verifiedEvents.isEmpty)
                      Padding(
                        padding: const EdgeInsets.all(40.0),
                        child: Center(
                          child: Column(
                            children: [
                              const Text(
                                '😔',
                                style: TextStyle(fontSize: 48),
                              ),
                              const SizedBox(height: 16),
                              Text(
                                'No verified events yet',
                                style: TextStyle(
                                  fontSize: 16,
                                  color: Colors.grey[600],
                                ),
                              ),
                            ],
                          ),
                        ),
                      )
                    else
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16.0),
                        child: Column(
                          children: _verifiedEvents
                              .map((event) => Padding(
                                    padding: const EdgeInsets.only(bottom: 12),
                                    child: _buildEventCard(event),
                                  ))
                              .toList(),
                        ),
                      ),
                    const SizedBox(height: 20),
                  ],
                ),
              ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          final result = await Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const SubmitEventPage()),
          );
          if (result == true) {
            _loadEvents(); // Reload events after submission
          }
        },
        backgroundColor: const Color(0xFF881C1C),
        icon: const Icon(Icons.add),
        label: const Text('Submit Event'),
      ),
    );
  }

  Widget _buildStatCard({
    required IconData icon,
    required String label,
    required String value,
    required Color color,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 32),
          const SizedBox(height: 8),
          Text(
            value,
            style: TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
          Text(
            label,
            style: TextStyle(
              fontSize: 12,
              color: Colors.grey[700],
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildEventCard(Event event, {bool isPending = false}) {
    return GestureDetector(
      onTap: () {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => EventDetailPage(event: event),
          ),
        );
      },
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isPending ? Colors.orange : Colors.grey[300]!,
            width: isPending ? 2 : 1,
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.grey.withOpacity(0.1),
              blurRadius: 4,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Row(
          children: [
            Text(event.emoji, style: const TextStyle(fontSize: 40)),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          event.title,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                      if (event.isVerified)
                        const Icon(
                          Icons.verified,
                          size: 16,
                          color: Color(0xFF881C1C),
                        ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    event.club,
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey[600],
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Icon(Icons.access_time, size: 14, color: Colors.grey[600]),
                      const SizedBox(width: 4),
                      Text(
                        event.formattedTime,
                        style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                      ),
                    ],
                  ),
                  const SizedBox(height: 2),
                  Row(
                    children: [
                      Icon(Icons.location_on, size: 14, color: Colors.grey[600]),
                      const SizedBox(width: 4),
                      Expanded(
                        child: Text(
                          event.location,
                          style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: const Color(0xFFFFF8E7),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: const Color(0xFFFFC72C)),
                        ),
                        child: Text(
                          event.foodType,
                          style: const TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                            color: Color(0xFF881C1C),
                          ),
                        ),
                      ),
                      if (event.conditions != null) ...[
                        const SizedBox(width: 8),
                        const Icon(Icons.info_outline, size: 14, color: Colors.orange),
                      ],
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}