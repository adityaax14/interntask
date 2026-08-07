import { useState } from "react";
import { getNarrative, formatDate } from "../api";

export default function Narrative({ data: cachedData, clinicId, date, onNarrativeLoaded }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const data = cachedData;

  const handleGenerate = async () => {
    if (!clinicId || !date) return;
    setLoading(true);
    setError(null);
    try {
      const result = await getNarrative(clinicId, date);
      onNarrativeLoaded(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // No data uploaded yet
  if (!clinicId || !date) {
    return (
      <div className="page-empty">
        <div className="empty-icon"></div>
        <h2>No Data Loaded</h2>
        <p>Upload a billing log to generate an AI narrative summary.</p>
      </div>
    );
  }

  // Data uploaded but narrative not yet generated
  if (!data && !loading) {
    return (
      <div className="page narrative-page">
        <header className="page-header">
          <div>
            <h1>AI Narrative Summary</h1>
            <p className="page-subtitle">
              Generated from today's reconciliation — Mehta Multi-Specialty Clinic
            </p>
          </div>
          <span className="ai-badge">AI SUGGESTED</span>
        </header>
        <div className="narrative-generate">
          <button className="generate-btn" onClick={handleGenerate}>
            Generate AI Summary
          </button>
          <p className="generate-hint">
            This will use the deterministic report to create a WhatsApp-style summary.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="page narrative-page">
      <header className="page-header">
        <div>
          <h1>AI Narrative Summary</h1>
          <p className="page-subtitle">
            Generated from today's reconciliation — Mehta Multi-Specialty Clinic
          </p>
        </div>
        <span className="ai-badge">AI SUGGESTED</span>
      </header>

      {loading && (
        <div className="narrative-loading">
          <div className="spinner" />
          <p>Generating AI summary…</p>
        </div>
      )}

      {error && (
        <div className="narrative-error">
          <p>Error: {error}</p>
          <button className="generate-btn generate-btn--small" onClick={handleGenerate}>
            Retry
          </button>
        </div>
      )}

      {data && (
        <div className="narrative-content">
          {/* ── Narrative Card ──────────────────────────────────── */}
          <div className="narrative-card">
            <div className="narrative-whatsapp-header">
              Sent to: Dr. Anand Mehta · WhatsApp
            </div>
            <div className="narrative-text">
              {data.narrative.split("\n").map((line, i) =>
                line.trim() ? (
                  <p key={i}>{line}</p>
                ) : (
                  <br key={i} />
                )
              )}
            </div>
            <div className="narrative-status">
              <span
                className={`status-badge status-badge--${data.status}`}
              >
                {data.status.toUpperCase()}
              </span>
            </div>
          </div>

          {/* ── Traced Figures Panel ───────────────────────────── */}
          <div className="traced-panel">
            <h2 className="traced-title">Traced Figures</h2>
            <p className="traced-subtitle">
              Every number above maps to the deterministic report — this is
              what gets auto-checked.
            </p>
            {data.traced_figures && data.traced_figures.length > 0 ? (
              <div className="traced-list">
                {data.traced_figures.map((fig, i) => (
                  <div key={i} className="traced-item">
                    <span className="traced-value">{fig.display_value}</span>
                    <span className="traced-field">{fig.field_name}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="traced-empty">No traced figures extracted.</p>
            )}
          </div>
        </div>
      )}

      {data && !loading && (
        <button
          className="generate-btn generate-btn--small regenerate-btn"
          onClick={handleGenerate}
        >
          Regenerate
        </button>
      )}
    </div>
  );
}
