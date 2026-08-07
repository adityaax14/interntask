import { formatRupees, formatDate } from "../api";

export default function Reconciliation({ data, date }) {
  if (!data) {
    return (
      <div className="page-empty">
        <div className="empty-icon"></div>
        <h2>No Data Loaded</h2>
        <p>Upload a billing log to view the EOD reconciliation report.</p>
      </div>
    );
  }

  const collectionPct =
    data.total_billed_paise - data.total_discount_paise > 0
      ? Math.round(
          (data.total_collected_paise /
            (data.total_billed_paise - data.total_discount_paise)) *
            100
        )
      : 0;

  return (
    <div className="page reconciliation-page">
      <header className="page-header">
        <div>
          <h1>EOD Reconciliation</h1>
          <p className="page-subtitle">
            Mehta Multi-Specialty Clinic — Kanpur, Uttar Pradesh
          </p>
        </div>
        <div className="date-badge">{formatDate(date)}</div>
      </header>

      {/* ── Stat Cards ─────────────────────────────────────────── */}
      <div className="stat-cards">
        <div className="stat-card">
          <span className="stat-label stat-label--billed">TOTAL BILLED</span>
          <span className="stat-value">{formatRupees(data.total_billed_paise)}</span>
          <span className="stat-meta stat-meta--blue">
            {data.visit_count} visit{data.visit_count !== 1 ? "s" : ""}
          </span>
        </div>

        <div className="stat-card">
          <span className="stat-label stat-label--collected">TOTAL COLLECTED</span>
          <span className="stat-value">
            {formatRupees(data.total_collected_paise)}
          </span>
          <span className="stat-meta stat-meta--green">
            {collectionPct}% of billed
          </span>
        </div>

        <div className="stat-card">
          <span className="stat-label stat-label--outstanding">OUTSTANDING</span>
          <span className="stat-value">
            {formatRupees(data.total_outstanding_paise)}
          </span>
          <span className="stat-meta stat-meta--orange">
            {data.pending_visit_count} pending visit
            {data.pending_visit_count !== 1 ? "s" : ""}
          </span>
        </div>

        <div className="stat-card">
          <span className="stat-label stat-label--refunds">REFUNDS</span>
          <span className="stat-value">{formatRupees(data.total_refunds_paise)}</span>
          <span className="stat-meta stat-meta--red">
            {data.refund_count} refund{data.refund_count !== 1 ? "s" : ""}
          </span>
        </div>
      </div>

      {/* ── Payment Mode Breakdown ─────────────────────────────── */}
      <div className="card breakdown-card">
        <h2 className="card-title">Payment Mode Breakdown</h2>
        <table className="breakdown-table">
          <thead>
            <tr>
              <th>Mode</th>
              <th>Billed</th>
              <th>Collected</th>
              <th>Outstanding</th>
            </tr>
          </thead>
          <tbody>
            {data.mode_breakdown.map((row) => (
              <tr key={row.mode}>
                <td className="mode-name">
                  {row.mode.charAt(0).toUpperCase() + row.mode.slice(1)}
                </td>
                <td>{formatRupees(row.billed_paise)}</td>
                <td>{formatRupees(row.collected_paise)}</td>
                <td>{formatRupees(row.outstanding_paise)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Validation Errors ──────────────────────────────────── */}
      {data.validation_errors && data.validation_errors.length > 0 && (
        <div className="card errors-card">
          <h2 className="card-title">⚠️ Validation Warnings</h2>
          <p className="errors-subtitle">
            {data.validation_errors.length} record
            {data.validation_errors.length !== 1 ? "s" : ""} rejected during
            ingestion
          </p>
          <div className="errors-list">
            {data.validation_errors.map((err, i) => (
              <div key={i} className="error-item">
                <code className="error-visit">{err.visit_id || "unknown"}</code>
                <span className="error-field">{err.field}</span>
                <span className="error-msg">{err.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
