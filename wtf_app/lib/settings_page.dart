import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'auth_provider.dart';
import 'package:add_2_calendar/add_2_calendar.dart';
import 'package:permission_handler/permission_handler.dart';

class SettingsPage extends StatelessWidget {
  const SettingsPage({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final auth = Provider.of<AuthProvider>(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
      ),
      body: ListView(
        children: [
          // Profile Section
          Container(
            padding: const EdgeInsets.all(20),
            child: Column(
              children: [
                if (auth.userPhotoUrl != null)
                  CircleAvatar(
                    backgroundImage: NetworkImage(auth.userPhotoUrl!),
                    radius: 40,
                  )
                else
                  const CircleAvatar(
                    child: Icon(Icons.person, size: 40),
                    radius: 40,
                  ),
                const SizedBox(height: 12),
                Text(
                  auth.userName ?? 'Student',
                  style: const TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                Text(
                  auth.userEmail ?? '',
                  style: TextStyle(
                    color: Colors.grey[600],
                  ),
                ),
              ],
            ),
          ),
          const Divider(),

          // Settings Options
          ListTile(
            leading: const Icon(Icons.notifications),
            title: const Text('Notifications'),
            subtitle: const Text('Manage SMS alerts'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () {
              // TODO: Navigate to notifications settings
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Coming soon!')),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.person),
            title: const Text('Account'),
            subtitle: const Text('Edit profile information'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () {
              // TODO: Navigate to account settings
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Coming soon!')),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.info),
            title: const Text('About'),
            subtitle: const Text('App version and info'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () {
              showAboutDialog(
                context: context,
                applicationName: 'Free Food Tracker',
                applicationVersion: '1.0.0',
                applicationIcon: const Text('🍕', style: TextStyle(fontSize: 40)),
                children: [
                  const Text('Never miss free food at UMass!'),
                ],
              );
            },
          ),
          const Divider(),

          // Add this to your settings_page.dart temporarily for testing


          // Add this ListTile in your settings page, before the Sign Out button
          ListTile(
            leading: const Icon(Icons.bug_report),
            title: const Text('Test Calendar'),
            subtitle: const Text('Debug: Test calendar integration'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () async {
              print('🧪 Testing calendar...');
              
              // Request permission
              final status = await Permission.calendar.request();
              print('📅 Calendar permission: $status');
              
              if (!status.isGranted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('❌ Calendar permission denied'),
                    backgroundColor: Colors.red,
                  ),
                );
                return;
              }
              
              try {
                final testEvent = Event(
                  title: 'TEST: Free Pizza Event',
                  description: 'This is a test event from WTF app',
                  location: 'CS Building',
                  startDate: DateTime.now().add(const Duration(hours: 1)),
                  endDate: DateTime.now().add(const Duration(hours: 2)),
                  allDay: false,
                );
                
                print('📝 Creating event: ${testEvent.title}');
                final result = await Add2Calendar.addEvent2Cal(testEvent);
                print('✅ Result: $result');
                
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text('✅ Calendar opened! Result: $result'),
                    backgroundColor: Colors.green,
                  ),
                );
              } catch (e) {
                print('❌ Error: $e');
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text('❌ Error: $e'),
                    backgroundColor: Colors.red,
                  ),
                );
              }
            },
          ),

          // Sign Out
          ListTile(
            leading: const Icon(Icons.logout, color: Colors.red),
            title: const Text(
              'Sign Out',
              style: TextStyle(color: Colors.red),
            ),
            onTap: () async {
              final shouldLogout = await showDialog<bool>(
                context: context,
                builder: (context) => AlertDialog(
                  title: const Text('Sign Out'),
                  content: const Text('Are you sure you want to sign out?'),
                  actions: [
                    TextButton(
                      onPressed: () => Navigator.pop(context, false),
                      child: const Text('Cancel'),
                    ),
                    TextButton(
                      onPressed: () => Navigator.pop(context, true),
                      child: const Text(
                        'Sign Out',
                        style: TextStyle(color: Colors.red),
                      ),
                    ),
                  ],
                ),
              );

              if (shouldLogout == true && context.mounted) {
                await auth.signOut();
              }
            },
          ),
        ],
      ),
    );
  }
}