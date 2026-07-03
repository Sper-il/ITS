/*
* nav_app.js. Wires the full-screen navigation mode.
*/
const NavApp = (() => {
  function $(s) { return document.querySelector(s); }

  let map = null;
  let userMarker = null;
  let routeData = null;
  let currentCoordIndex = 0;
  
  let watchId = null;
  let isAutoCenter = true;
  let isHeadingUp = false;
  let isVoiceEnabled = true;
  let lastAnnouncedManeuver = "";
  let lastHeading = 0;
  let simInterval = null;
  let lastPos = null;

  // Bearing calculation
  function bearingDeg(lat1, lon1, lat2, lon2) {
    const phi1 = lat1 * Math.PI / 180;
    const phi2 = lat2 * Math.PI / 180;
    const dl = (lon2 - lon1) * Math.PI / 180;
    const x = Math.sin(dl) * Math.cos(phi2);
    const y = Math.cos(phi1) * Math.sin(phi2) - Math.sin(phi1) * Math.cos(phi2) * Math.cos(dl);
    return (Math.atan2(x, y) * 180 / Math.PI + 360) % 360;
  }

  function getManeuverIcon(diff) {
    const ad = Math.abs(diff);
    if (ad < 18) return "straight";
    if (ad < 60) return diff > 0 ? "turn_slight_right" : "turn_slight_left";
    if (ad < 120) return diff > 0 ? "turn_right" : "turn_left";
    return diff > 0 ? "u_turn_right" : "u_turn_left";
  }

  function getManeuverText(diff, nextStreet) {
    const ad = Math.abs(diff);
    let action = "Đi thẳng";
    if (ad >= 18 && ad < 60) action = diff > 0 ? "Rẽ nhẹ phải" : "Rẽ nhẹ trái";
    else if (ad >= 60 && ad < 120) action = diff > 0 ? "Rẽ phải" : "Rẽ trái";
    else if (ad >= 120) action = diff > 0 ? "Quay đầu phải" : "Quay đầu trái";
    return `${action} vào ${nextStreet || "đường tiếp theo"}`;
  }

  // Voice Guidance
  function speak(text) {
    if (!isVoiceEnabled || !("speechSynthesis" in window)) return;
    if (text === lastAnnouncedManeuver) return; // avoid spam
    lastAnnouncedManeuver = text;
    
    // Stop previous
    window.speechSynthesis.cancel();
    
    const ut = new SpeechSynthesisUtterance(text);
    ut.lang = "vi-VN";
    ut.rate = 1.0;
    window.speechSynthesis.speak(ut);
  }

  // Draw the route with LOS colors
  function renderRoute(route) {
    if (!map) return;
    if (route.edges && route.edges.length) {
      route.edges.forEach(e => {
        if (e.lat1 == null) return;
        L.polyline([[e.lat1, e.lon1], [e.lat2, e.lon2]], {
          color: (typeof LOS_COLORS !== 'undefined' && LOS_COLORS[e.los]) || e.los_color || "#888",
          weight: 6, opacity: 0.9, lineCap: "round", lineJoin: "round",
        }).addTo(map);
      });
    } else {
      const latlngs = route.geometry.map(([la, lo]) => [la, lo]);
      L.polyline(latlngs, { color: "#2563eb", weight: 6, opacity: 0.9 }).addTo(map);
    }

    const dest = route.geometry[route.geometry.length - 1];
    L.marker(dest, {
      icon: L.divIcon({
        html: `<span class="material-symbols-outlined text-red-500 text-4xl" style="font-variation-settings: 'FILL' 1; text-shadow: 0 0 10px rgba(0,0,0,0.5);">location_on</span>`,
        className: "", iconSize: [36, 36], iconAnchor: [18, 36]
      })
    }).addTo(map);
  }

  function distance(lat1, lon1, lat2, lon2) {
    const p = 0.017453292519943295;
    const c = Math.cos;
    const a = 0.5 - c((lat2 - lat1) * p)/2 + 
            c(lat1 * p) * c(lat2 * p) * 
            (1 - c((lon2 - lon1) * p))/2;
    return 12742 * Math.asin(Math.sqrt(a)); // km
  }

  function updateUI() {
    if (!routeData) return;
    
    const geom = routeData.geometry;
    const totalDistKm = routeData.total_distance_m / 1000;
    
    let distCoveredKm = 0;
    for (let i = 0; i < currentCoordIndex; i++) {
      distCoveredKm += distance(geom[i][0], geom[i][1], geom[i+1][0], geom[i+1][1]);
    }
    
    let distRemKm = totalDistKm - distCoveredKm;
    if (distRemKm < 0) distRemKm = 0;
    
    let compPct = (distCoveredKm / totalDistKm) * 100;
    if (compPct > 100) compPct = 100;

    const speedMps = routeData.total_distance_m / routeData.total_travel_time_s;
    let remTimeS = (distRemKm * 1000) / speedMps;
    let remMin = Math.ceil(remTimeS / 60);

    // Update DOM
    if ($("#nav-dist-rem")) $("#nav-dist-rem").textContent = distRemKm.toFixed(1);
    if ($("#nav-eta")) $("#nav-eta").textContent = remMin;
    if ($("#nav-comp-text")) $("#nav-comp-text").textContent = Math.round(compPct) + "%";
    if ($("#nav-comp-bar")) $("#nav-comp-bar").style.width = compPct + "%";

    // Maneuver
    let nextEdgeIndex = Math.floor((currentCoordIndex / geom.length) * (routeData.edges?.length || 1));
    if (routeData.edges && nextEdgeIndex >= routeData.edges.length) nextEdgeIndex = routeData.edges.length - 1;
    
    const e = routeData.edges ? routeData.edges[nextEdgeIndex] : null;
    const next = routeData.edges ? routeData.edges[nextEdgeIndex + 1] : null;
    
    let maneuverText = "Đi thẳng";
    let icon = "straight";
    let speakText = "";
    
    if (currentCoordIndex >= geom.length - 1) {
      maneuverText = "Bạn đã đến nơi!";
      icon = "flag";
      speakText = maneuverText;
      setBannerState("off", maneuverText, icon);
    } else if (next && e && e.lat2 != null && next.lat1 != null) {
      const b_out = bearingDeg(e.lat2, e.lon2, next.lat1, next.lon1);
      const b_in  = bearingDeg(e.lat1 || e.lat2, e.lon1 || e.lon2, e.lat2, e.lon2);
      let diff = ((b_out - b_in + 540) % 360) - 180;
      icon = getManeuverIcon(diff);
      maneuverText = getManeuverText(diff, next.street);
      
      const distStr = e.length_m < 1000 ? Math.round(e.length_m) + " mét" : (e.length_m / 1000).toFixed(1) + " ki lô mét";
      speakText = `Trong ${distStr} nữa, ${maneuverText}`;
      
      setBannerState("default", maneuverText, icon, e.length_m);
    } else {
      maneuverText = `Đi thẳng trên ${e?.street || "đường hiện tại"}`;
      setBannerState("default", maneuverText, "straight", e?.length_m);
      speakText = maneuverText;
    }

    if (e && e.length_m < 300) { // Only announce if close
        speak(speakText);
    }
    
    const d = new Date();
    if ($("#nav-clock")) $("#nav-clock").textContent = d.getHours().toString().padStart(2, '0') + ":" + d.getMinutes().toString().padStart(2, '0');
  }

  function setBannerState(state, text, iconStr, distToNext) {
    const banner = $("#nav-banner");
    if (!banner) return;
    const colors = {
      default:  "#1565C0",
      warning:  "#E65100",
      danger:   "#B71C1C",
      off:      "#1B5E20",
    };
    banner.style.background = colors[state] || colors.default;
    
    if (text && $("#nav-maneuver")) $("#nav-maneuver").textContent = text;
    if (iconStr && $("#nav-icon")) $("#nav-icon").textContent = iconStr;
    
    if ($("#nav-dist-next")) {
        if (distToNext !== undefined) {
          $("#nav-dist-next").textContent = Math.round(distToNext) + "m";
        } else {
          $("#nav-dist-next").textContent = "";
        }
    }
  }

  // Find closest point index
  function findClosestIndex(lat, lon, geom) {
    let minDist = Infinity;
    let minIdx = 0;
    for (let i = 0; i < geom.length; i++) {
      const d = distance(lat, lon, geom[i][0], geom[i][1]);
      if (d < minDist) {
        minDist = d;
        minIdx = i;
      }
    }
    return { index: minIdx, dist: minDist };
  }

  function handlePositionUpdate(pos) {
    if (!routeData) return;
    lastPos = pos;
    const lat = pos.coords.latitude;
    const lon = pos.coords.longitude;
    
    // Update marker
    userMarker.setLatLng([lat, lon]);
    
    // Auto center map if not free roaming
    if (isAutoCenter) {
      map.panTo([lat, lon], { animate: true, duration: 1.0 });
    }

    // Speedometer
    let speedKmh = 0;
    if (pos.coords.speed != null) {
      speedKmh = Math.round(pos.coords.speed * 3.6);
    } else {
      // simulate speed if null for demo purposes
      speedKmh = Math.round(Math.random() * 5 + 40); 
    }
    
    if ($("#nav-speed")) $("#nav-speed").textContent = speedKmh;
    const speedBox = $("#speedometer");
    if (speedBox) {
      if (speedKmh > 60) {
        speedBox.classList.remove("border-outline-variant/30");
        speedBox.classList.add("border-red-500", "text-red-500");
      } else {
        speedBox.classList.add("border-outline-variant/30");
        speedBox.classList.remove("border-red-500", "text-red-500");
      }
    }

    // Heading/Rotation
    // Heading/Rotation
    let heading = pos.coords.heading;
    if (heading == null) {
        // calculate from last pos
        const geom = routeData.geometry;
        if (currentCoordIndex < geom.length - 1) {
            heading = bearingDeg(lat, lon, geom[currentCoordIndex+1][0], geom[currentCoordIndex+1][1]);
        } else {
            heading = lastHeading;
        }
    }
    lastHeading = heading;
        
    const container = $("#map-container");
    if (container) {
        if (isHeadingUp) {
            container.style.transition = "transform 0.5s ease-in-out";
            container.style.transformOrigin = "center center";
            // Create a 3D tilt effect: perspective + pitch + heading + zoom compensation + move marker lower
            container.style.transform = `perspective(1200px) rotateX(55deg) rotateZ(${-heading}deg) scale(1.8) translateY(15%)`;
        } else {
            container.style.transition = "transform 0.5s ease-in-out";
            container.style.transformOrigin = "center center";
            container.style.transform = `perspective(1200px) rotateX(0deg) rotateZ(0deg) scale(1) translateY(0%)`;
        }
    }
        
    // Marker rotation
    const markerEl = userMarker.getElement();
    if (markerEl) {
        const inner = markerEl.querySelector('#user-arrow-container');
        if (inner) {
            inner.style.transform = `rotateZ(${heading}deg)`;
        }
    }

    // Snap to route
    const geom = routeData.geometry;
    const closest = findClosestIndex(lat, lon, geom);
    currentCoordIndex = closest.index;

    // Check off-route ( > 50m)
    if (closest.dist > 0.05) {
      setBannerState("danger", "Bạn đã lệch tuyến đường!", "report_problem");
      const distToDest = distance(lat, lon, geom[geom.length-1][0], geom[geom.length-1][1]);
      if ($("#nav-dist-rem")) $("#nav-dist-rem").textContent = distToDest.toFixed(1);
    } else {
      updateUI();
    }
  }

  function toggleSimulation(enabled) {
    if (watchId !== null) {
      navigator.geolocation.clearWatch(watchId);
      watchId = null;
    }
    if (simInterval !== null) {
      clearInterval(simInterval);
      simInterval = null;
    }

    if (enabled) {
      if ("geolocation" in navigator) {
        watchId = navigator.geolocation.watchPosition(
          handlePositionUpdate, 
          (err) => {
            console.error("GPS error:", err);
            setBannerState("warning", "Vui lòng cấp quyền vị trí GPS", "gps_off");
          }, 
          { enableHighAccuracy: true, maximumAge: 10000, timeout: 5000 }
        );
      } else {
        setBannerState("danger", "Trình duyệt không hỗ trợ GPS", "gps_off");
      }
    }
  }

  function init() {
    try {
      const raw = sessionStorage.getItem("its_route_result");
      if (raw) {
        const parsed = JSON.parse(raw);
        routeData = parsed.routes[parsed.selectedIdx];
      }
    } catch(e) {}

    if (!routeData || !routeData.geometry) return;

    const startLoc = routeData.geometry[0];
    map = L.map('map', {
      zoomControl: false,
      attributionControl: false
    }).setView(startLoc, 17);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { maxZoom: 19 }).addTo(map);

    renderRoute(routeData);

    const userIcon = L.divIcon({
      className: '',
      html: `<div id="user-arrow-container" style="transition: transform 0.5s ease-out; transform-origin: center; display: flex; align-items: center; justify-content: center; width: 48px; height: 48px;">
               <svg width="36" height="36" viewBox="0 0 24 24" fill="#3b82f6" stroke="white" stroke-width="2.5" style="filter: drop-shadow(0px 4px 8px rgba(0,0,0,0.6));">
                 <path d="M12 2L21 21L12 17L3 21L12 2Z" stroke-linejoin="round" stroke-linecap="round"/>
               </svg>
             </div>`,
      iconSize: [48, 48], iconAnchor: [24, 24]
    });
    userMarker = L.marker(startLoc, { icon: userIcon, zIndexOffset: 1000 }).addTo(map);

    updateUI();

    // Wire Free Roam logic
    map.on('dragstart', () => {
      isAutoCenter = false;
      const recenterBtn = $("#recenterBtn");
      if (recenterBtn) {
          recenterBtn.classList.remove("text-primary");
          recenterBtn.classList.add("text-white", "animate-pulse");
      }
    });

    $("#recenterBtn")?.addEventListener("click", () => {
      isAutoCenter = true;
      const recenterBtn = $("#recenterBtn");
      if (recenterBtn) {
          recenterBtn.classList.add("text-primary");
          recenterBtn.classList.remove("text-white", "animate-pulse");
      }
      if (lastPos) {
        map.setView([lastPos.coords.latitude, lastPos.coords.longitude], 17);
        handlePositionUpdate(lastPos);
      } else if (routeData && routeData.geometry[currentCoordIndex]) {
        map.setView(routeData.geometry[currentCoordIndex], 17);
        handlePositionUpdate({coords: {latitude: routeData.geometry[currentCoordIndex][0], longitude: routeData.geometry[currentCoordIndex][1], speed: null, heading: lastHeading}});
      }
    });

    $("#compassBtn")?.addEventListener("click", () => {
        isHeadingUp = !isHeadingUp;
        const compassBtn = $("#compassBtn");
        if (isHeadingUp) {
            compassBtn.classList.add("text-primary");
            compassBtn.classList.remove("text-white");
        } else {
            compassBtn.classList.remove("text-primary");
            compassBtn.classList.add("text-white");
        }
        // Force update map rotation
        if (lastPos) {
           handlePositionUpdate(lastPos);
        } else if (routeData && routeData.geometry[currentCoordIndex]) {
           const [lat, lon] = routeData.geometry[currentCoordIndex];
           handlePositionUpdate({coords: {latitude: lat, longitude: lon, speed: null, heading: lastHeading}});
        }
    });

    // Wire Voice Toggle
    const allBtns = document.querySelectorAll('button .material-symbols-outlined');
    let volBtn = null;
    allBtns.forEach(b => { if(b.textContent.includes("volume")) volBtn = b.parentElement; });
    
    if (volBtn) {
        volBtn.addEventListener("click", () => {
            isVoiceEnabled = !isVoiceEnabled;
            const icon = volBtn.querySelector("span");
            icon.textContent = isVoiceEnabled ? "volume_up" : "volume_off";
            if (isVoiceEnabled) speak("Đã bật dẫn đường bằng giọng nói.");
        });
    }

    $("#exit-btn")?.addEventListener("click", () => window.location.href = "/routing");
    $("#zoomInBtn")?.addEventListener("click", () => map.zoomIn());
    $("#zoomOutBtn")?.addEventListener("click", () => map.zoomOut());

    $("#auto-next-toggle")?.addEventListener("change", (e) => toggleSimulation(e.target.checked));
    
    if ($("#auto-next-toggle")?.checked) {
      toggleSimulation(true);
    }
  }

  return { init };
})();

// jQuery-like contains selector for the volume button binding
HTMLElement.prototype.containsText = function(text) { return this.innerText.includes(text); }

document.addEventListener("DOMContentLoaded", NavApp.init);
