// MapTiler Configuration
const MAPTILER_KEY = 'MT4X5mlV3sOGZhylVirr';
const SPEED_THRESHOLD_KMH = 9;  // 9 km/h to trigger motorcycle prompt
const PROMPT_COOLDOWN = 5000;  // 5 seconds before showing prompt again
const GPS_UPDATE_INTERVAL = 1000;  // Send GPS update every 1 second

let map;
let currentRideId = null;
let isRecording = false;
let rideStartTime = null;
let lastPromptTime = 0;
let gpsWatchId = null;
let ridePolyline = null;
let ridePoints = [];
let rideRoute = [];
let startPoint = null;
let totalDistance = 0;
let avgSpeed = 0;
let topSpeed = 0;

// Toast notification system (instead of alert)
function showToast(message, type = 'info', duration = 3000) {
  // type can be: 'success', 'error', 'info', 'warning'
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  toast.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    padding: 16px 20px;
    border-radius: 8px;
    color: white;
    font-weight: 500;
    z-index: 10000;
    animation: slideIn 0.3s ease;
    max-width: 400px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  `;
  
  // Set colors based on type
  const colors = {
    success: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
    error: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
    info: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
    warning: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
  };
  
  toast.style.background = colors[type] || colors.info;
  document.body.appendChild(toast);
  
  // Auto remove after duration
  setTimeout(() => {
    toast.style.animation = 'slideOut 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// Add animation styles
const style = document.createElement('style');
style.textContent = `
  @keyframes slideIn {
    from { transform: translateX(400px); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
  }
  @keyframes slideOut {
    from { transform: translateX(0); opacity: 1; }
    to { transform: translateX(400px); opacity: 0; }
  }
`;
document.head.appendChild(style);

// Format time in seconds to HH:MM or MM:SS format
function formatTime(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

// Helper functions to persist state
function saveState() {
  localStorage.setItem('motoLog_rideState', JSON.stringify({
    currentRideId,
    isRecording,
    rideStartTime
  }));
}

function restoreState() {
  const saved = localStorage.getItem('motoLog_rideState');
  if (saved) {
    try {
      const state = JSON.parse(saved);
      // Only restore if we have a valid ride ID
      if (state.currentRideId) {
        currentRideId = state.currentRideId;
        isRecording = state.isRecording;
        rideStartTime = state.rideStartTime;
        console.log('📂 State restored from localStorage with active ride ID:', state.currentRideId);
      } else {
        console.log('📂 localStorage exists but has no ride ID. Clearing stale state.');
        clearState();
      }
    } catch (e) {
      console.error('Failed to restore state:', e);
      clearState();
    }
  } else {
    console.log('📂 No saved state in localStorage');
  }
}

function clearState() {
  currentRideId = null;
  isRecording = false;
  rideStartTime = null;
  localStorage.removeItem('motoLog_rideState');
}

// Initialize map
function initMap() {
  map = L.map('map').setView([42.6955, 23.3322], 13);
  
  L.tileLayer(`https://api.maptiler.com/maps/streets-v2/{z}/{x}/{y}.png?key=${MAPTILER_KEY}`, {
    attribution: '<a href="https://www.maptiler.com/copyright/" target="_blank">&copy; MapTiler</a> <a href="https://www.openstreetmap.org/copyright" target="_blank">&copy; OpenStreetMap</a>',
    tileSize: 256,
    maxZoom: 19
  }).addTo(map);
}

// Start manual ride
function startManualRide() {
  console.log('🔘 START BUTTON CLICKED');
  console.log('   Current state: isRecording=' + isRecording + ', currentRideId=' + currentRideId);
  
  if (isRecording) {
    console.log('⚠️  Already recording. Ignoring click.');
    return;
  }
  
  console.log('✅ Not recording yet. Initiating start sequence...');
  document.getElementById('startBtn').textContent = '⏳ Starting...';
  document.getElementById('startBtn').disabled = true;
  startRide();
}

