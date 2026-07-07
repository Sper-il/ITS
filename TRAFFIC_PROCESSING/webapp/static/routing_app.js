/*
* routing_app.js. Wires the Routing tab (both empty + found states) to /api/route.
*
* Behaviour:
*  - Populate "Tuyến nhanh" preset dropdown from /api/route/presets
*  - On Tìm đường click, call /api/route/find with selected start + end
*  - Re-render the results drawer + map polyline with the returned routes
*/
const RoutingApp = (() => {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  // ── State ──
  const state = {
    start: null,    // { label, lat, lon }
    end:   null,
    waypoints: [],   // [{ label, lat, lon }]   intermediate stops (fix #6)
    vehicle: "car",
    routes: [],
    selectedIdx: 0,   // index in the visible (non-shortest) route array
  };

  // ── Distance / time formatters (defensive fallback if backend omits display fields) ──
  function formatDist(m) {
    if (m == null || isNaN(m)) return "—";
    if (m >= 1000) return (m / 1000).toFixed(1) + " km";
    return Math.round(m) + " m";
  }
  function formatTime(s) {
    if (s == null || isNaN(s) || s <= 0) return "—";
    s = Math.round(s);
    if (s < 60)    return s + "s";
    if (s < 3600)  return Math.floor(s / 60) + "m";
    return Math.floor(s / 3600) + "h " + Math.floor((s % 3600) / 60) + "m";
  }

  // ── Floating chip sync (empty state) ──
  function syncFloatingChips() {
    const fs = $("#floating-start");
    const fe = $("#floating-end");
    if (fs) fs.textContent = state.start?.label || "Điểm xuất phát...";
    if (fe) fe.textContent = state.end?.label   || "Điểm đến...";
  }

  // ── "Use current location" button (empty state) ──
  function wireUseCurrentLocation() {
    const btn = $("#use-current-location-btn");
    if (!btn) return;
    btn.addEventListener("click", () => {
      if (!navigator.geolocation) {
        alert("Trình duyệt không hỗ trợ định vị.");
        return;
      }
      const orig = btn.innerHTML;
      btn.innerHTML = '<span class="material-symbols-outlined text-sm animate-spin">progress_activity</span> Đang lấy vị trí...';
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          btn.innerHTML = orig;
          state.start = {
            label: "Vị trí của tôi",
            lat: pos.coords.latitude,
            lon: pos.coords.longitude,
          };
          const inp = $("#input-start");
          if (inp) inp.value = state.start.label;
          renderChips();
          syncFloatingChips();
        },
        (err) => {
          btn.innerHTML = orig;
          alert("Không lấy được vị trí: " + err.message);
        },
        { enableHighAccuracy: true, timeout: 10000 }
      );
    });
  }

  // ── Custom SVG icon by name (anti-emoji) ──
  const ICONS = {
    play:      `<svg width="14" height="14" viewBox="0 0 24 24" fill="white"><polygon points="6 4 20 12 6 20 6 4"/></svg>`,
    flag:      `<svg width="14" height="14" viewBox="0 0 24 24" fill="white"><polygon points="5 3 19 12 5 21 5 3"/></svg>`,
    swap:      `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>`,
    search:    `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>`,
    car:       `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M5 17h14l-1.5-7H6.5L5 17z"/><circle cx="7" cy="17" r="2"/><circle cx="17" cy="17" r="2"/></svg>`,
    gps:       `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg>`,
    check:     `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="20 6 9 17 4 12"/></svg>`,
    warning:   `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/></svg>`,
    close:     `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
  };

  // ── Presets dropdown ──
  // ── Presets autocomplete ──
  let _presets = [];

  async function loadPresets() {
    const data = await API.get("/api/route/presets");
    _presets = data.presets.filter(p => !p.is_header && p.lat != null && p.lon != null);
  }

  function showAutocomplete(inputEl, which, wpIdx) {
    // Remove any existing dropdown
    $$(".preset-dropdown").forEach(d => d.remove());
    const query = inputEl.value.trim().toLowerCase();
    const matches = query
      ? _presets.filter(p => p.label.toLowerCase().includes(query))
      : _presets.slice(0, 15);
    if (!matches.length) return;

    const dropdown = document.createElement("div");
    dropdown.className = "preset-dropdown";
    dropdown.style.cssText = `
      position:absolute;top:100%;left:0;right:0;z-index:100;
      max-height:240px;overflow-y:auto;
      background:rgba(18,33,49,0.95);backdrop-filter:blur(12px);
      border:1px solid rgba(255,255,255,0.1);border-radius:8px;
      margin-top:4px;box-shadow:0 8px 32px rgba(0,0,0,0.4);
    `;
    matches.forEach(p => {
      const item = document.createElement("div");
      item.style.cssText = `padding:10px 14px;cursor:pointer;font-size:13px;color:#d4e4fa;transition:background 0.15s;`;
      item.textContent = p.label;
      item.addEventListener("mouseenter", () => item.style.background = "rgba(37,99,235,0.15)");
      item.addEventListener("mouseleave", () => item.style.background = "transparent");
      item.addEventListener("mousedown", (e) => {
        e.preventDefault();
        const point = { label: p.label, lat: p.lat, lon: p.lon };
        if (which === "start") state.start = point;
        else if (which === "end") state.end = point;
        else if (which === "waypoint" && wpIdx != null && state.waypoints[wpIdx]) {
          state.waypoints[wpIdx] = point;
        }
        inputEl.value = p.label;
        dropdown.remove();
        renderChips();
        if (which === "waypoint") renderWaypoints();
      });
      dropdown.appendChild(item);
    });
    inputEl.parentElement.style.position = "relative";
    inputEl.parentElement.appendChild(dropdown);
  }

  function pickPreset(which) {
    // Legacy fallback — now handled by autocomplete
    const input = which === "start" ? $("#input-start") : $("#input-end");
    if (input) input.focus();
  }

  function renderChips() {
    const startInput = $("#input-start");
    const endInput = $("#input-end");
    if (startInput && state.start) {
      startInput.value = state.start.label;
      startInput.style.color = "#b4c5ff";
    }
    if (endInput && state.end) {
      endInput.value = state.end.label;
      endInput.style.color = "#b4c5ff";
    }
    const goBtn = $("#find-route-btn");
    if (goBtn) goBtn.disabled = !(state.start && state.end);
    syncFloatingChips();
    window.dispatchEvent(new CustomEvent("routing-state-changed"));
  }

  // ── Waypoint management (fix #6) ──
  function renderWaypoints() {
    const container = $("#waypoints-container");
    if (!container) return;
    container.innerHTML = "";
    state.waypoints.forEach((wp, idx) => {
      const row = document.createElement("div");
      row.className = "relative group";
      row.innerHTML = `
        <label class="text-[10px] font-bold text-tertiary uppercase absolute -top-2 left-3 px-1 bg-surface-container z-10">Điểm dừng ${idx + 1}</label>
        <div class="flex gap-2">
          <div class="flex-1 bg-surface-container-low border border-outline-variant/20 rounded-lg p-3 flex items-center gap-3 group-focus-within:border-primary/50 transition-all">
            <span class="material-symbols-outlined text-tertiary text-sm">flag</span>
            <input class="wp-input bg-transparent border-none p-0 text-sm text-on-surface placeholder:text-outline-variant/60 focus:ring-0 w-full" placeholder="Điểm dừng ${idx + 1}..." type="text" value="${wp.label || ''}"/>
          </div>
          <button class="wp-del w-10 h-[46px] bg-surface-container-low border border-outline-variant/20 rounded-lg flex items-center justify-center hover:bg-error/20 transition-colors" title="Xóa điểm dừng">
            <span class="material-symbols-outlined text-on-surface-variant">remove</span>
          </button>
        </div>
      `;
      const inp = row.querySelector(".wp-input");
      inp.addEventListener("input", () => {
        wp.label = inp.value;
      });
      inp.addEventListener("focus", () => showAutocomplete(inp, "waypoint", idx));
      inp.addEventListener("blur", () => setTimeout(() => $$(".preset-dropdown").forEach(d => d.remove()), 200));
      row.querySelector(".wp-del").addEventListener("click", () => {
        state.waypoints.splice(idx, 1);
        renderWaypoints();
      });
      container.appendChild(row);
    });
  }

  function wireAddWaypoint() {
    const btn = $("#add-waypoint-btn");
    if (!btn) return;
    btn.addEventListener("click", () => {
      if (state.waypoints.length >= 5) {
        alert("Tối đa 5 điểm dừng.");
        return;
      }
      state.waypoints.push({ label: "", lat: null, lon: null });
      renderWaypoints();
    });
  }

  // ── Fetch routes ──
  async function findRoute() {
    console.log("[findRoute] Called. state.start:", state.start, "state.end:", state.end);
    if (!state.start || !state.end) {
      console.warn("[findRoute] Missing start or end point!");
      alert("Vui lòng chọn điểm xuất phát và điểm đến.");
      return;
    }
    try {
      // If user added waypoints, use the multi-leg endpoint (fix #6).
      if (state.waypoints.length && state.waypoints.every(w => w.lat != null)) {
        const wps = [state.start, ...state.waypoints, state.end];
        const out = await API.post("/api/route/multi-leg", {
          waypoints: wps.map(w => ({ lat: w.lat, lon: w.lon, label: w.label })),
          vehicle: state.vehicle,
        });
        if (out.error) {
          alert(out.error);
          return;
        }
        // Render the concatenated leg geometries as a single polyline.
        const allEdges = out.legs.flatMap(l => l.edges || []);
        const allGeo = out.legs.flatMap(l => l.geometry || []);
        // Tally LOS distribution across all legs
        const losDist = { A: 0, B: 0, C: 0, D: 0, E: 0, F: 0 };
        allEdges.forEach(e => {
          const L = e.los || "B";
          losDist[L] = (losDist[L] || 0) + 1;
        });
        const avgConf = allEdges.length
          ? allEdges.reduce((a, e) => a + (e.travel_time_s || 0), 0) / Math.max(allEdges.length, 1)
          : 0;
        const synthetic = {
          strategy: "Multi-stop",
          total_distance_m: out.total_distance_m,
          total_distance_display: out.total_distance_display,
          total_travel_time_s: out.total_travel_time_s,
          total_travel_time_str: out.total_travel_time_str,
          avg_confidence: 0.7,
          los_distribution: losDist,
          geometry: allGeo,
          edges: allEdges,
        };
        state.routes = [synthetic];
        state.selectedIdx = 0;

        // Save route data to sessionStorage for the found page
        try {
          sessionStorage.setItem("its_route_result", JSON.stringify({
            start: state.start,
            end: state.end,
            vehicle: state.vehicle,
            routes: state.routes,
            selectedIdx: state.selectedIdx,
          }));
        } catch(ex) {}

        // Display inline instead of redirecting
        const emptyMsg = document.getElementById("empty-state-msg");
        const resPanel = document.getElementById("results-container");
        if (emptyMsg) emptyMsg.style.display = "none";
        if (resPanel) {
          resPanel.classList.remove("hidden");
          resPanel.classList.add("flex");
        }
        
        if (window.RoutingApp && typeof window.RoutingApp.renderDrawer === "function") {
          window.RoutingApp.renderDrawer();
        } else if (typeof renderDrawer === "function") {
          renderDrawer();
        }
        window.dispatchEvent(new CustomEvent("route-found"));
        return;
      }

      const out = await API.post("/api/route/find", {
        start_lat: state.start.lat,
        start_lon: state.start.lon,
        end_lat: state.end.lat,
        end_lon: state.end.lon,
        vehicle: state.vehicle,
      });
      if (!out.routes || !out.routes.length) {
        const empty = $("#results-empty");
        if (empty) empty.style.display = "block";
        if (out.message) alert(out.message);
        return;
      }
      state.routes = out.routes;
      // Hide "Ngắn nhất" from map + selected default = first non-shortest
      const visible = state.routes.filter(r => r.strategy !== "Ngắn nhất");
      state.selectedIdx = 0;

      // Save route data to sessionStorage for the found page
      const selRoute = visible[state.selectedIdx] || state.routes[0];
      try {
        sessionStorage.setItem("its_route_result", JSON.stringify({
          start: state.start,
          end: state.end,
          vehicle: state.vehicle,
          routes: state.routes,
          selectedIdx: state.selectedIdx,
        }));
      } catch(ex) {}

      // Display inline instead of redirecting
      const emptyMsg = document.getElementById("empty-state-msg");
      const resPanel = document.getElementById("results-container");
      if (emptyMsg) emptyMsg.style.display = "none";
      if (resPanel) {
        resPanel.classList.remove("hidden");
        resPanel.classList.add("flex");
      }
      
      if (window.RoutingApp && typeof window.RoutingApp.renderDrawer === "function") {
        window.RoutingApp.renderDrawer();
      } else if (typeof renderDrawer === "function") {
        renderDrawer();
      }
      window.dispatchEvent(new CustomEvent("route-found"));
      return;
    } catch (ex) {
      console.error("findRoute error:", ex);
      alert("Lỗi khi tìm đường: " + ex.message);
    }
  }

  // ── Render map polylines on the SVG-like map background ──
  function renderMap() {
    const svg = $("#map-svg");
    if (!svg) return;
    // Wipe existing routes/markers
    $$(".route-poly, .route-marker, .route-active").forEach(e => e.remove());
    const visible = state.routes.filter(r => r.strategy !== "Ngắn nhất");

    // We use a simple equirectangular projection so the polyline fits
    // the SVG viewport (1200×700). For a real Leaflet integration
    // a future sprint is required; this gets the design intent across.
    const allLats = [];
    const allLons = [];
    state.routes.forEach(r => r.geometry.forEach(([la, lo]) => {
      allLats.push(la); allLons.push(lo);
    }));
    if (!allLats.length) return;
    const minLat = Math.min(...allLats), maxLat = Math.max(...allLats);
    const minLon = Math.min(...allLons), maxLon = Math.max(...allLons);
    const padLat = (maxLat - minLat) * 0.1;
    const padLon = (maxLon - minLon) * 0.1;
    function project(lat, lon) {
      const x = ((lon - (minLon - padLon)) / ((maxLon + padLon) - (minLon - padLon))) * 1200;
      const y = (1 - (lat - (minLat - padLat)) / ((maxLat + padLat) - (minLat - padLat))) * 600 + 50;
      return [x, y];
    }

    // Routes
    state.routes.forEach((r) => {
      const isVisible = r.strategy !== "Ngắn nhất";
      const isSelected = isVisible && visible[state.selectedIdx]?.strategy === r.strategy;
      const color = ROUTE_STRATEGY_COLORS[r.strategy] || "#888";
      const d = r.geometry.map(([la, lo]) => project(la, lo))
                     .map((p, i) => (i === 0 ? `M${p[0]} ${p[1]}` : `L${p[0]} ${p[1]}`))
                     .join(" ");
      const halo = document.createElementNS("http://www.w3.org/2000/svg", "path");
      halo.setAttribute("d", d);
      halo.setAttribute("stroke", "#ffffff");
      halo.setAttribute("fill", "none");
      halo.setAttribute("opacity", isSelected ? "0.85" : "0.4");
      halo.setAttribute("stroke-width", isSelected ? 10 : 6);
      halo.classList.add("route-poly");
      svg.appendChild(halo);

      // Per-edge LOS colors for the selected route only
      if (isSelected && r.edges?.length) {
        r.edges.forEach((e, i) => {
          let ax, ay, bx, by;
          if (e.lat1 && e.lon1 && e.lat2 && e.lon2) {
            [ax, ay] = project(e.lat1, e.lon1);
            [bx, by] = project(e.lat2, e.lon2);
          } else {
            // Fallback: use geometry points
            ax = ay = bx = by = null;
            const gi = i * 2;
            if (r.geometry[gi]) [ax, ay] = project(r.geometry[gi][0], r.geometry[gi][1]);
            if (r.geometry[gi + 1]) [bx, by] = project(r.geometry[gi + 1][0], r.geometry[gi + 1][1]);
          }
          if (ax == null) return;
          const seg = document.createElementNS("http://www.w3.org/2000/svg", "line");
          seg.setAttribute("x1", ax); seg.setAttribute("y1", ay);
          seg.setAttribute("x2", bx); seg.setAttribute("y2", by);
          seg.setAttribute("stroke", e.los_color);
          seg.setAttribute("stroke-width", 6);
          seg.setAttribute("stroke-linecap", "round");
          seg.setAttribute("opacity", "0.95");
          seg.classList.add("route-poly");
          const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
          title.textContent = `${e.street} · LOS ${e.los} · ${Math.round(e.length_m)}m`;
          seg.appendChild(title);
          svg.appendChild(seg);
        });
      } else {
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", d);
        path.setAttribute("stroke", color);
        path.setAttribute("fill", "none");
        path.setAttribute("opacity", isSelected ? "0.9" : "0.5");
        path.setAttribute("stroke-width", isSelected ? 6 : 4);
        path.classList.add("route-poly");
        svg.appendChild(path);
      }
    });

    // Start marker
    if (state.start) {
      const [sx, sy] = project(state.start.lat, state.start.lon);
      const m = document.createElementNS("http://www.w3.org/2000/svg", "g");
      m.classList.add("route-marker");
      m.innerHTML = `
        <circle cx="${sx}" cy="${sy}" r="16" fill="rgba(34,197,94,0.2)" class="pulse-ring"/>
        <circle cx="${sx}" cy="${sy}" r="8" fill="#22c55e"/>
      `;
      svg.appendChild(m);
    }
    // End marker
    if (state.end) {
      const [ex, ey] = project(state.end.lat, state.end.lon);
      const m = document.createElementNS("http://www.w3.org/2000/svg", "g");
      m.classList.add("route-marker");
      m.innerHTML = `
        <circle cx="${ex}" cy="${ey}" r="20" fill="rgba(239,68,68,0.2)" class="pulse-ring"/>
        <circle cx="${ex}" cy="${ey}" r="10" fill="#ef4444"/>
      `;
      svg.appendChild(m);
    }
  }

  // ── Render the results drawer below the map ──
  function renderDrawer() {
    const visible = state.routes.filter(r => r.strategy !== "Ngắn nhất");
    if (!visible.length) return;

    // Drawer header (selected strategy name + summary)
    const sel = visible[state.selectedIdx] || visible[0];
    const headerTitle = $("#drawer-strategy");
    if (headerTitle) headerTitle.textContent = sel.strategy;

    const distEl = $("#drawer-distance");
    const timeEl = $("#drawer-time");
    const confEl = $("#drawer-confidence");
    if (distEl) {
      distEl.textContent = sel.total_distance_display || formatDist(sel.total_distance_m);
      distEl.style.color = "#b4c5ff";
    }
    if (timeEl) {
      timeEl.textContent = sel.total_travel_time_str || formatTime(sel.total_travel_time_s);
      timeEl.style.color = "#b4c5ff";
    }
    if (confEl) {
      const conf = (sel.avg_confidence != null && !isNaN(sel.avg_confidence))
        ? (sel.avg_confidence * 100).toFixed(0) + "%"
        : "—";
      confEl.textContent = conf;
      confEl.style.color = "#b4c5ff";
    }

    // Route strategy chips (3 total, hide Ngắn nhất)
    const radio = $("#route-radio");
    if (radio) {
      radio.innerHTML = "";
      visible.forEach((r, i) => {
        const color = ROUTE_STRATEGY_COLORS[r.strategy] || "#888";
        const isActive = i === state.selectedIdx;
        const btn = document.createElement("button");
        btn.dataset.idx = String(i);
        btn.dataset.strategy = r.strategy;
        btn.className = `route-chip ${isActive ? 'active' : ''}`;
        btn.style.cssText = `
          padding:6px 12px;border-radius:8px;
          background:${isActive ? color + "22" : "transparent"};
          border:1px solid ${isActive ? color : "rgba(255,255,255,0.12)"};
          color:${isActive ? color : "inherit"};
          font-size:13px;font-weight:600;cursor:pointer;
          display:inline-flex;align-items:center;gap:6px;
        `;
        btn.innerHTML = `<span style="width:8px;height:8px;border-radius:50%;background:${color};"></span>${r.strategy}`;
        btn.addEventListener("click", () => {
          state.selectedIdx = i;
          renderMap();
          renderDrawer();
        });
        radio.appendChild(btn);
      });
    }

    // LOS distribution strip
    const strip = $("#los-strip");
    if (strip) {
      const total = Object.values(sel.los_distribution).reduce((a, b) => a + b, 0) || 1;
      strip.innerHTML = "";
      "ABCDEF".split("").forEach(L => {
        const c = sel.los_distribution[L] || 0;
        if (!c) return;
        const seg = document.createElement("div");
        seg.style.cssText = `flex:${c};background:${LOS_COLORS[L]};height:5px;`;
        seg.title = `LOS ${L} · ${c} edges`;
        strip.appendChild(seg);
      });
    }

    // LOS badges row
    const badges = $("#los-badges");
    if (badges) {
      badges.innerHTML = "";
      "ABCDEF".split("").forEach(L => {
        const c = sel.los_distribution[L] || 0;
        if (!c) return;
        const b = document.createElement("span");
        b.style.cssText = `
          padding:2px 8px;border-radius:6px;
          background:${LOS_COLORS[L]};color:#fff;
          font-size:11px;font-weight:700;letter-spacing:0.04em;
        `;
        b.textContent = `${L} × ${c}`;
        badges.appendChild(b);
      });
    }

    // Route comparison cards (3)
    const cards = $("#route-cards");
    if (cards) {
      cards.innerHTML = "";
      state.routes.forEach((r) => {
        const color = ROUTE_STRATEGY_COLORS[r.strategy] || "#888";
        const isActive = visible[state.selectedIdx]?.strategy === r.strategy;
        const card = document.createElement("div");
        card.style.cssText = `
          padding:14px 16px;border-radius:12px;
          background:${isActive ? "rgba(37,99,235,0.06)" : "transparent"};
          border:1px solid ${isActive ? "#2563eb" : "rgba(255,255,255,0.08)"};
        `;
        card.innerHTML = `
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
            <span style="width:8px;height:8px;border-radius:50%;background:${color};"></span>
            <span style="font-weight:600;font-size:14px;">${r.strategy}</span>
          </div>
          <div style="display:flex;gap:12px;">
            <div>
              <div style="font-size:18px;font-weight:700;">${r.total_distance_display || formatDist(r.total_distance_m)}</div>
              <div style="font-size:10px;text-transform:uppercase;letter-spacing:0.08em;color:rgba(255,255,255,0.5);">Khoảng cách</div>
            </div>
            <div>
              <div style="font-size:18px;font-weight:700;">${r.total_travel_time_str || formatTime(r.total_travel_time_s)}</div>
              <div style="font-size:10px;text-transform:uppercase;letter-spacing:0.08em;color:rgba(255,255,255,0.5);">Thời gian</div>
            </div>
          </div>
        `;
        cards.appendChild(card);
      });
    }

    // Summary strip
    const totalDist = $("#sum-distance");
    const totalTime = $("#sum-time");
    const totalConf = $("#sum-confidence");
    const totalEdge = $("#sum-edges");
    if (totalDist) totalDist.textContent = sel.total_distance_display || formatDist(sel.total_distance_m);
    if (totalTime) totalTime.textContent = sel.total_travel_time_str || formatTime(sel.total_travel_time_s);
    if (totalConf) {
      const conf = (sel.avg_confidence != null && !isNaN(sel.avg_confidence))
        ? (sel.avg_confidence * 100).toFixed(0) + "%"
        : "—";
      totalConf.textContent = conf;
      totalConf.style.color = "#b4c5ff";
    }
    if (totalEdge) totalEdge.textContent = String(sel.edges?.length || 0);

    // Call renderTurnDirections so it updates when switching routes
    if (typeof renderTurnDirections === "function") {
      renderTurnDirections(sel);
    }
  }

  // ── Wire buttons ──
  function wireButtons() {
    const startSel = $('button[data-role="start"]');
    const endSel = $('button[data-role="end"]');
    const goBtn = $("#find-route-btn");

    console.log("[wireButtons] goBtn found:", !!goBtn, goBtn ? "disabled=" + goBtn.disabled : "");

    if (startSel) startSel.addEventListener("click", () => pickPreset("start"));
    if (endSel)   endSel.addEventListener("click", () => pickPreset("end"));
    if (goBtn) {
      goBtn.addEventListener("click", () => {
        console.log("[wireButtons] Button clicked! state.start:", state.start, "state.end:", state.end);
        findRoute();
      });
    } else {
      console.error("[wireButtons] ERROR: find-route-btn not found!");
    }

    // Autocomplete for text inputs
    const startInput = $("#input-start");
    const endInput = $("#input-end");
    if (startInput) {
      startInput.addEventListener("input", () => showAutocomplete(startInput, "start"));
      startInput.addEventListener("focus", () => showAutocomplete(startInput, "start"));
      startInput.addEventListener("blur", () => setTimeout(() => $$(".preset-dropdown").forEach(d => d.remove()), 200));
    }
    if (endInput) {
      endInput.addEventListener("input", () => showAutocomplete(endInput, "end"));
      endInput.addEventListener("focus", () => showAutocomplete(endInput, "end"));
      endInput.addEventListener("blur", () => setTimeout(() => $$(".preset-dropdown").forEach(d => d.remove()), 200));
    }

    // Nav links
    $$("nav a").forEach(a => {
      const t = a.textContent.trim();
      if (t === "Tổng quan" || t === "Overview") a.href = "/overview";
      else if (t === "Dự đoán nhanh" || t === "Quick Predict") a.href = "/predict";
      else if (t === "Tìm đường" || t === "Routing") a.href = "/routing";
    });

    // Swap button
    const swap = $("#swap-btn");
    if (swap) {
      swap.addEventListener("click", () => {
        const t = state.start;
        state.start = state.end;
        state.end = t;
        renderChips();
      });
    }
  }

  // ── Graph stats banner ──
  async function loadGraphStats() {
    try {
      const s = await API.get("/api/route/graph/stats");
      const b = $("#graph-banner");
      if (!b) return;
      if (s.ok) {
        b.className = "glass-panel rounded-xl p-3 border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 text-sm";
        b.textContent = `Đồ thị: ${s.nodes.toLocaleString()} nút, ${s.edges.toLocaleString()} cạnh`;
      } else {
        b.className = "glass-panel rounded-xl p-3 border border-error/30 bg-error/10 text-error text-sm";
        b.textContent = "⚠️ Đồ thị trống — Hãy build cache trước khi dùng Routing.";
      }
    } catch (ex) {
      console.warn("graph stats:", ex);
    }
  }

  // ── Vehicle selector (fix #3) ──
  function wireVehicleSelector() {
    const btn = $("#vehicle-btn");
    const menu = $("#vehicle-menu");
    const label = $("#vehicle-label");
    const icon = $("#vehicle-icon");
    if (!btn || !menu) return;

    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      menu.classList.toggle("hidden");
    });

    document.addEventListener("click", (e) => {
      if (!menu.contains(e.target) && e.target !== btn) menu.classList.add("hidden");
    });

    $$(".vehicle-option").forEach(opt => {
      opt.addEventListener("click", () => {
        state.vehicle = opt.dataset.vehicle;
        if (label) label.textContent = opt.dataset.label;
        if (icon)  icon.textContent = opt.dataset.icon;
        menu.classList.add("hidden");
        // If we already have a route, re-run find with the new vehicle.
        if (state.start && state.end && state.routes.length) findRoute();
      });
    });
  }

  // ── Geolocation (fix #5) ──
  function wireGeolocation() {
    $$('button[data-role]').forEach(btn => {
      btn.addEventListener("click", () => {
        const which = btn.dataset.role;
        if (!navigator.geolocation) {
          alert("Trình duyệt không hỗ trợ định vị.");
          return;
        }
        btn.disabled = true;
        const orig = btn.innerHTML;
        btn.innerHTML = '<span class="material-symbols-outlined text-primary text-sm animate-spin">progress_activity</span>';
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            btn.innerHTML = orig;
            btn.disabled = false;
            const point = {
              label: "Vị trí hiện tại",
              lat:   pos.coords.latitude,
              lon:   pos.coords.longitude,
            };
            if (which === "start") {
              state.start = point;
              const inp = $("#input-start");
              if (inp) inp.value = point.label;
            } else {
              state.end = point;
              const inp = $("#input-end");
              if (inp) inp.value = point.label;
            }
            renderChips();
          },
          (err) => {
            btn.innerHTML = orig;
            btn.disabled = false;
            alert("Không lấy được vị trí: " + err.message);
          },
          { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
        );
      });
    });
  }

  // ── Sidebar toggle (fix #2) ──
  function wireSidebarToggle() {
    const btn = $("#toggle-sidebar-btn");
    const panel = $("#route-input-panel");
    if (!btn || !panel) return;
    btn.addEventListener("click", () => {
      const hidden = panel.style.display === "none";
      panel.style.display = hidden ? "flex" : "none";
      btn.querySelector(".material-symbols-outlined").textContent =
        hidden ? "menu_open" : "menu";
    });
  }

  // ── Expanders (fix #4) ──
  function wireExpanders() {
    $$(".expander-toggle").forEach(toggle => {
      toggle.addEventListener("click", () => {
        const body = toggle.parentElement.querySelector(".expander-body");
        const chev = toggle.querySelector(".expander-chevron");
        if (!body) return;
        const hidden = body.classList.toggle("hidden");
        if (chev) chev.style.transform = hidden ? "rotate(0deg)" : "rotate(180deg)";
      });
    });
  }

  // ── Save current route to history (LocalStorage) ──
  function pushHistory(start, end) {
    try {
      const key = "its_route_history_v1";
      const raw = localStorage.getItem(key);
      const arr = raw ? JSON.parse(raw) : [];
      arr.unshift({
        start_label: start.label,
        end_label:   end.label,
        start_lat:   start.lat,
        start_lon:   start.lon,
        end_lat:     end.lat,
        end_lon:     end.lon,
        ts:          Date.now(),
      });
      while (arr.length > 50) arr.pop();
      localStorage.setItem(key, JSON.stringify(arr));
      renderHistory();
    } catch (ex) { /* ignore quota errors */ }
  }

  function renderHistory() {
    const list = $("#history-list");
    if (!list) return;
    let arr = [];
    try {
      const raw = localStorage.getItem("its_route_history_v1");
      arr = raw ? JSON.parse(raw) : [];
    } catch (ex) { arr = []; }
    if (!arr.length) {
      list.innerHTML = '<div class="text-center py-3 text-xs">Chưa có lịch sử</div>';
      return;
    }
    list.innerHTML = "";
    arr.forEach((h, i) => {
      const row = document.createElement("div");
      row.style.cssText = "padding:8px 10px;border-radius:8px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;gap:8px;";
      row.innerHTML = `
        <div style="flex:1;min-width:0;">
          <div style="font-weight:600;font-size:12px;color:#d4e4fa;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${h.start_label} → ${h.end_label}</div>
          <div style="font-size:10px;color:rgba(255,255,255,0.5);">${new Date(h.ts).toLocaleString("vi-VN")}</div>
        </div>
        <button data-idx="${i}" class="history-del material-symbols-outlined text-on-surface-variant hover:text-error" style="font-size:14px;background:none;border:none;cursor:pointer;">close</button>
      `;
      row.addEventListener("mouseenter", () => row.style.background = "rgba(37,99,235,0.15)");
      row.addEventListener("mouseleave", () => row.style.background = "transparent");
      row.addEventListener("click", (e) => {
        if (e.target.classList.contains("history-del")) return;
        state.start = { label: h.start_label, lat: h.start_lat, lon: h.start_lon };
        state.end   = { label: h.end_label,   lat: h.end_lat,   lon: h.end_lon };
        renderChips();
        findRoute();
      });
      list.appendChild(row);
    });
    // Wire delete buttons
    $$(".history-del", list).forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const idx = parseInt(btn.dataset.idx, 10);
        arr.splice(idx, 1);
        localStorage.setItem("its_route_history_v1", JSON.stringify(arr));
        renderHistory();
      });
    });
  }

  // ── Favorites (LocalStorage) ──
  function renderFavorites() {
    const list = $("#favorites-list");
    if (!list) return;
    let arr = [];
    try {
      const raw = localStorage.getItem("its_favorites_v1");
      arr = raw ? JSON.parse(raw) : [];
    } catch (ex) { arr = []; }
    if (!arr.length) {
      list.innerHTML = '<div class="text-center py-3 text-xs">Chưa có địa điểm lưu</div>';
      return;
    }
    list.innerHTML = "";
    arr.forEach((f, i) => {
      const row = document.createElement("div");
      row.style.cssText = "padding:8px 10px;border-radius:8px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;gap:8px;";
      row.innerHTML = `
        <div style="flex:1;min-width:0;">
          <div style="font-weight:600;font-size:12px;color:#d4e4fa;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${f.label}</div>
          <div style="font-size:10px;color:rgba(255,255,255,0.5);">${f.lat.toFixed(4)}, ${f.lon.toFixed(4)}</div>
        </div>
        <button data-idx="${i}" class="fav-del material-symbols-outlined text-on-surface-variant hover:text-error" style="font-size:14px;background:none;border:none;cursor:pointer;">close</button>
      `;
      row.addEventListener("mouseenter", () => row.style.background = "rgba(37,99,235,0.15)");
      row.addEventListener("mouseleave", () => row.style.background = "transparent");
      row.addEventListener("click", (e) => {
        if (e.target.classList.contains("fav-del")) return;
        // Use the favourite as the destination (or start if no end yet).
        if (!state.end || (state.start && !state.end)) {
          state.end = { label: f.label, lat: f.lat, lon: f.lon };
          const inp = $("#input-end");
          if (inp) inp.value = f.label;
        } else {
          state.start = { label: f.label, lat: f.lat, lon: f.lon };
          const inp = $("#input-start");
          if (inp) inp.value = f.label;
        }
        renderChips();
      });
      list.appendChild(row);
    });
    $$(".fav-del", list).forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const idx = parseInt(btn.dataset.idx, 10);
        arr.splice(idx, 1);
        localStorage.setItem("its_favorites_v1", JSON.stringify(arr));
        renderFavorites();
      });
    });
  }

  function saveFavorite(point) {
    try {
      const raw = localStorage.getItem("its_favorites_v1");
      const arr = raw ? JSON.parse(raw) : [];
      // dedupe by label
      if (arr.some(f => f.label === point.label && f.lat === point.lat && f.lon === point.lon)) return;
      arr.unshift({ label: point.label, lat: point.lat, lon: point.lon, ts: Date.now() });
      while (arr.length > 30) arr.pop();
      localStorage.setItem("its_favorites_v1", JSON.stringify(arr));
      renderFavorites();
    } catch (ex) { /* ignore */ }
  }

  // ── GPX export (fix #7) ──
  function exportGPX() {
    if (!state.routes.length) {
      alert("Chưa có tuyến đường để xuất.");
      return;
    }
    const visible = state.routes.filter(r => r.strategy !== "Ngắn nhất");
    const sel = visible[state.selectedIdx] || visible[0];
    if (!sel || !sel.geometry || !sel.geometry.length) {
      alert("Không có geometry để xuất.");
      return;
    }
    const name = `ITS_Route_${state.start?.label || "Start"}_to_${state.end?.label || "End"}`.replace(/\s+/g, "_");
    const pts = sel.geometry.map(([la, lo]) => `      <trkpt lat="${la}" lon="${lo}"></trkpt>`).join("\n");
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="ITS Traffic Dashboard" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>${name}</name>
    <time>${new Date().toISOString()}</time>
  </metadata>
  <trk>
    <name>${name}</name>
    <trkseg>
${pts}
    </trkseg>
  </trk>
</gpx>`;
    const blob = new Blob([xml], { type: "application/gpx+xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name + ".gpx";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // ── Turn-by-turn directions (fix #8) ──
  function renderTurnDirections(route) {
    const box = $("#turn-directions");
    if (!box || !route || !route.edges?.length) {
      if (box) box.innerHTML = '<div class="text-center py-3 text-xs text-on-surface-variant">Không có chỉ dẫn</div>';
      return;
    }

    const edges = route.edges;
    const items = [];
    let total_m = 0;

    for (let i = 0; i < edges.length; i++) {
      const e = edges[i];
      const next = edges[i + 1];
      total_m += (e.length_m || 0);

      let maneuver = "Đi thẳng";
      let icon = "straight";

      if (i === 0) {
        maneuver = "Bắt đầu từ " + (e.street || "điểm xuất phát");
        icon = "play_arrow";
      } else if (i === edges.length - 1) {
        maneuver = "Đến điểm kết thúc";
        icon = "flag";
      } else if (next && e.lat2 != null && e.lon2 != null &&
                 next.lat1 != null && next.lon1 != null) {
        // compute bearing diff between current edge and next edge
        const b_out = bearingDeg(e.lat2, e.lon2, next.lat1, next.lon1);
        const b_in  = bearingDeg(e.lat1 || e.lat2, e.lon1 || e.lon2, e.lat2, e.lon2);
        let diff = ((b_out - b_in + 540) % 360) - 180;
        const ad = Math.abs(diff);
        if (ad < 18)        { maneuver = "Đi thẳng";       icon = "straight"; }
        else if (ad < 60)   { maneuver = diff > 0 ? "Rẽ nhẹ phải" : "Rẽ nhẹ trái";
                              icon     = diff > 0 ? "turn_slight_right" : "turn_slight_left"; }
        else if (ad < 120)  { maneuver = diff > 0 ? "Rẽ phải" : "Rẽ trái";
                              icon     = diff > 0 ? "turn_right" : "turn_left"; }
        else                { maneuver = diff > 0 ? "Quay đầu phải" : "Quay đầu trái";
                              icon     = diff > 0 ? "u_turn_right" : "u_turn_left"; }
        maneuver += ` vào ${next.street || "đường tiếp theo"}`;
      }

      items.push({
        icon,
        maneuver,
        street:    e.street || "—",
        length_m:  e.length_m || 0,
        time_s:    e.travel_time_s || 0,
        los:       e.los || "B",
        los_color: e.los_color || LOS_COLORS[e.los] || "#888",
      });
    }

    // Render
    box.innerHTML = "";
    items.forEach((it, idx) => {
      const row = document.createElement("div");
      row.style.cssText = "display:flex;gap:10px;padding:8px;border-radius:8px;align-items:flex-start;";
      row.innerHTML = `
        <div style="width:28px;height:28px;border-radius:50%;background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center;flex-shrink:0;">
          <span class="material-symbols-outlined text-primary" style="font-size:16px;">${it.icon}</span>
        </div>
        <div style="flex:1;min-width:0;">
          <div style="font-size:12px;font-weight:600;color:#d4e4fa;line-height:1.4;">${it.maneuver}</div>
          <div style="font-size:11px;color:rgba(255,255,255,0.6);margin-top:2px;display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
            <span>${Math.round(it.length_m)} m</span>
            <span>·</span>
            <span style="padding:1px 6px;border-radius:4px;background:${it.los_color};color:#fff;font-size:10px;font-weight:700;">LOS ${it.los}</span>
          </div>
        </div>
      `;
      box.appendChild(row);
    });

    // Save last route for back-button restoration
    try {
      sessionStorage.setItem("its_last_route", JSON.stringify({
        strategy:      route.strategy,
        total_distance_m: route.total_distance_m,
        total_travel_time_s: route.total_travel_time_s,
        edges:         route.edges,
        geometry:      route.geometry,
        start_label:   state.start?.label,
        end_label:     state.end?.label,
      }));
    } catch (ex) { /* ignore */ }
  }

  function bearingDeg(lat1, lon1, lat2, lon2) {
    const phi1 = lat1 * Math.PI / 180;
    const phi2 = lat2 * Math.PI / 180;
    const dl = (lon2 - lon1) * Math.PI / 180;
    const x = Math.sin(dl) * Math.cos(phi2);
    const y = Math.cos(phi1) * Math.sin(phi2) - Math.sin(phi1) * Math.cos(phi2) * Math.cos(dl);
    return (Math.atan2(x, y) * 180 / Math.PI + 360) % 360;
  }

  // ── GPX export button (fix #7) ──
  function wireGPXExport() {
    const btn = $("#export-gpx-btn");
    if (!btn) return;
    btn.addEventListener("click", exportGPX);
  }

  function wireSaveFavorite() {
    const btn = $("#save-fav-btn");
    if (!btn) return;
    btn.addEventListener("click", () => {
      if (!state.end) {
        alert("Chưa có điểm đến để lưu.");
        return;
      }
      saveFavorite(state.end);
      btn.innerHTML = '<span class="material-symbols-outlined text-sm">check</span> Đã lưu';
      setTimeout(() => {
        btn.innerHTML = '<span class="material-symbols-outlined text-sm">bookmark_add</span> Lưu điểm đến';
      }, 2000);
    });
  }

  async function init() {
    await loadPresets();
    wireButtons();
    wireVehicleSelector();
    wireGeolocation();
    wireSidebarToggle();
    wireExpanders();
    wireGPXExport();
    wireSaveFavorite();
    wireUseCurrentLocation();
    wireAddWaypoint();
    renderChips();
    renderWaypoints();
    await loadGraphStats();
    renderHistory();
    renderFavorites();
    // Restore last route from sessionStorage (when returning from /navigation)
    try {
      const raw = sessionStorage.getItem("its_last_route");
      if (raw) {
        const r = JSON.parse(raw);
        state.routes = [{
          strategy: r.strategy,
          total_distance_m: r.total_distance_m,
          total_distance_display: (r.total_distance_m >= 1000
            ? (r.total_distance_m / 1000).toFixed(1) + " km"
            : Math.round(r.total_distance_m) + " m"),
          total_travel_time_s: r.total_travel_time_s,
          total_travel_time_str: (() => {
            const s = Math.round(r.total_travel_time_s);
            if (s < 60) return s + "s";
            if (s < 3600) return Math.floor(s / 60) + "m";
            return Math.floor(s / 3600) + "h " + Math.floor((s % 3600) / 60) + "m";
          })(),
          avg_confidence: 0.5,
          los_distribution: {},
          geometry: r.geometry,
          edges: r.edges,
        }];
        const drawer = $("#results-drawer");
        if (drawer) drawer.style.display = "flex";
        renderMap();
        renderDrawer();
        renderTurnDirections(state.routes[0]);
      }
    } catch (ex) { /* ignore */ }
  }

  return { init, state, showAutocomplete, syncFloatingChips, renderChips, renderDrawer, renderMap, formatDist, formatTime };
})();

// Expose RoutingApp globally for Leaflet map integration
window.RoutingApp = RoutingApp;

/* ════════════════════════════════════════════════════════════════════
   Leaflet Map — initialised on DOMContentLoaded, re-used for both
   empty + found states. Tiles: CartoDB dark_all.
   ════════════════════════════════════════════════════════════════════ */
document.addEventListener("DOMContentLoaded", function () {
  const HCMC_CENTER = [10.775, 106.700];
  const TILE_DARK   = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";
  const ATTR_DARK   = "&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> &copy; <a href='https://carto.com/attributions'>CARTO</a>";

  let map        = null;
  let startMk    = null;
  let endMk      = null;
  let routeLines = [];

  // ── Icon factories ──────────────────────────────────────────────
  function mkIcon(color) {
    const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='24' height='36' viewBox='0 0 24 36'>
      <path d='M12 0C5.4 0 0 5.4 0 12c0 9 12 24 12 24S24 21 24 12C24 5.4 18.6 0 12 0z' fill='${color}'/>
      <circle cx='12' cy='12' r='5' fill='white'/>
    </svg>`;
    return L.divIcon({ html: svg, className: "", iconSize: [24, 36], iconAnchor: [12, 36] });
  }
  const ICON_START = mkIcon("#22c55e");
  const ICON_END   = mkIcon("#ef4444");

  // ── Init map (once) ────────────────────────────────────────────
  function initMap() {
    const container = document.getElementById("leaflet-map");
    if (!container || map) return;

    map = L.map("leaflet-map", {
      center:             HCMC_CENTER,
      zoom:               13,
      zoomControl:        true,
      attributionControl: true,
    });

    L.tileLayer(TILE_DARK, { attribution: ATTR_DARK, maxZoom: 19 }).addTo(map);

    // Click on map → assign start / end in sequence
    map.on("click", function (e) {
      const RA = window.RoutingApp;
      if (!RA) return;
      const s = RA.state;
      if (!s.start) {
        s.start = { label: "Điểm chọn", lat: e.latlng.lat, lon: e.latlng.lng };
        if (RA.renderChips) RA.renderChips();
      } else if (!s.end) {
        s.end = { label: "Điểm chọn", lat: e.latlng.lat, lon: e.latlng.lng };
        if (RA.renderChips) RA.renderChips();
      }
    });

    // Listen to autocomplete / geolocation events to update markers
    window.addEventListener("routing-state-changed", () => {
      renderMarkers();
    });

    // Listen to route-found event to draw the polyline
    window.addEventListener("route-found", () => {
      renderRoutes();
    });
  }

  // ── Render / update start + end markers ────────────────────────
  function renderMarkers() {
    if (!map) return;
    const state = window.RoutingApp ? window.RoutingApp.state : { start: null, end: null };

    if (startMk) { map.removeLayer(startMk); startMk = null; }
    if (endMk)   { map.removeLayer(endMk);   endMk   = null; }

    const latlngs = [];

    if (state.start && state.start.lat != null) {
      startMk = L.marker([state.start.lat, state.start.lon], { icon: ICON_START })
        .addTo(map)
        .bindPopup(state.start.label || "Xuất phát");
      latlngs.push([state.start.lat, state.start.lon]);
    }
    if (state.end && state.end.lat != null) {
      endMk = L.marker([state.end.lat, state.end.lon], { icon: ICON_END })
        .addTo(map)
        .bindPopup(state.end.label || "Điểm đến");
      latlngs.push([state.end.lat, state.end.lon]);
    }
    
    // Auto-fit bounds if we have points
    if (latlngs.length > 0) {
      if (latlngs.length === 1) {
        map.flyTo(latlngs[0], 14, { duration: 0.5 });
      } else {
        map.flyToBounds(L.latLngBounds(latlngs), { padding: [50, 50], duration: 0.5, maxZoom: 15 });
      }
    }
  }

  // ── Draw route polylines (LOS-coloured per edge) ───────────────
  function renderRoutes() {
    if (!map) return;
    routeLines.forEach(l => map.removeLayer(l));
    routeLines = [];

    const RA = window.RoutingApp;
    if (!RA) return;
    const visible = RA.state.routes.filter(r => r.strategy !== "Ngắn nhất");
    const sel = visible[RA.state.selectedIdx] || visible[0];
    if (!sel || !sel.geometry || !sel.geometry.length) return;

    if (sel.edges && sel.edges.length) {
      sel.edges.forEach(e => {
        if (e.lat1 == null) return;
        const pts = (e.geometry && e.geometry.length > 0) ? e.geometry : [[e.lat1, e.lon1], [e.lat2, e.lon2]];
        const line = L.polyline(pts, {
          color: (typeof LOS_COLORS !== 'undefined' && LOS_COLORS[e.los]) || e.los_color || "#888", weight: 5, opacity: 0.9,
          lineCap: "round", lineJoin: "round",
        })
          .bindPopup(`${e.street || "—"} · LOS ${e.los} · ${Math.round(e.length_m)}m`)
          .addTo(map);
        routeLines.push(line);
      });
    } else {
      const latlngs = sel.geometry.map(([la, lo]) => [la, lo]);
      const color = ROUTE_STRATEGY_COLORS[sel.strategy] || "#2563eb";
      L.polyline(latlngs, { color, weight: 5, opacity: 0.85 }).addTo(map);
    }

    try {
      const bounds = L.latLngBounds(sel.geometry.map(([la, lo]) => [la, lo]));
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
    } catch (_) {}
  }

  // ── Boot ──────────────────────────────────────────────────────
  // Initialize RoutingApp (this will also init map via wrapper)
  console.log("[RoutingApp] Boot - window.RoutingApp:", !!window.RoutingApp);
  if (window.RoutingApp && window.RoutingApp.init) {
    // Wrap the original init to also call map functions
    const origInit = window.RoutingApp.init;
    window.RoutingApp.init = async function() {
      console.log("[RoutingApp] init() called");
      await origInit.apply(this, arguments);
      initMap();
      renderMarkers();
      renderRoutes();
      console.log("[RoutingApp] init() complete, state:", this.state);
    };
    window.RoutingApp.init();
  } else {
    console.log("[RoutingApp] WARNING - RoutingApp not found!");
    initMap();
  }
})();
