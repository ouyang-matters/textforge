import React, { useState, useRef, useCallback } from "react";
import { api, RewriteResult } from "../api";

const STRENGTHS = [
  { id: "light", label: "Light" },
  { id: "natural", label: "Natural" },
  { id: "strong", label: "Strong" },
];

const STYLES = [
  { id: "natural", label: "Natural" },
  { id: "academic", label: "Academic" },
  { id: "professional", label: "Professional" },
  { id: "concise", label: "Concise" },
  { id: "creative", label: "Creative" },
];

type Status = "idle" | "rewriting" | "validating" | "repairing" | "done" | "error";

export function RewriteView({ configured }: { configured: boolean }) {
  const [input, setInput] = useState("");
  const [strength, setStrength] = useState("natural");
  const [style, setStyle] = useState("natural");
  const [result, setResult] = useState<RewriteResult | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState("");
  const [showDiff, setShowDiff] = useState(false);
  const busyRef = useRef(false);

  // Preservation toggles
  const [preserves, setPreserves] = useState({
    meaning: true,
    numbers: true,
    formulas: true,
    citations: true,
    names: true,
    technical: true,
  });

  const handleRewrite = useCallback(async () => {
    if (busyRef.current || !input.trim()) return;
    busyRef.current = true;
    setStatus("rewriting");
    setError("");
    setResult(null);

    try {
      const res = await api.rewrite({
        text: input,
        strength,
        style,
        preserve_meaning: preserves.meaning,
        preserve_numbers: preserves.numbers,
        preserve_formulas: preserves.formulas,
        preserve_citations: preserves.citations,
        preserve_names: preserves.names,
        preserve_technical: preserves.technical,
      });
      setResult(res);
      setStatus("done");
    } catch (e: any) {
      setError(e.message || "Rewrite failed");
      setStatus("error");
    } finally {
      busyRef.current = false;
    }
  }, [input, strength, style, preserves]);

  const copyResult = useCallback(() => {
    if (result) navigator.clipboard.writeText(result.text);
  }, [result]);

  const fmtMetric = (key: string, val: unknown) => {
    if (val === null || val === undefined) return "—";
    if (typeof val === "number") return val.toFixed(3);
    return String(val);
  };

  return (
    <div className="view rewrite-view">
      <div className="view-header">
        <h1>Rewrite</h1>
        <div className="controls-row">
          <div className="control-group">
            <label>Strength</label>
            <div className="toggle-group">
              {STRENGTHS.map((s) => (
                <button
                  key={s.id}
                  className={`toggle-btn ${strength === s.id ? "active" : ""}`}
                  onClick={() => setStrength(s.id)}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>
          <div className="control-group">
            <label>Style</label>
            <div className="toggle-group">
              {STYLES.map((s) => (
                <button
                  key={s.id}
                  className={`toggle-btn ${style === s.id ? "active" : ""}`}
                  onClick={() => setStyle(s.id)}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="preserve-bar">
        {Object.entries(preserves).map(([key, val]) => (
          <label key={key} className="preserve-toggle">
            <input
              type="checkbox"
              checked={val}
              onChange={() =>
                setPreserves((p) => ({ ...p, [key]: !p[key as keyof typeof p] }))
              }
            />
            <span>{key.charAt(0).toUpperCase() + key.slice(1)}</span>
          </label>
        ))}
      </div>

      <div className="panes">
        <div className="pane">
          <div className="pane-header">Original</div>
          <textarea
            className="pane-textarea"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Paste your text here…"
          />
        </div>
        <div className="pane">
          <div className="pane-header">
            Result
            {result && (
              <div className="pane-actions">
                <button className="btn-sm" onClick={() => setShowDiff(!showDiff)}>
                  {showDiff ? "Plain" : "Diff"}
                </button>
                <button className="btn-sm" onClick={copyResult}>
                  Copy
                </button>
              </div>
            )}
          </div>
          <div className="pane-result">
            {status === "idle" && (
              <div className="empty-state">
                {configured
                  ? "Paste text and press Rewrite"
                  : "Configure API key in Settings first"}
              </div>
            )}
            {(status === "rewriting" || status === "validating" || status === "repairing") && (
              <div className="loading-state">
                <div className="spinner" />
                <span>
                  {status === "rewriting"
                    ? "Rewriting…"
                    : status === "validating"
                    ? "Validating…"
                    : "Repairing…"}
                </span>
              </div>
            )}
            {status === "error" && <div className="error-state">{error}</div>}
            {status === "done" && result && (
              <>
                {showDiff ? (
                  <DiffView original={input} rewritten={result.text} />
                ) : (
                  <div className="result-text">{result.text}</div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      <div className="bottom-bar">
        <button
          className="btn-primary"
          onClick={handleRewrite}
          disabled={!configured || status === "rewriting" || !input.trim()}
        >
          {status === "rewriting" ? "Rewriting…" : "Rewrite"}
        </button>

        {result && status === "done" && (
          <div className="metrics-row">
            {Object.entries(result.metrics)
              .filter(([k]) =>
                [
                  "semantic_similarity",
                  "character_edit_ratio",
                  "token_edit_ratio",
                  "length_ratio",
                ].includes(k)
              )
              .map(([k, v]) => (
                <div className="metric" key={k}>
                  <span className="metric-label">
                    {k.replace(/_/g, " ")}
                  </span>
                  <span className="metric-value">{fmtMetric(k, v)}</span>
                </div>
              ))}
            {result.validation && (
              <div className="metric">
                <span className="metric-label">validation</span>
                <span
                  className={`metric-value ${
                    result.validation.passed ? "pass" : "fail"
                  }`}
                >
                  {result.validation.passed ? "passed" : "issues"}
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* Simple line-based diff */
function DiffView({ original, rewritten }: { original: string; rewritten: string }) {
  const origLines = original.split("\n");
  const newLines = rewritten.split("\n");
  const maxLen = Math.max(origLines.length, newLines.length);

  return (
    <div className="diff-view">
      {Array.from({ length: maxLen }, (_, i) => {
        const o = origLines[i] ?? "";
        const n = newLines[i] ?? "";
        const changed = o !== n;
        return (
          <div key={i} className={`diff-line ${changed ? "changed" : ""}`}>
            <span className="diff-num">{i + 1}</span>
            {changed ? (
              <>
                {o && <span className="diff-del">{o}</span>}
                {n && <span className="diff-add">{n}</span>}
              </>
            ) : (
              <span>{n}</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