// Start ride recording
function startRide() {
  const bikeId = document.getElementById('bikeSelect').value;
  
  console.log('🟢 startRide() called with bikeId:', bikeId);
  console.log('   Current state before: currentRideId=', currentRideId, 'isRecording=', isRecording);
  
  fetch('/api/ride/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ bike_id: bikeId || null })
  })
  .then(r => {
    console.log('📡 Response status:', r.status);
    return r.json();
  })
  .then(data => {
    console.log('🔍 startRide API response:', JSON.stringify(data));
    console.log('   data.success:', data.success);
    console.log('   data.ride_id:', data.ride_id);
    console.log('   data.error:', data.error);
    
    if (!data) {
      throw new Error('No response data from server');
    }
    
    // Validate ride_id is a positive number
    if (data.success === true && data.ride_id && data.ride_id > 0) {
      // Set state FIRST before anything else
      currentRideId = data.ride_id;
      isRecording = true;
      rideStartTime = Date.now();
      ridePoints = [];
      rideRoute = [];
      saveState();
      
      console.log('✅ State set successfully:');
      console.log('   currentRideId=', currentRideId, '(type:', typeof currentRideId, ')');
      console.log('   isRecording=', isRecording);
      console.log('   rideStartTime=', rideStartTime);
      console.log('💾 State saved to localStorage');
      
      // Verify state was saved
      const saved = localStorage.getItem('motoLog_rideState');
      console.log('💾 Saved state in localStorage:', saved);
      
      // Update UI
      document.getElementById('status').textContent = '🔴 Recording...';
      document.getElementById('status').className = 'track-status status-recording';
      document.getElementById('startBtn').textContent = '▶ Start';
      document.getElementById('startBtn').disabled = true;
      document.getElementById('stopBtn').disabled = false;
      document.getElementById('bikeSelect').disabled = true;
      
      // Clear previous route
      if (ridePolyline) map.removeLayer(ridePolyline);
      if (startPoint) map.removeLayer(startPoint);
      startPoint = null;
      
      // Start GPS tracking
      console.log('🎯 Starting GPS tracking...');
      startGPSTracking();
    } else if (data.success === false) {
      throw new Error('API error: ' + (data.error || 'Unknown error'));
    } else {
      throw new Error('Bad response: success=' + data.success + ', ride_id=' + data.ride_id);
    }
  })
  .catch(e => {
    console.error('❌ ERROR in startRide:', e);
    console.error('❌ Stack trace:', e.stack);
    document.getElementById('startBtn').textContent = '▶ Start';
    document.getElementById('startBtn').disabled = false;
    showToast('Failed to start ride: ' + e.message, 'error');
  });
}

// Start GPS tracking with watchPosition
function startGPSTracking() {
  if (!navigator.geolocation) {
    console.warn('⚠️ Geolocation not supported on this device');
    showToast('Geolocation not available. Recording will continue without GPS.', 'warning');
    return;
  }
  
  // Clear any previous GPS watch to avoid conflicts
  if (gpsWatchId !== null) {
    console.log('🛑 Clearing previous GPS watch:', gpsWatchId);
    navigator.geolocation.clearWatch(gpsWatchId);
    gpsWatchId = null;
  }
  
  const options = {
    enableHighAccuracy: true,
    maximumAge: 0,  // Don't use cached location - always get fresh GPS
    timeout: 5000   // Wait up to 5 seconds for a GPS fix
  };
  
  console.log('🎯 Starting fresh GPS watch with options:', options);
  gpsWatchId = navigator.geolocation.watchPosition(onGPSUpdate, onGPSError, options);
  console.log('   GPS watch ID:', gpsWatchId);
}

// Handle GPS updates
function onGPSUpdate(position) {
  const { latitude, longitude, speed, heading, accuracy } = position.coords;
  const timestamp = Math.floor(Date.now() / 1000);
  
  console.log('📍 GPS Update received:');
  console.log('   Accuracy:', accuracy, 'meters', accuracy <= 50 ? '✅ GOOD' : accuracy <= 100 ? '⚠️ FAIR' : '❌ POOR');
  console.log('   Lat:', latitude, 'Lon:', longitude);
  console.log('   Speed:', speed ? (speed * 3.6).toFixed(1) : 0, 'km/h');
  
  // Only use GPS fixes with reasonable accuracy (better than 100 meters)
  if (accuracy > 100) {
    console.log('   ⚠️ Accuracy too poor (' + accuracy + 'm), skipping this point');
    // Still return so we don't miss better fixes
  }
  
  // Speed is in m/s, convert to km/h
  const speedKMH = (speed || 0) * 3.6;
  
  // Store point
  const point = { latitude, longitude, speed: speedKMH, timestamp, accuracy };
  ridePoints.push(point);
  rideRoute.push([latitude, longitude]);
  
  // Zoom map to current position on first GPS update with good accuracy
  if (ridePoints.length === 1 || (ridePoints.length <= 3 && accuracy <= 100)) {
    console.log('🗺️ Centering map on accurate location (accuracy: ' + accuracy + 'm, zoom 18)');
    // Use zoom level 18 for very accurate location
    map.setView([latitude, longitude], 18);
  } else if (ridePoints.length > 1) {
    // Keep centering on recent good positions
    map.setView([latitude, longitude], map.getZoom());
  }
  
  // Update map
  updateMapRoute();
  updateStats();
  
  // Check for high speed to trigger motorcycle prompt
  if (speedKMH > SPEED_THRESHOLD_KMH && !isRecording && (Date.now() - lastPromptTime) > PROMPT_COOLDOWN) {
    lastPromptTime = Date.now();
    showMotorcyclePrompt();
  }
  
  // Send GPS point to backend if recording
  if (isRecording && currentRideId) {
    fetch('/api/ride/add-gps-point', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ride_id: currentRideId,
        latitude,
        longitude,
        speed: speedKMH,
        altitude: position.coords.altitude,
        timestamp
      })
    }).catch(e => console.error('Error adding GPS point:', e));
  }
}

