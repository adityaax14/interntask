import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { formatRupees, formatDate } from "../api";

export default function Analytics({ data, date }) {
  if (!data) {
    return (
      <div className="page-empty">
        <div className="empty-icon"></div>
        <h2>No Data Loaded</h2>
        <p>Upload a billing log to view analytics.</p>
      </div>
    );
  }

  const chartData = data.revenue_by_hour.map((h) => ({
    label: h.label,
    revenue: h.revenue_paise / 100,
    revenuePaise: h.revenue_paise,
    hour: h.hour,
  }));

  const peakHour = data.peak_hour;

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const d = payload[0].payload;
      return (
        <div className="chart-tooltip">
          <p className="chart-tooltip-label">{d.label}</p>
          <p className="chart-tooltip-value">
            {formatRupees(d.revenuePaise)}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="page analytics-page">
      <header className="page-header">
        <div>
          <h1>Analytics</h1>
          <p className="page-subtitle">
            Mehta Multi-Specialty Clinic — {formatDate(date)}
          </p>
        </div>
      </header>

      {/* ── Revenue by Hour Chart ──────────────────────────────── */}
      <div className="card chart-card">
        <div className="chart-header">
          <h2 className="card-title">Revenue by Hour of Day</h2>
          {peakHour && (
            <span className="peak-badge">
              Peak: {peakHour.label}–
              {_nextHourLabel(peakHour.hour)} —{" "}
              {formatRupees(peakHour.revenue_paise)}
            </span>
          )}
        </div>

        {chartData.length > 0 ? (
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart
                data={chartData}
                margin={{ top: 20, right: 20, bottom: 5, left: 10 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 13, fill: "#64748b" }}
                  axisLine={{ stroke: "#e2e8f0" }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 12, fill: "#64748b" }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v) => `₹${v}`}
                />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="revenue" radius={[6, 6, 0, 0]} maxBarSize={48}>
                  {chartData.map((entry) => (
                    <Cell
                      key={entry.hour}
                      fill={
                        peakHour && entry.hour === peakHour.hour
                          ? "#2563eb"
                          : "#bfdbfe"
                      }
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <p className="chart-empty">No revenue data for this day.</p>
        )}
      </div>

      {/* ── Medicine Rankings ──────────────────────────────────── */}
      <div className="rankings-row">
        <div className="card ranking-card">
          <h2 className="card-title">Top Medicines — by Quantity</h2>
          {data.top_medicines_by_qty.length > 0 ? (
            <div className="ranking-list">
              {data.top_medicines_by_qty.map((med) => (
                <div key={med.drug_name} className="ranking-item">
                  <span className="ranking-num">{med.rank}</span>
                  <span className="ranking-name">{med.drug_name}</span>
                  <span className="ranking-value">{med.quantity} units</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="ranking-empty">No medicine data.</p>
          )}
        </div>

        <div className="card ranking-card">
          <h2 className="card-title">Top Medicines — by Revenue</h2>
          {data.top_medicines_by_revenue.length > 0 ? (
            <div className="ranking-list">
              {data.top_medicines_by_revenue.map((med) => (
                <div key={med.drug_name} className="ranking-item">
                  <span className="ranking-num">{med.rank}</span>
                  <span className="ranking-name">{med.drug_name}</span>
                  <span className="ranking-value">
                    {formatRupees(med.revenue_paise)}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="ranking-empty">No medicine data.</p>
          )}
        </div>
      </div>
    </div>
  );
}

function _nextHourLabel(hour) {
  const next = (hour + 1) % 24;
  if (next === 0) return "12am";
  if (next < 12) return `${next}am`;
  if (next === 12) return "12pm";
  return `${next - 12}pm`;
}
