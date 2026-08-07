import { NavLink } from "react-router-dom";
import logo from "../assets/logo.png";

const navItems = [
  { path: "/", label: "EOD Reconciliation" },
  { path: "/analytics", label: "Analytics" },
  { path: "/narrative", label: "AI Summary" },
];

export default function Sidebar({
  clinicName,
  onUpload,
  uploading,
  dates = [],
  currentDate,
  onDateChange,
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <img src={logo} alt="SwasthiQ Logo" className="logo-image" />
        </div>
        {clinicName && <p className="sidebar-clinic">{clinicName}</p>}
      </div>

      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `nav-item ${isActive ? "nav-item--active" : ""}`
            }
            end={item.path === "/"}
          >
            <span className="nav-dot" />
            <span className="nav-label">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Date selector — visible when multiple dates are available */}
      {dates.length > 1 && (
        <div className="sidebar-dates">
          <label className="dates-label">Select Date</label>
          <select
            className="dates-select"
            value={currentDate || ""}
            onChange={(e) => onDateChange(e.target.value)}
          >
            {dates.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="sidebar-upload">
        <label
          className={`upload-btn ${uploading ? "upload-btn--loading" : ""}`}
        >
          <input
            type="file"
            accept=".json"
            onChange={onUpload}
            disabled={uploading}
            style={{ display: "none" }}
          />
          {uploading ? "Processing…" : "Upload Billing Log"}
        </label>
      </div>

      <div className="sidebar-footer">
        <p className="sidebar-version">v1.0.0</p>
      </div>
    </aside>
  );
}