function onGPSError(error) {
  console.error('GPS Error:', error.message, 'Code:', error.code);
  // Don't alert on every error, just log it
  // The ride can continue recording without GPS points
  if (error.code === 3) {
    console.warn('GPS timeout - continuing ride without location updates');
  }
}

// Show motorcycle prompt
function showMotorcyclePrompt() {
  document.getElementById('motorcyclePrompt').style.display = 'block';
}

// Handle motorcycle confirmation
function confirmMotorcycle(isMotorcycle) {
  document.getElementById('motorcyclePrompt').style.display = 'none';
  
  if (isMotorcycle) {
    startRide();
  }
}

// Update map route visualization
function updateMapRoute() {
  if (rideRoute.length < 2) return;
  
  if (ridePolyline) {
    map.removeLayer(ridePolyline);
  }
  
  ridePolyline = L.polyline(rideRoute, {
    color: '#3b82f6',
    weight: 3,
    opacity: 0.8,
    dashArray: '5, 5'
  }).addTo(map);
  
  // Add start marker
  if (!startPoint && rideRoute.length > 0) {
    startPoint = L.circleMarker(rideRoute[0], {
      radius: 6,
      fillColor: '#10b981',
      color: '#fff',
      weight: 2,
      opacity: 1,
      fillOpacity: 0.8
    }).addTo(map);
  }
  
  // Add end marker (current position)
  const lastPoint = rideRoute[rideRoute.length - 1];
  L.circleMarker(lastPoint, {
    radius: 5,
    fillColor: '#3b82f6',
    color: '#fff',
    weight: 2,
    opacity: 1,
    fillOpacity: 0.8
  }).addTo(map);
  
  // Center map on current position
  map.setView(lastPoint, map.getZoom());
}

