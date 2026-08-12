import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { HardDrive, Camera, AlertTriangle, Activity } from 'lucide-react';

import L from 'leaflet';
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({ iconUrl: icon, shadowUrl: iconShadow, iconSize: [25, 41], iconAnchor: [12, 41] });
L.Marker.prototype.options.icon = DefaultIcon;

export default function App() {
  const [territory, setTerritory] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [stats, setStats] = useState({
    active_cameras: 142,
    identified_tigers: 0,
    storage_saved_mb: 0.0,
    quarantined_images: 0
  });
  const [uploadStatus, setUploadStatus] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const API_BASE = "http://127.0.0.1:8000";

  // Fetch initial dynamic data on load
  const fetchDashboardData = async () => {
    try {
      const terrRes = await axios.get(`${API_BASE}/territory/T-001`);
      if (terrRes.data.status === "calculated") setTerritory(terrRes.data);

      const statsRes = await axios.get(`${API_BASE}/system_stats`);
      setStats(statsRes.data);
    } catch (error) {
      console.error("Error fetching data:", error);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    // Start with a clean, dynamic system alert
    setAlerts([{ 
      id: Date.now(), 
      type: "SYSTEM", 
      msg: "Command Center online. AI Models loaded into memory.", 
      time: new Date().toLocaleTimeString() 
    }]);
  }, []);

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setIsUploading(true);
    setUploadStatus(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await axios.post(`${API_BASE}/upload_camera_trap`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      setUploadStatus(response.data);

      // --- DYNAMIC ALERTS GENERATION ---
      const newTime = new Date().toLocaleTimeString();
      let newAlert = null;

      if (response.data.status === 'success') {
        newAlert = {
          id: Date.now(),
          type: "NORMAL",
          msg: `📸 Match: ${response.data.tiger_id} identified (Score: ${response.data.distance_score}). ${response.data.message}`,
          time: newTime
        };
      } else if (response.data.status === 'quarantined') {
        newAlert = {
          id: Date.now(),
          type: "SYSTEM",
          msg: `🛡️ Triage Active: Blank image quarantined. Saved storage.`,
          time: newTime
        };
      }

      // Add the new alert to the top of the feed
      if (newAlert) {
        setAlerts(prevAlerts => [newAlert, ...prevAlerts]);
      }
      
      // Refresh the KPI numbers to reflect the new upload
      fetchDashboardData();

    } catch (error) {
      console.error("Upload failed", error);
      setUploadStatus({ status: "error", message: "Failed to connect to the backend API." });
    } finally {
      setIsUploading(false);
    }
  };

  // Calculate active alerts (just counting how many 'CRITICAL' alerts exist in the dynamic feed)
  const criticalAlertCount = alerts.filter(a => a.type === 'CRITICAL').length;

  return (
    <div className="min-h-screen p-6 bg-slate-900 font-sans">
      <header className="mb-8 border-b border-slate-700 pb-4">
        <h1 className="text-3xl font-bold text-emerald-400">Pench Wildlife Command Center</h1>
        <p className="text-slate-400">Automated Camera Trap Intelligence System</p>
      </header>

      {/* DYNAMIC KPI Cards Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-slate-800 p-4 rounded-lg border border-slate-700 flex items-center">
          <Camera className="text-blue-400 w-8 h-8 mr-4" />
          <div>
            <p className="text-slate-400 text-sm">Active Camera Traps</p>
            <p className="text-2xl font-bold">{stats.active_cameras}</p>
          </div>
        </div>
        <div className="bg-slate-800 p-4 rounded-lg border border-slate-700 flex items-center">
          <Activity className="text-emerald-400 w-8 h-8 mr-4" />
          <div>
            <p className="text-slate-400 text-sm">Identified Tigers</p>
            <p className="text-2xl font-bold">{stats.identified_tigers}</p>
          </div>
        </div>
        <div className="bg-slate-800 p-4 rounded-lg border border-slate-700 flex items-center">
          <HardDrive className="text-purple-400 w-8 h-8 mr-4" />
          <div>
            <p className="text-slate-400 text-sm">Storage Saved (MB)</p>
            <p className="text-2xl font-bold">{stats.storage_saved_mb}</p>
          </div>
        </div>
        <div className={`bg-slate-800 p-4 rounded-lg border flex items-center ${criticalAlertCount > 0 ? 'border-red-900' : 'border-slate-700'}`}>
          <AlertTriangle className={`${criticalAlertCount > 0 ? 'text-red-500' : 'text-slate-500'} w-8 h-8 mr-4`} />
          <div>
            <p className="text-slate-400 text-sm">Active Alerts</p>
            <p className={`text-2xl font-bold ${criticalAlertCount > 0 ? 'text-red-500' : 'text-slate-300'}`}>
              {criticalAlertCount}
            </p>
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Map Section */}
        <div className="lg:col-span-2 bg-slate-800 rounded-lg border border-slate-700 overflow-hidden h-[500px] flex flex-col">
          <div className="p-3 bg-slate-800 border-b border-slate-700 flex justify-between items-center">
            <h2 className="font-semibold text-emerald-400">Live Territory Map</h2>
            <span className="text-xs bg-slate-700 px-2 py-1 rounded">UTM Zone 44N Projected</span>
          </div>
          
          <div className="flex-grow bg-slate-900 relative">
            <MapContainer center={[21.655, 79.215]} zoom={13} style={{ height: '100%', width: '100%', zIndex: 0 }}>
              <TileLayer
                url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                attribution='&copy; <a href="https://carto.com/">Carto</a>'
              />
              {territory && territory.centroid && (
                <Marker position={[territory.centroid.lat, territory.centroid.lon]}>
                  <Popup>
                    <strong className="text-slate-900">Tiger {territory.tiger_id} Core</strong><br/>
                    Area: {territory.core_area_sqkm} sq km
                  </Popup>
                </Marker>
              )}
            </MapContainer>
          </div>
        </div>

        {/* DYNAMIC Alerts Sidebar */}
        <div className="bg-slate-800 rounded-lg border border-slate-700 flex flex-col h-[500px]">
          <div className="p-4 border-b border-slate-700">
            <h2 className="font-semibold text-emerald-400">Intelligence Feed</h2>
          </div>
          <div className="p-4 overflow-y-auto flex-grow space-y-4">
            {alerts.map((alert) => (
              <div key={alert.id} className={`p-4 rounded-md border ${
                alert.type === 'CRITICAL' ? 'bg-red-900/20 border-red-700' 
                : alert.type === 'SYSTEM' ? 'bg-slate-800 border-slate-600'
                : 'bg-slate-700/50 border-slate-600'
              }`}>
                <div className="flex justify-between items-start mb-2">
                  <span className={`text-xs font-bold px-2 py-1 rounded ${
                    alert.type === 'CRITICAL' ? 'bg-red-600 text-white' 
                    : alert.type === 'SYSTEM' ? 'bg-slate-600 text-slate-300'
                    : 'bg-emerald-600 text-white'
                  }`}>
                    {alert.type}
                  </span>
                  <span className="text-xs text-slate-400">{alert.time}</span>
                </div>
                <p className="text-sm text-slate-200">{alert.msg}</p>
                {alert.type === 'CRITICAL' && (
                  <button className="mt-3 text-xs bg-red-600 hover:bg-red-500 text-white px-3 py-1 rounded transition">
                    Dispatch Team
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      </div> 

      {/* Camera Trap Upload Section */}
      <div className="mt-6 bg-slate-800 rounded-lg border border-slate-700 p-6">
        <h2 className="font-semibold text-emerald-400 mb-4 flex items-center gap-2">
          <Camera size={20} /> Live Camera Trap Feed (Test Upload)
        </h2>
        
        <div className="flex flex-wrap items-center gap-4">
          <label className={`cursor-pointer px-4 py-2 rounded font-medium transition ${
            isUploading ? 'bg-slate-600 text-slate-400' : 'bg-emerald-600 hover:bg-emerald-500 text-white'
          }`}>
            {isUploading ? "Processing AI Pipeline..." : "Upload Camera Image"}
            <input type="file" className="hidden" onChange={handleFileUpload} accept="image/*" disabled={isUploading} />
          </label>

          {uploadStatus && (
            <div className={`px-4 py-2 rounded border ${
              uploadStatus.status === 'success' ? 'bg-emerald-900/30 border-emerald-700 text-emerald-300' 
              : uploadStatus.status === 'quarantined' ? 'bg-yellow-900/30 border-yellow-700 text-yellow-300'
              : 'bg-red-900/30 border-red-700 text-red-300'
            }`}>
              {uploadStatus.status === 'success' ? (
                <span><strong>🐯 Match Found:</strong> {uploadStatus.tiger_id} (Distance Score: {uploadStatus.distance_score}) - {uploadStatus.message}</span>
              ) : uploadStatus.status === 'quarantined' ? (
                <span><strong>🛡️ Quarantined:</strong> {uploadStatus.message}</span>
              ) : (
                <span><strong>❌ Error:</strong> {uploadStatus.message}</span>
              )}
            </div>
          )}
        </div>
      </div>
      
    </div>
  );
}