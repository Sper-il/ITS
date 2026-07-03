/*
* api.js. Small client wrapper around /api/*.
*
* Usage:
*   const { samples, mean_conf, dominant_los } = await api.get('/api/overview/summary');
*   const { rows } = await api.get('/api/overview/distribution');
*   const result = await api.post('/api/predict', { length: 500, ... });
*/
const API = (() => {
  const base = "";

  async function request(path, options = {}) {
    const res = await fetch(base + path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    });
    if (!res.ok) {
      const body = await res.text();
      throw new Error(`API ${res.status}: ${body.slice(0, 200)}`);
    }
    return res.json();
  }

  return {
    get:  (path)             => request(path,        { method: "GET"  }),
    post: (path, payload = {}) => request(path,      { method: "POST", body: JSON.stringify(payload) }),
  };
})();

/* ── LOS_COLORS / LOS_NAMES client mirror (matches backend/core/constants.py) ── */
const LOS_COLORS = {
  A: "#2563eb", B: "#3b82f6", C: "#60a5fa",
  D: "#f97316", E: "#ef4444", F: "#b91c1c",
};
const LOS_NAMES = {
  A: "Rất tốt (Tự do)",
  B: "Tốt (Ổn định)",
  C: "Ổn định (Trung bình)",
  D: "Kém (Gần tắc)",
  E: "Rất kém (Tắc nghẽn)",
  F: "Quá tải (Đứng im)",
};
const LOS_ADVICE = {
  A: { text: "Rất tốt (Tự do) · tốc độ cao, không có ma sát.",      color: "#2563eb" },
  B: { text: "Tốt (Ổn định) · chạy đều ở tốc độ thiết kế.",     color: "#3b82f6" },
  C: { text: "Ổn định (Trung bình) · giữ khoảng cách an toàn.",   color: "#60a5fa" },
  D: { text: "Kém (Gần tắc) · chuẩn bị giảm tốc độ.",   color: "#f97316" },
  E: { text: "Rất kém (Tắc nghẽn) · cân nhắc đường khác.", color: "#ef4444" },
  F: { text: "Quá tải (Đứng im) · tránh tuyến đường này.", color: "#b91c1c" },
};
const ROUTE_STRATEGY_COLORS = {
  "Ít kẹt nhất": "#2563eb",
  "Nhanh nhất":  "#f59e0b",
  "Ngắn nhất":   "#10b981",
};

/* ── Number formatters ── */
function fmtPercent(x, digits = 1) {
  if (x === null || x === undefined || Number.isNaN(x)) return "—";
  return (x * 100).toFixed(digits) + "%";
}
function fmtDistance(m) {
  if (m == null) return "—";
  if (m >= 1000) return (m / 1000).toFixed(1) + " km";
  return Math.round(m) + " m";
}
function fmtTravelTime(s) {
  if (s == null || s <= 0) return "—";
  s = Math.round(s);
  if (s < 60)   return s + "s";
  if (s < 3600) return Math.floor(s / 60) + "m";
  return Math.floor(s / 3600) + "h " + Math.floor((s % 3600) / 60) + "m";
}