// Update displayed statistics
function updateStats() {
  if (ridePoints.length < 1) return;
  
  // Distance calculation using Haversine formula
  let distance = 0;
  for (let i = 0; i < ridePoints.length - 1; i++) {
    const d = haversine(
      ridePoints[i].latitude, ridePoints[i].longitude,
      ridePoints[i + 1].latitude, ridePoints[i + 1].longitude
    );
    distance += d;
  }
  totalDistance = distance;  // Save globally for modal
  
  // Speed stats
  const speeds = ridePoints.map(p => p.speed).filter(s => s > 0);
  topSpeed = speeds.length > 0 ? Math.max(...speeds) : 0;
  avgSpeed = speeds.length > 0 ? speeds.reduce((a, b) => a + b) / speeds.length : 0;
  
  // Time
  const elapsedSeconds = Math.floor((Date.now() - rideStartTime) / 1000);
  const minutes = Math.floor(elapsedSeconds / 60);
  const seconds = elapsedSeconds % 60;
  
  // Current speed
  const currentSpeed = ridePoints.length > 0 ? ridePoints[ridePoints.length - 1].speed : 0;
  
  // Update UI
  document.getElementById('distance').textContent = (distance / 1000).toFixed(2) + ' km';
  document.getElementById('speed').textContent = Math.round(currentSpeed) + ' km/h';
  document.getElementById('topSpeed').textContent = topSpeed.toFixed(1) + ' km/h';
  document.getElementById('avgSpeed').textContent = avgSpeed.toFixed(1) + ' km/h';
  document.getElementById('time').textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

// Stop ride
function stopRide() {
  console.log('🛑 stopRide() called. State: currentRideId=', currentRideId, 'isRecording=', isRecording);
  
  // Restore state in case it was lost
  if (!currentRideId) {
    restoreState();
    console.log('⚠️ State was lost. Restored from localStorage. currentRideId=', currentRideId);
  }
  
  // Check both conditions but provide helpful error messages
  if (!currentRideId) {
    console.error('❌ ERROR: No ride ID!');
    showToast('No ride ID found. Did you click Start?', 'error');
    return;
  }
  
  if (!isRecording) {
    console.warn('⚠️ WARNING: isRecording is false but we have a ride ID. Attempting stop anyway...');
    // Don't return here - allow stop to proceed with just the ride ID
  }
  
  // Stop GPS tracking first
  if (gpsWatchId) {
    navigator.geolocation.clearWatch(gpsWatchId);
    gpsWatchId = null;
    console.log('🛑 GPS watch stopped');
  }
  
  // Update modal with current stats
  document.getElementById('modalDistance').textContent = totalDistance.toFixed(2) + ' km';
  document.getElementById('modalTime').textContent = formatTime(Math.floor((Date.now() - rideStartTime) / 1000));
  document.getElementById('modalAvgSpeed').textContent = (avgSpeed || 0).toFixed(1) + ' km/h';
  document.getElementById('modalTopSpeed').textContent = (topSpeed || 0).toFixed(1) + ' km/h';
  
  // Clear form fields
  document.getElementById('rideTitle').value = '';
  document.getElementById('rideDescription').value = '';
  document.getElementById('ridePhotos').value = '';
  document.getElementById('photoPreview').textContent = '';
  document.getElementById('ridePublic').checked = true;
  
  // Show modal
  document.getElementById('stopOverlay').classList.add('active');
  document.getElementById('stopModal').classList.add('active');
  document.getElementById('rideTitle').focus();
  
  console.log('✅ Stop modal displayed');
}

function submitStopForm(event) {
  event.preventDefault();
  
  console.log('📝 Form submitted');
  
  const title = document.getElementById('rideTitle').value || 'My Ride';
  const description = document.getElementById('rideDescription').value || '';
  const isPublic = document.getElementById('ridePublic').checked;
  const photos = document.getElementById('ridePhotos').files;
  const saveBtn = document.getElementById('saveRideBtn');
  
  if (!title.trim()) {
    showToast('Please enter a ride title', 'warning');
    return false;
  }
  
  // Disable button and show loading state
  saveBtn.disabled = true;
  saveBtn.classList.add('loading');
  saveBtn.textContent = 'Saving...';
  
  // Create FormData for file upload
  const formData = new FormData();
  formData.append('ride_id', currentRideId);
  formData.append('title', title);
  formData.append('description', description);
  formData.append('public', isPublic);
  
  // Add photos if selected
  if (photos && photos.length > 0) {
    for (let i = 0; i < photos.length; i++) {
      formData.append('photos', photos[i]);
    }
  }
  
  console.log('📤 Sending stop request for ride:', currentRideId);
  
  fetch('/api/ride/stop', {
    method: 'POST',
    body: formData
  })
  .then(r => r.json())
  .then(data => {
    console.log('✅ Stop response:', data);
    
    if (data.error) {
      throw new Error(data.error);
    }
    
    // Hide modal
    document.getElementById('stopOverlay').classList.remove('active');
    document.getElementById('stopModal').classList.remove('active');
    
    // Reset UI
    showToast('Ride saved successfully! 🎉', 'success');
    document.getElementById('status').textContent = '✅ Ride finished: ' + title;
    document.getElementById('stopBtn').disabled = true;
    document.getElementById('stopBtn').textContent = 'Stop Ride';
    document.getElementById('startBtn').disabled = false;
    document.getElementById('startBtn').textContent = 'Start Ride';
    
    // Clear state
    currentRideId = null;
    isRecording = false;
    rideStartTime = null;
    ridePoints = [];
    rideRoute = [];
    totalDistance = 0;
    avgSpeed = 0;
    topSpeed = 0;
    localStorage.removeItem('motoLog_rideState');
    
    // Reset form and button
    document.getElementById('stopForm').reset();
    saveBtn.disabled = false;
    saveBtn.classList.remove('loading');
    saveBtn.textContent = 'Save Ride';
  })
  .catch(e => {
    console.error('❌ Error stopping ride:', e);
    showToast('Error saving ride: ' + e.message, 'error');
    document.getElementById('status').textContent = '❌ Error: ' + e.message;
    
    // Re-enable button on error
    saveBtn.disabled = false;
    saveBtn.classList.remove('loading');
    saveBtn.textContent = 'Save Ride';
  });
  
  return false;
}

function cancelStopForm() {
  console.log('❌ Stop form cancelled');
  
  // Hide modal
  document.getElementById('stopOverlay').classList.remove('active');
  document.getElementById('stopModal').classList.remove('active');
  
  // Optionally resume GPS if ride is still active
  if (currentRideId && isRecording && !gpsWatchId) {
    console.log('📍 Resuming GPS tracking...');
    startGPSTracking();
  }
}

// Upload and parse GPX file
function uploadGPX() {
  const fileInput = document.getElementById('gpxFile');
  const file = fileInput.files[0];
  const uploadBtn = event.target;
  
  if (!file) {
    showToast('Please select a GPX file', 'warning');
    return;
  }
  
  uploadBtn.textContent = '📤 Uploading...';
  uploadBtn.disabled = true;
  
  const formData = new FormData();
  formData.append('gpx_file', file);
  
  console.log('🟡 uploadGPX() started. Current state:');
  console.log('   currentRideId:', currentRideId);
  console.log('   isRecording:', isRecording);
  
  // Restore state in case it was lost
  if (!currentRideId) {
    restoreState();
    console.log('📂 Restored state from localStorage. currentRideId=', currentRideId);
  }
  
  fetch('/api/ride/upload-gpx', {
    method: 'POST',
    body: formData
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      console.log('✅ GPX file uploaded successfully with', data.count, 'points');
      console.log('📊 Current state after upload - isRecording:', isRecording, 'currentRideId:', currentRideId);
      
      // If ride not started, start it now
      if (!currentRideId) {
        console.log('🟠 No active ride. Auto-starting new ride for GPX...');
        
        const bikeId = document.getElementById('bikeSelect').value;
        
        fetch('/api/ride/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ bike_id: bikeId || null })
        })
        .then(r => r.json())
        .then(startData => {
          console.log('📡 Start API response:', startData);
          console.log('   success:', startData.success, 'ride_id:', startData.ride_id);
          
          if (startData.success && startData.ride_id && startData.ride_id > 0) {
            // Set ALL state immediately and SAVE IT
            currentRideId = startData.ride_id;
            isRecording = true;
            rideStartTime = Date.now();
            ridePoints = [];
            rideRoute = [];
            saveState();
            
            console.log('✅✅ AUTO-START SUCCESS! New state:');
            console.log('   currentRideId:', currentRideId);
            console.log('   isRecording:', isRecording);
            console.log('   rideStartTime:', rideStartTime);
            console.log('💾 State saved to localStorage');
            
            // Update UI
            document.getElementById('status').textContent = '🔴 Recording...';
            document.getElementById('status').className = 'track-status status-recording';
            document.getElementById('startBtn').disabled = true;
            document.getElementById('stopBtn').disabled = false;
            document.getElementById('bikeSelect').disabled = true;
            
            // Start GPS
            startGPSTracking();
            
            // Proceed with GPX immediately
            console.log('✅ State ready! Starting GPX simulation with', data.points.length, 'points');
            simulateGPXRide(data.points);
            
            uploadBtn.textContent = '📤 Upload GPX';
            uploadBtn.disabled = false;
          } else {
            console.error('❌ Failed to start ride:', startData.error);
            showToast('Failed to start ride: ' + startData.error, 'error');
            uploadBtn.textContent = '📤 Upload GPX';
            uploadBtn.disabled = false;
          }
        })
        .catch(e => {
          console.error('❌ Error calling start API:', e);
          showToast('Network error: ' + e.message, 'error');
          uploadBtn.textContent = '📤 Upload GPX';
          uploadBtn.disabled = false;
        });
      } else {
        console.log('✅ Ride already active (ID: ' + currentRideId + '), proceeding with GPX immediately');
        simulateGPXRide(data.points);
        uploadBtn.textContent = '📤 Upload GPX';
        uploadBtn.disabled = false;
      }
      
      document.getElementById('gpxFile').value = '';
      document.getElementById('fileName').textContent = '📄 Choose GPX File';
      
      setTimeout(() => {
        showToast(`Loaded ${data.count} GPS points from GPX file`, 'success');
      }, 500);
    } else {
      showToast('Error: ' + data.error, 'error');
      uploadBtn.textContent = '📤 Upload GPX';
      uploadBtn.disabled = false;
    }
  })
  .catch(e => {
    console.error('Error uploading GPX:', e);
    showToast('Upload error: ' + e.message, 'error');
    uploadBtn.textContent = '📤 Upload GPX';
    uploadBtn.disabled = false;
  });
}

