/**
 * API client for the SwasthiQ backend.
 * All functions return parsed JSON responses.
 */

const API_BASE = "http://localhost:8000/api/billing";

/**
 * Upload a billing log JSON file.
 */
export async function uploadBillingLog(file) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail?.message || "Upload failed");
  }

  return res.json();
}

/**
 * Get EOD reconciliation report.
 */
export async function getReconciliation(clinicId, date) {
  const res = await fetch(`${API_BASE}/reconciliation/${clinicId}/${date}`);
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail?.message || "Not found");
  }
  return res.json();
}

/**
 * Get analytics report.
 */
export async function getAnalytics(clinicId, date) {
  const res = await fetch(`${API_BASE}/analytics/${clinicId}/${date}`);
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail?.message || "Not found");
  }
  return res.json();
}

/**
 * Get AI narrative summary.
 */
export async function getNarrative(clinicId, date) {
  const res = await fetch(`${API_BASE}/narrative/${clinicId}/${date}`);
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail?.message || "Not found");
  }
  return res.json();
}

/**
 * Get available dates for a clinic.
 */
export async function getDates(clinicId) {
  const res = await fetch(`${API_BASE}/dates/${clinicId}`);
  if (!res.ok) return { dates: [] };
  return res.json();
}

/**
 * Get list of clinics.
 */
export async function getClinics() {
  const res = await fetch(`${API_BASE}/clinics`);
  if (!res.ok) return { clinics: [] };
  return res.json();
}

/**
 * Format paise to rupee display string.
 */
export function formatRupees(paise) {
  const rupees = paise / 100;
  return `₹${rupees.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

/**
 * Format date string for display.
 */
export function formatDate(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/**
 * Ping backend health endpoint to keep it alive on free hosting tiers (e.g., Render)
 */
export async function pingHealth() {
  try {
    const baseUrl = API_BASE.replace("/api/billing", "");
    await fetch(`${baseUrl}/health`);
  } catch (err) {
    console.warn("Health check ping failed:", err);
  }
}

