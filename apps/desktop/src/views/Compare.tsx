import React, { useState, useCallback } from "react";
import { api, CompareResult } from "../api";

export function CompareView() {
  const [original, setOriginal] = useState("");
  const [rewritten, setRewritten] = useState("");
  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleCompare = useCallback(async () => {
    if (!original.trim() || !rewritten.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await api.compare(original, rewritten);
      setResult(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [original, rewritten]);

  return (
    <div className="view compare-view">
      <div className="view-header">
        <h1>Compare</h1>
      </div>

      <div className="panes">
        <div className="pane">
          <div className="pane-header">Original</div>
          <textarea
            className="pane-textarea"
            value={original}
            onChange={(e) => setOriginal(e.target.value)}
            placeholder="Paste original text…"
          />
        </div>
        <div className="pane">
          <div className="pane-header">Rewritten</div>
          <textarea
            className="pane-textarea"
            value={rewritten}
            onChange={(e) => setRewritten(e.target.value)}
            placeholder="Paste rewritten text…"
          />
        </div>
      </div>

      <div className="bottom-bar">
        <button
          className="btn-primary"
          onClick={handleCompare}
          disabled={loading || !original.trim() || !rewritten.trim()}
        >
          {loading ? "Comparing…" : "Compare"}
        </button>
      </div>

      {error && <div className="error-state" style={{ marginTop: 12 }}>{error}</div>}

      {result && (
        <div className="compare-results">
          <div className="result-section">
            <h3>Edit Metrics</h3>
            <div className="metrics-grid">
              {Object.entries(result.metrics).map(([k, v]) => (
                <div key={k} className="metric">
                  <span className="metric-label">{k.replace(/_/g, " ")}</span>
                  <span className="metric-value">
                    {typeof v === "number" ? v.toFixed(3) : String(v)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="result-section">
            <h3>Preservation</h3>
            <div className="metrics-grid">
              <div className="metric">
                <span className="metric-label">Numbers</span>
                <span className={`metric-value ${result.number_preservation.passed ? "pass" : "fail"}`}>
                  {result.number_preservation.passed ? "Preserved" : "Changed"}
                </span>
              </div>
              <div className="metric">
                <span className="metric-label">Entity Score</span>
                <span className="metric-value">{result.entity_preservation.score.toFixed(3)}</span>
              </div>
              <div className="metric">
                <span className="metric-label">Quality</span>
                <span className={`metric-value ${result.quality.passed ? "pass" : "fail"}`}>
                  {result.quality.passed ? "Passed" : "Issues"}
                </span>
              </div>
            </div>
            {result.number_preservation.missing.length > 0 && (
              <div className="issue-list">
                Missing numbers: {result.number_preservation.missing.join(", ")}
              </div>
            )}
            {result.entity_preservation.missing.length > 0 && (
              <div className="issue-list">
                Missing entities: {result.entity_preservation.missing.slice(0, 10).join(", ")}
              </div>
            )}
            {result.quality.issues.length > 0 && (
              <div className="issue-list">
                {result.quality.issues.map((iss, i) => (
                  <div key={i}>{iss}</div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