// Simulate ride from GPX points
function simulateGPXRide(gpxPoints) {
  console.log('🎯 simulateGPXRide() called');
  console.log('   currentRideId:', currentRideId, '(type:', typeof currentRideId, ')');
  console.log('   isRecording:', isRecording);
  console.log('   gpxPoints:', gpxPoints.length);
  
  // Restore state if it was somehow lost
  if (!currentRideId) {
    console.log('⚠️ currentRideId is null! Attempting to restore from localStorage...');
    restoreState();
  }
  
  if (!currentRideId) {
    console.error('❌ FATAL: No ride ID available even after restore!');
    showToast('Error: No active ride ID. Please click Start again or refresh.', 'error');
    return;
  }
  
  if (!isRecording) {
    console.warn('⚠️ WARNING: isRecording is false, but we have a ride ID. Proceeding with GPX simulation...');
  }
  
  console.log('✅ GPX simulation starting with', gpxPoints.length, 'points');
  console.log('💾 Current localStorage state:', localStorage.getItem('motoLog_rideState'));
  
  rideRoute = gpxPoints.map(p => [p.lat, p.lon]);
  let pointIndex = 0;
  
  // Send all points to backend with delays
  const sendNextPoint = () => {
    if (pointIndex >= gpxPoints.length) {
      console.log('GPX simulation complete');
      showToast('GPX simulation complete! ' + gpxPoints.length + ' points added.', 'success');
      return;
    }
    
    const point = gpxPoints[pointIndex];
    const timestamp = Math.floor(Date.now() / 1000) + pointIndex;
    
    fetch('/api/ride/add-gps-point', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ride_id: currentRideId,
        latitude: point.lat,
        longitude: point.lon,
        speed: 25 + Math.random() * 15,  // Simulate 25-40 km/h
        altitude: point.ele || 0,
        timestamp: timestamp
      })
    })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        // Add to local tracking
        ridePoints.push({
          latitude: point.lat,
          longitude: point.lon,
          speed: 30,
          timestamp: timestamp
        });
        
        updateMapRoute();
        updateStats();
        
        pointIndex++;
        // Send next point after 50ms
        setTimeout(sendNextPoint, 50);
      } else {
        console.error('Error adding GPX point:', data.error);
      }
    })
    .catch(e => console.error('Error sending GPX point:', e));
  };
  
  sendNextPoint();
}

