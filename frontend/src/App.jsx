import { useState, useCallback, useEffect } from "react";
import { Routes, Route, useSearchParams } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Reconciliation from "./pages/Reconciliation";
import Analytics from "./pages/Analytics";
import Narrative from "./pages/Narrative";
import {
  uploadBillingLog,
  getReconciliation,
  getAnalytics,
  getDates,
  pingHealth,
} from "./api";

export default function App() {
  const [recon, setRecon] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [narrative, setNarrative] = useState(null);
  const [clinicId, setClinicId] = useState(null);
  const [date, setDate] = useState(null);
  const [dates, setDates] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [searchParams] = useSearchParams();

  // Load data if clinic_id and date are in URL params
  useEffect(() => {
    const paramClinic = searchParams.get("clinicId");
    const paramDate = searchParams.get("date");
    if (paramClinic && paramDate) {
      loadData(paramClinic, paramDate);
    }

    // Ping backend every 10 minutes (600,000 ms) to keep it alive (e.g., on Render)
    pingHealth(); // Initial ping
    const keepAliveInterval = setInterval(pingHealth, 600000);
    return () => clearInterval(keepAliveInterval);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const loadData = async (cid, dt) => {
    try {
      setClinicId(cid);
      setDate(dt);
      setNarrative(null);

      const [reconData, analyticsData, datesData] = await Promise.all([
        getReconciliation(cid, dt),
        getAnalytics(cid, dt),
        getDates(cid),
      ]);

      setRecon(reconData);
      setAnalytics(analyticsData);
      setDates(datesData.dates || []);
    } catch (err) {
      setUploadError(err.message);
    }
  };

  const handleUpload = useCallback(async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Limit file size to 10MB
    const MAX_FILE_SIZE_MB = 10;
    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      setUploadError(`File is too large. Please upload a file smaller than ${MAX_FILE_SIZE_MB}MB.`);
      e.target.value = "";
      return;
    }

    setUploading(true);
    setUploadError(null);
    setNarrative(null);

    try {
      const result = await uploadBillingLog(file);
      const cid = result.clinic_id;
      const dt = result.date;

      await loadData(cid, dt);
    } catch (err) {
      setUploadError(err.message);
      console.error("Upload error:", err);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleDateChange = useCallback(async (newDate) => {
    if (clinicId && newDate) {
      await loadData(clinicId, newDate);
    }
  }, [clinicId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleNarrativeLoaded = useCallback((data) => {
    setNarrative(data);
  }, []);

  return (
    <div className="app-layout">
      <Sidebar
        clinicName={clinicId ? "Mehta Multi-Specialty Clinic" : null}
        onUpload={handleUpload}
        uploading={uploading}
        dates={dates}
        currentDate={date}
        onDateChange={handleDateChange}
      />

      <main className="main-content">
        {uploadError && (
          <div className="global-error">
            <span>Error: {uploadError}</span>
            <button onClick={() => setUploadError(null)}>×</button>
          </div>
        )}

        <Routes>
          <Route
            path="/"
            element={<Reconciliation data={recon} date={date} />}
          />
          <Route
            path="/analytics"
            element={<Analytics data={analytics} date={date} />}
          />
          <Route
            path="/narrative"
            element={
              <Narrative
                data={narrative}
                clinicId={clinicId}
                date={date}
                onNarrativeLoaded={handleNarrativeLoaded}
              />
            }
          />
        </Routes>
      </main>
    </div>
  );
}
