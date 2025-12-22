import 'package:flutter/material.dart';
import 'package:add_2_calendar/add_2_calendar.dart';
import 'package:map_launcher/map_launcher.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:share_plus/share_plus.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:flutter_social_button/flutter_social_button.dart';
import 'package:font_awesome_flutter/font_awesome_flutter.dart';


class EventDetailPage extends StatelessWidget {
  final dynamic event; // Event object from home_page.dart

  const EventDetailPage({Key? key, required this.event}) : super(key: key);

  // Generate shareable text
  String _getShareText() {
    return '''
🍕 ${event.title}

📅 ${event.formattedTime}
📍 ${event.location}
🍴 Free Food: ${event.foodType}
👥 ${event.club}
${event.conditions != null ? '\n⚠️ ${event.conditions}' : ''}

Never miss free food at UMass! Download WTF App 📱
''';
  }

  // Show share options bottom sheet
  void _showShareOptions(BuildContext context) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Padding(
              padding: EdgeInsets.all(16),
              child: Text(
                'Share Event',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            const Divider(height: 1),
            // _buildShareOption(
            //   context,
            //   icon: Icons.share,
            //   title: 'Share via...',
            //   subtitle: 'Use native share sheet',
            //   color: Colors.blue,
            //   onTap: () {
            //     Navigator.pop(context);
            //     _shareGeneric(context);
            //   },
            // ),
            _buildShareOption(
              context,
              icon: const FaIcon(
                FontAwesomeIcons.whatsapp,
                color: Color(0xFF25D366),
                size: 20,
              ),
              title: 'WhatsApp',
              subtitle: 'Share on WhatsApp',
              color: const Color(0xFF25D366),
              onTap: () {
                Navigator.pop(context);
                _shareViaWhatsApp(context);
              },
            ),
            _buildShareOption(
              context,
              icon: const FaIcon(
                FontAwesomeIcons.solidMessage,
                color: Colors.green,
                size: 18,
              ),
              title: 'Messages',
              subtitle: 'iMessage or SMS',
              color: Colors.green,
              onTap: () {
                Navigator.pop(context);
                _shareViaSMS(context);
              },
            ),
            _buildShareOption(
              context,
              icon: const FaIcon(
                FontAwesomeIcons.twitter,
                color: Color(0xFF1DA1F2),
                size: 20,
              ), // X icon
              title: 'X (Twitter)',
              subtitle: 'Post on X',
              color: Colors.black,
              onTap: () {
                Navigator.pop(context);
                _shareViaTwitter(context);
              },
            ),
            _buildShareOption(
              context,
              icon: const FaIcon(
                FontAwesomeIcons.instagram,
                color: Color(0xFFE1306C),
                size: 20,
              ),
              title: 'Instagram',
              subtitle: 'Share to Instagram',
              color: const Color(0xE1306C),
              onTap: () {
                Navigator.pop(context);
                _shareViaInstagram(context);
              },
            ),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }

  Widget _buildShareOption(
    BuildContext context, {
    required Widget icon,
    required String title,
    required String subtitle,
    required Color color,
    required VoidCallback onTap,
  }) {
    return ListTile(
      leading: CircleAvatar(
        backgroundColor: color.withOpacity(0.1),
        child: icon,
      ),
      title: Text(title),
      subtitle: Text(subtitle),
      trailing: const Icon(Icons.chevron_right),
      onTap: onTap,
    );
  }

  // Generic share using native share sheet
  Future<void> _shareGeneric(BuildContext context) async {
    try {
      await Share.share(
        _getShareText(),
        subject: 'Free Food at UMass: ${event.title}',
      );
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error sharing: $e')),
        );
      }
    }
  }

  // Share via WhatsApp
  Future<void> _shareViaWhatsApp(BuildContext context) async {
    final text = Uri.encodeComponent(_getShareText());
    final whatsappUrl = Uri.parse('whatsapp://send?text=$text');
    
    try {
      if (await canLaunchUrl(whatsappUrl)) {
        await launchUrl(whatsappUrl);
      } else {
        // Fallback to web WhatsApp
        final webUrl = Uri.parse('https://wa.me/?text=$text');
        if (await canLaunchUrl(webUrl)) {
          await launchUrl(webUrl, mode: LaunchMode.externalApplication);
        } else {
          throw 'WhatsApp not installed';
        }
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('WhatsApp not installed or unavailable'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  // Share via SMS/iMessage
  Future<void> _shareViaSMS(BuildContext context) async {
    final text = Uri.encodeComponent(_getShareText());
    final smsUrl = Uri.parse('sms:?body=$text');
    
    try {
      if (await canLaunchUrl(smsUrl)) {
        await launchUrl(smsUrl);
      } else {
        throw 'SMS not available';
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('SMS not available on this device'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  // Share via Twitter/X
  Future<void> _shareViaTwitter(BuildContext context) async {
    final text = Uri.encodeComponent(
      '🍕 Free Food Alert!\n\n${event.title} @ ${event.location}\n${event.formattedTime}\n\n#UMass #FreeFood #UMassAmherst'
    );
    
    // Try Twitter app first
    final twitterAppUrl = Uri.parse('twitter://post?message=$text');
    final twitterWebUrl = Uri.parse('https://twitter.com/intent/tweet?text=$text');
    
    try {
      if (await canLaunchUrl(twitterAppUrl)) {
        await launchUrl(twitterAppUrl);
      } else if (await canLaunchUrl(twitterWebUrl)) {
        await launchUrl(twitterWebUrl, mode: LaunchMode.externalApplication);
      } else {
        throw 'Twitter not available';
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Could not open Twitter/X'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  // Share via Instagram
  Future<void> _shareViaInstagram(BuildContext context) async {
    // Instagram doesn't have a direct text sharing API
    // We'll open Instagram app or show message to share manually
    final instagramUrl = Uri.parse('instagram://');
    
    try {
      if (await canLaunchUrl(instagramUrl)) {
        await launchUrl(instagramUrl);
        if (context.mounted) {
          showDialog(
            context: context,
            builder: (context) => AlertDialog(
              title: const Text('Share on Instagram'),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Instagram opened! To share:'),
                  const SizedBox(height: 12),
                  const Text('1. Create a Story or Post'),
                  const Text('2. Add text with event details'),
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.grey[200],
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: SelectableText(
                      _getShareText(),
                      style: const TextStyle(fontSize: 12),
                    ),
                  ),
                ],
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Close'),
                ),
                TextButton(
                  onPressed: () {
                    Share.share(_getShareText());
                    Navigator.pop(context);
                  },
                  child: const Text('Copy & Share'),
                ),
              ],
            ),
          );
        }
      } else {
        throw 'Instagram not installed';
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Instagram not installed'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  // Add event to calendar
  Future<void> _addToCalendar(BuildContext context) async {
    // Show loading dialog
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => const Center(
        child: Card(
          child: Padding(
            padding: EdgeInsets.all(20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                CircularProgressIndicator(),
                SizedBox(height: 16),
                Text('Adding to calendar...'),
              ],
            ),
          ),
        ),
      ),
    );

    try {
      // Request calendar permission first
      final permissionStatus = await Permission.calendar.request();
      
      if (!permissionStatus.isGranted) {
        if (context.mounted) {
          Navigator.pop(context); // Close loading dialog
          
          // Show permission denied dialog
          showDialog(
            context: context,
            builder: (context) => AlertDialog(
              title: const Text('Calendar Permission Required'),
              content: const Text(
                'Please enable calendar access in Settings to add events to your calendar.',
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Cancel'),
                ),
                TextButton(
                  onPressed: () {
                    Navigator.pop(context);
                    openAppSettings();
                  },
                  child: const Text('Open Settings'),
                ),
              ],
            ),
          );
        }
        return;
      }

      // Create calendar event
      final calendarEvent = Event(
        title: event.title,
        description: '${event.club}\n\nFood: ${event.foodType}\n\nLocation: ${event.location}',
        location: event.location,
        startDate: event.dateTime,
        endDate: event.dateTime.add(const Duration(hours: 2)),
        allDay: false,
        iosParams: const IOSParams(
          reminder: Duration(minutes: 30), // Reminder 30 min before
        ),
        androidParams: const AndroidParams(
          emailInvites: [],
        ),
      );

      // Add to calendar
      final result = await Add2Calendar.addEvent2Cal(calendarEvent);
      
      if (context.mounted) {
        Navigator.pop(context); // Close loading dialog
        
        if (result != null && result == true) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Row(
                children: [
                  Icon(Icons.check_circle, color: Colors.white),
                  SizedBox(width: 12),
                  Text('Event added to calendar!'),
                ],
              ),
              backgroundColor: Colors.green,
              duration: Duration(seconds: 3),
            ),
          );
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Calendar opened. Please save the event.'),
              backgroundColor: Colors.orange,
            ),
          );
        }
      }
    } catch (e) {
      debugPrint('Calendar error: $e');
      
      if (context.mounted) {
        Navigator.pop(context); // Close loading dialog
        
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Could not add to calendar',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
                Text('Error: $e', style: const TextStyle(fontSize: 12)),
              ],
            ),
            backgroundColor: Colors.red,
            duration: const Duration(seconds: 5),
          ),
        );
      }
    }
  }

  // Open in map app
  Future<void> _openInMaps(BuildContext context) async {
    try {
      // Get coordinates from event or parse location
      final coords = _getEventCoordinates();
      
      // Check if map apps are available
      final availableMaps = await MapLauncher.installedMaps;

      if (availableMaps.isEmpty) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('No map apps installed')),
          );
        }
        return;
      }

      // If only one map app, open directly
      if (availableMaps.length == 1) {
        await availableMaps.first.showMarker(
          coords: Coords(coords.latitude, coords.longitude),
          title: event.title,
          description: event.location,
        );
        return;
      }

      // Show map selection dialog
      if (context.mounted) {
        await showModalBottomSheet(
          context: context,
          builder: (context) => SafeArea(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text(
                    'Choose Map App',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ),
                ...availableMaps.map((map) {
                  return ListTile(
                    leading: Image.asset(
                      map.icon,
                      height: 30,
                      width: 30,
                    ),
                    title: Text(map.mapName),
                    onTap: () {
                      Navigator.pop(context);
                      map.showMarker(
                        coords: Coords(coords.latitude, coords.longitude),
                        title: event.title,
                        description: event.location,
                      );
                    },
                  );
                }).toList(),
                const SizedBox(height: 16),
              ],
            ),
          ),
        );
      }
    } catch (e) {
      debugPrint('Error opening maps: $e');
      if (context.mounted) {
        // Fallback: Open Google Maps web
        _openGoogleMapsWeb(context);
      }
    }
  }

  // Fallback: Open Google Maps in browser
  Future<void> _openGoogleMapsWeb(BuildContext context) async {
    final coords = _getEventCoordinates();
    final url = Uri.parse(
      'https://www.google.com/maps/search/?api=1&query=${coords.latitude},${coords.longitude}',
    );
    
    if (await canLaunchUrl(url)) {
      await launchUrl(url, mode: LaunchMode.externalApplication);
    } else {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not open maps')),
        );
      }
    }
  }

  // Get coordinates for the event location
  Coords _getEventCoordinates() {
    // Map of building names to coordinates (same as in map_page.dart)
    final buildingCoordinates = <String, Coords>{
      'cs building': Coords(42.3905, -72.5274),
      'computer science building': Coords(42.3905, -72.5274),
      'lederle': Coords(42.3894, -72.5253),
      'lgrt': Coords(42.3908, -72.5286),
      'morrill': Coords(42.3910, -72.5240),
      'hasbrouck': Coords(42.3892, -72.5281),
      'student union': Coords(42.3906, -72.5267),
      'campus center': Coords(42.3906, -72.5267),
      'library': Coords(42.3888, -72.5268),
      'du bois library': Coords(42.3888, -72.5268),
      'southwest': Coords(42.3851, -72.5316),
      'central': Coords(42.3895, -72.5241),
      'northeast': Coords(42.3929, -72.5217),
      'orchard hill': Coords(42.3982, -72.5182),
      'rec center': Coords(42.3863, -72.5298),
      'mullins center': Coords(42.3862, -72.5281),
      'berkshire': Coords(42.3849, -72.5324),
      'worcester': Coords(42.3847, -72.5309),
      'franklin': Coords(42.3896, -72.5232),
      'hampshire': Coords(42.3897, -72.5247),
    };

    final locationLower = event.location.toLowerCase();
    
    for (final building in buildingCoordinates.keys) {
      if (locationLower.contains(building)) {
        return buildingCoordinates[building]!;
      }
    }
    
    // Default to UMass campus center
    return Coords(42.3868, -72.5301);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Event Details'),
        actions: [
          IconButton(
            icon: const Icon(Icons.share),
            onPressed: () => _showShareOptions(context),
            tooltip: 'Share Event',
          ),
        ],
      ),
      body: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Hero Image/Emoji Section
            Container(
              width: double.infinity,
              height: 200,
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    Color(0xFF881C1C),
                    Color(0xFF5C1010),
                  ],
                ),
              ),
              child: Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      event.emoji,
                      style: const TextStyle(fontSize: 80),
                    ),
                    const SizedBox(height: 12),
                    if (event.isVerified)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: const [
                            Icon(
                              Icons.verified,
                              size: 16,
                              color: Color(0xFF881C1C),
                            ),
                            SizedBox(width: 6),
                            Text(
                              'Verified Event',
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                color: Color(0xFF881C1C),
                              ),
                            ),
                          ],
                        ),
                      )
                    else
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                        decoration: BoxDecoration(
                          color: Colors.orange[100],
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: const [
                            Icon(
                              Icons.pending,
                              size: 16,
                              color: Colors.orange,
                            ),
                            SizedBox(width: 6),
                            Text(
                              'Pending Verification',
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                color: Colors.orange,
                              ),
                            ),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
            ),

            // Event Info
            Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Title
                  Text(
                    event.title,
                    style: const TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),

                  // Club
                  Text(
                    event.club,
                    style: TextStyle(
                      fontSize: 16,
                      color: Colors.grey[600],
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Details Cards
                  _buildInfoCard(
                    icon: Icons.access_time,
                    title: 'When',
                    subtitle: event.formattedTime,
                    color: Colors.blue,
                  ),
                  const SizedBox(height: 12),

                  _buildInfoCard(
                    icon: Icons.location_on,
                    title: 'Where',
                    subtitle: event.location,
                    color: Colors.red,
                  ),
                  const SizedBox(height: 12),

                  _buildInfoCard(
                    icon: Icons.restaurant,
                    title: 'Food Available',
                    subtitle: event.foodType,
                    color: Colors.orange,
                  ),

                  // Conditions (if any)
                  if (event.conditions != null) ...[
                    const SizedBox(height: 12),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.orange[50],
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: Colors.orange),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.info, color: Colors.orange),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text(
                                  'Important Note',
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    color: Colors.orange,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  event.conditions!,
                                  style: const TextStyle(fontSize: 14),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],

                  const SizedBox(height: 32),

                  // Action Buttons
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () => _addToCalendar(context),
                          icon: const Icon(Icons.calendar_today),
                          label: const Text('Add to Calendar'),
                          style: OutlinedButton.styleFrom(
                            padding: const EdgeInsets.symmetric(vertical: 14),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: ElevatedButton.icon(
                          onPressed: () => _openInMaps(context),
                          icon: const Icon(Icons.directions),
                          label: const Text('Directions'),
                          style: ElevatedButton.styleFrom(
                            padding: const EdgeInsets.symmetric(vertical: 14),
                          ),
                        ),
                      ),
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

  Widget _buildInfoCard({
    required IconData icon,
    required String title,
    required String subtitle,
    required Color color,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey[300]!),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: color.withOpacity(0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: color, size: 24),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey[600],
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  subtitle,
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}