// Haversine distance formula (returns km)
function haversine(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
            Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

function toRad(deg) {
  return deg * (Math.PI / 180);
}

// Initialize on page load
window.addEventListener('DOMContentLoaded', () => {
  restoreState();
  initMap();
  
  // Update UI based on restored state - but only if there's actually a recording happening
  // Check if currentRideId is valid (> 0) and isRecording is true
  if (currentRideId && currentRideId > 0 && isRecording) {
    console.log('🔄 Page reloaded with active ride. Restoring UI...');
    document.getElementById('status').textContent = '🔴 Recording...';
    document.getElementById('status').className = 'track-status status-recording';
    document.getElementById('startBtn').disabled = true;
    document.getElementById('stopBtn').disabled = false;
    document.getElementById('bikeSelect').disabled = true;
  } else {
    // Clear any stale state
    clearState();
    document.getElementById('status').textContent = '⏸️ Ready to track';
    document.getElementById('status').className = 'track-status status-idle';
    document.getElementById('startBtn').disabled = false;
    document.getElementById('stopBtn').disabled = true;
    document.getElementById('bikeSelect').disabled = false;
  }
});

// Add file preview functionality
document.getElementById('ridePhotos').addEventListener('change', function(e) {
  const files = e.target.files;
  const preview = document.getElementById('photoPreview');
  
  if (files && files.length > 0) {
    const fileNames = Array.from(files).map(file => file.name);
    preview.textContent = fileNames.join(', ');
    preview.style.color = 'var(--text)';
  } else {
    preview.textContent = '';
  }
});