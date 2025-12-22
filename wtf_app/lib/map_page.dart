import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:geolocator/geolocator.dart';
import 'package:permission_handler/permission_handler.dart';
import 'dart:async';
import 'event_detail_page.dart';

// Mock Event class (should match the one in home_page.dart)
class MapEvent {
  final int id;
  final String title;
  final String club;
  final String location;
  final String foodType;
  final String emoji;
  final LatLng coordinates;

  MapEvent({
    required this.id,
    required this.title,
    required this.club,
    required this.location,
    required this.foodType,
    required this.emoji,
    required this.coordinates,
  });
}

class MapPage extends StatefulWidget {
  const MapPage({Key? key}) : super(key: key);

  @override
  State<MapPage> createState() => _MapPageState();
}

class _MapPageState extends State<MapPage> {
  GoogleMapController? _mapController;
  Position? _currentPosition;
  bool _isLoadingLocation = true;
  bool _locationPermissionDenied = false;
  
  // UMass Amherst campus center coordinates
  static const LatLng _umassCenter = LatLng(42.3868, -72.5301);
  
  // Events with coordinates
  final List<MapEvent> _events = [];
  Set<Marker> _markers = {};
  
  // Map of building names to coordinates (UMass buildings)
  final Map<String, LatLng> _buildingCoordinates = {
    // Academic Buildings
    'cs building': LatLng(42.3905, -72.5274),
    'computer science building': LatLng(42.3905, -72.5274),
    'lederle': LatLng(42.3894, -72.5253),
    'lgrt': LatLng(42.3908, -72.5286),
    'morrill': LatLng(42.3910, -72.5240),
    'hasbrouck': LatLng(42.3892, -72.5281),
    'student union': LatLng(42.3906, -72.5267),
    'campus center': LatLng(42.3906, -72.5267),
    'library': LatLng(42.3888, -72.5268),
    'du bois library': LatLng(42.3888, -72.5268),
    
    // Dorms
    'southwest': LatLng(42.3851, -72.5316),
    'central': LatLng(42.3895, -72.5241),
    'northeast': LatLng(42.3929, -72.5217),
    'orchard hill': LatLng(42.3982, -72.5182),
    
    // Recreation
    'rec center': LatLng(42.3863, -72.5298),
    'mullins center': LatLng(42.3862, -72.5281),
    
    // Dining
    'berkshire': LatLng(42.3849, -72.5324),
    'worcester': LatLng(42.3847, -72.5309),
    'franklin': LatLng(42.3896, -72.5232),
    'hampshire': LatLng(42.3897, -72.5247),
  };

  @override
  void initState() {
    super.initState();
    _requestLocationPermission();
    _loadEvents();
  }

  @override
  void dispose() {
    _mapController?.dispose();
    super.dispose();
  }

  Future<void> _requestLocationPermission() async {
    // Check service
    final serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      setState(() {
        _locationPermissionDenied = true;
        _isLoadingLocation = false;
      });
      return;
    }

    LocationPermission permission = await Geolocator.checkPermission();

    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }

    if (permission == LocationPermission.deniedForever ||
        permission == LocationPermission.denied) {
      setState(() {
        _locationPermissionDenied = true;
        _isLoadingLocation = false;
      });
      return;
    }

    await _getCurrentLocation();
  }

  Future<void> _getCurrentLocation() async {
    try {
      final position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      );
      
      setState(() {
        _currentPosition = position;
        _isLoadingLocation = false;
      });
      
      // Move camera to user location if on campus
      if (_mapController != null && _isOnCampus(position)) {
        _mapController!.animateCamera(
          CameraUpdate.newLatLngZoom(
            LatLng(position.latitude, position.longitude),
            17,
          ),
        );
      }
    } catch (e) {
      debugPrint('Error getting location: $e');
      setState(() => _isLoadingLocation = false);
    }
  }

  bool _isOnCampus(Position position) {
    // Check if user is within ~1km of campus center
    final distance = Geolocator.distanceBetween(
      _umassCenter.latitude,
      _umassCenter.longitude,
      position.latitude,
      position.longitude,
    );
    return distance < 2000; // 2km radius
  }

  void _loadEvents() {
    // TODO: Load from API
    // For now, mock data with coordinates
    _events.clear();
    _events.addAll([
      MapEvent(
        id: 1,
        title: 'CS Club Meeting',
        club: 'Computer Science Club',
        location: 'CS Building Room 142',
        foodType: 'Pizza & Drinks',
        emoji: '🍕',
        coordinates: _getCoordinatesForLocation('CS Building Room 142'),
      ),
      MapEvent(
        id: 2,
        title: 'Engineering Social',
        club: 'Engineering Society',
        location: 'Student Union',
        foodType: 'Tacos & Snacks',
        emoji: '🌮',
        coordinates: _getCoordinatesForLocation('LGRT 1635'),
      ),
      MapEvent(
        id: 3,
        title: 'Math Seminar',
        club: 'Math Department',
        location: 'LGRT 1634',
        foodType: 'Coffee & Cookies',
        emoji: '🍪',
        coordinates: _getCoordinatesForLocation('LGRT 1634'),
      ),
    ]);
    
    _createMarkers();
  }

  LatLng _getCoordinatesForLocation(String location) {
    // Try to match location to known buildings
    final locationLower = location.toLowerCase();
    
    for (final building in _buildingCoordinates.keys) {
      if (locationLower.contains(building)) {
        return _buildingCoordinates[building]!;
      }
    }
    
    // Default to campus center if not found
    return _umassCenter;
  }

  void _createMarkers() {
    final markers = <Marker>{};
    final groupedEvents = _groupEventsByLocation();

    for (final entry in groupedEvents.entries) {
      final location = entry.key;
      final eventsAtLocation = entry.value;

      markers.add(
        Marker(
          markerId: MarkerId(
            'event_${location.latitude}_${location.longitude}',
          ),
          position: location,
          icon: BitmapDescriptor.defaultMarkerWithHue(
            BitmapDescriptor.hueOrange,
          ),
          infoWindow: InfoWindow(
            title: eventsAtLocation.length == 1
                ? '${eventsAtLocation.first.emoji} ${eventsAtLocation.first.title}'
                : '🍽 ${eventsAtLocation.length} events here',
            snippet: eventsAtLocation.length == 1
                ? eventsAtLocation.first.location
                : 'Tap to view all',
            onTap: () {
              if (eventsAtLocation.length == 1) {
                _showEventBottomSheet(eventsAtLocation.first);
              } else {
                _showMultipleEventsBottomSheet(eventsAtLocation);
              }
            },
          ),
        ),
      );
    }

    setState(() => _markers = markers);
  }

  void _showMultipleEventsBottomSheet(List<MapEvent> events) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => ListView.separated(
        padding: const EdgeInsets.all(16),
        itemCount: events.length,
        separatorBuilder: (_, __) => const Divider(),
        itemBuilder: (context, index) {
          final event = events[index];
          return ListTile(
            leading: Text(event.emoji, style: const TextStyle(fontSize: 28)),
            title: Text(event.title),
            subtitle: Text('${event.club}\n${event.foodType}'),
            isThreeLine: true,
            onTap: () {
              Navigator.pop(context);
              _showEventBottomSheet(event);
            },
          );
        },
      ),
    );
  }



  Map<LatLng, List<MapEvent>> _groupEventsByLocation() {
    final Map<LatLng, List<MapEvent>> grouped = {};

    for (final event in _events) {
      grouped.putIfAbsent(event.coordinates, () => []).add(event);
    }

    return grouped;
  }


  void _showEventBottomSheet(MapEvent event) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => Container(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(event.emoji, style: const TextStyle(fontSize: 40)),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        event.title,
                        style: const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      Text(
                        event.club,
                        style: TextStyle(
                          color: Colors.grey[600],
                          fontSize: 14,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                const Icon(Icons.location_on, size: 20),
                const SizedBox(width: 8),
                Expanded(child: Text(event.location)),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                const Icon(Icons.restaurant, size: 20),
                const SizedBox(width: 8),
                Text(event.foodType),
              ],
            ),
            const SizedBox(height: 20),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () {
                      Navigator.pop(context);
                      _getDirections(event.coordinates);
                    },
                    icon: const Icon(Icons.directions),
                    label: const Text('Directions'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: () {
                      Navigator.pop(context);
                      // TODO: Navigate to event detail page
                    },
                    icon: const Icon(Icons.info),
                    label: const Text('Details'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  void _getDirections(LatLng destination) {
    if (_currentPosition == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Location not available')),
      );
      return;
    }
    
    // Animate camera to show both points
    _mapController?.animateCamera(
      CameraUpdate.newLatLngBounds(
        LatLngBounds(
          southwest: LatLng(
            _currentPosition!.latitude < destination.latitude
                ? _currentPosition!.latitude
                : destination.latitude,
            _currentPosition!.longitude < destination.longitude
                ? _currentPosition!.longitude
                : destination.longitude,
          ),
          northeast: LatLng(
            _currentPosition!.latitude > destination.latitude
                ? _currentPosition!.latitude
                : destination.latitude,
            _currentPosition!.longitude > destination.longitude
                ? _currentPosition!.longitude
                : destination.longitude,
          ),
        ),
        100, // padding
      ),
    );
    
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Showing route on map')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Campus Map'),
        actions: [
          if (_currentPosition != null)
            IconButton(
              icon: const Icon(Icons.my_location),
              onPressed: () {
                _mapController?.animateCamera(
                  CameraUpdate.newLatLngZoom(
                    LatLng(
                      _currentPosition!.latitude,
                      _currentPosition!.longitude,
                    ),
                    17,
                  ),
                );
              },
              tooltip: 'My Location',
            ),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              setState(() {});
              _loadEvents();
              _getCurrentLocation();
            },
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: Stack(
        children: [
          // Google Map
          GoogleMap(
            initialCameraPosition: CameraPosition(
              target: _umassCenter,
              zoom: 15,
            ),
            onMapCreated: (controller) {
              _mapController = controller;
              _createMarkers();
            },
            markers: _markers,
            myLocationEnabled: true,
            myLocationButtonEnabled: false,
            compassEnabled: true,
            mapToolbarEnabled: false,
            zoomControlsEnabled: false,
            // Constrain map to UMass campus area
            minMaxZoomPreference: const MinMaxZoomPreference(14, 20),
            cameraTargetBounds: CameraTargetBounds(
              LatLngBounds(
                southwest: const LatLng(42.375, -72.545),
                northeast: const LatLng(42.405, -72.515),
              ),
            ),
          ),
          
          // Loading overlay
          if (_isLoadingLocation)
            Container(
              color: Colors.black26,
              child: const Center(
                child: Card(
                  child: Padding(
                    padding: EdgeInsets.all(20),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        CircularProgressIndicator(),
                        SizedBox(height: 16),
                        Text('Getting your location...'),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          
          // Permission denied message
          if (_locationPermissionDenied)
            Positioned(
              top: 16,
              left: 16,
              right: 16,
              child: Card(
                color: Colors.orange[100],
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Row(
                    children: [
                      const Icon(Icons.location_off, color: Colors.orange),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: const [
                            Text(
                              'Location Permission Denied',
                              style: TextStyle(fontWeight: FontWeight.bold),
                            ),
                            Text(
                              'Enable location to see your position',
                              style: TextStyle(fontSize: 12),
                            ),
                          ],
                        ),
                      ),
                      TextButton(
                        onPressed: () {
                          openAppSettings();
                        },
                        child: const Text('Settings'),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          
          // // Event count badge
          // Positioned(
          //   bottom: 16,
          //   left: 16,
          //   child: Card(
          //     child: Padding(
          //       padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          //       child: Row(
          //         mainAxisSize: MainAxisSize.min,
          //         children: [
          //           const Icon(Icons.restaurant, color: Color(0xFF881C1C)),
          //           const SizedBox(width: 8),
          //           Text(
          //             '${_events.length} events nearby',
          //             style: const TextStyle(fontWeight: FontWeight.bold),
          //           ),
          //         ],
          //       ),
          //     ),
          //   ),
          // ),
        ],
      ),
    );
  }
}