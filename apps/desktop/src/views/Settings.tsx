import React, { useState, useEffect, useCallback } from "react";
import { api, getApiKey, setApiKey } from "../api";

export function SettingsView({
  configured,
  onConfigured,
}: {
  configured: boolean;
  onConfigured: () => void;
}) {
  const [key, setKey] = useState("");
  const [masked, setMasked] = useState("");
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState<{
    ok: boolean;
    msg: string;
  } | null>(null);

  useEffect(() => {
    (async () => {
      const saved = await getApiKey();
      if (saved) {
        setKey(saved);
        setMasked(saved.slice(0, 10) + "…" + saved.slice(-4));
      }
    })();
  }, []);

  const handleTest = useCallback(async () => {
    if (!key.trim()) return;
    setTesting(true);
    setTestResult(null);
    try {
      const res = await api.testProvider(key);
      if (res.ok) {
        setTestResult({ ok: true, msg: `Connected (${res.model || "ok"})` });
      } else {
        setTestResult({ ok: false, msg: res.error || "Failed" });
      }
    } catch (e: any) {
      setTestResult({ ok: false, msg: e.message });
    } finally {
      setTesting(false);
    }
  }, [key]);

  const handleSave = useCallback(async () => {
    if (!key.trim()) return;
    setSaving(true);
    try {
      await setApiKey(key);
      await api.configureProvider(key);
      setMasked(key.slice(0, 10) + "…" + key.slice(-4));
      onConfigured();
    } catch (e: any) {
      setTestResult({ ok: false, msg: e.message });
    } finally {
      setSaving(false);
    }
  }, [key, onConfigured]);

  return (
    <div className="view settings-view">
      <div className="view-header">
        <h1>Settings</h1>
      </div>

      <div className="settings-section">
        <h2>Anthropic API</h2>
        <p className="settings-desc">
          Your API key is stored in the app's local config directory, not in the database.
          TextForge uses BYOK (Bring Your Own Key) through the official Anthropic API.
        </p>

        <div className="settings-field">
          <label>API Key</label>
          <div className="key-input-row">
            <input
              type="password"
              className="text-input"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="sk-ant-…"
            />
            <button className="btn-secondary" onClick={handleTest} disabled={testing || !key.trim()}>
              {testing ? "Testing…" : "Test"}
            </button>
            <button className="btn-primary" onClick={handleSave} disabled={saving || !key.trim()}>
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
          {masked && configured && (
            <div className="settings-hint">Current: {masked}</div>
          )}
          {testResult && (
            <div className={`test-result ${testResult.ok ? "pass" : "fail"}`}>
              {testResult.msg}
            </div>
          )}
        </div>
      </div>

      <div className="settings-section">
        <h2>Privacy</h2>
        <p className="settings-desc">
          History is opt-in. Raw text logging is disabled by default.
          Your text is sent only to the Anthropic API for rewriting.
        </p>
      </div>

      <div className="settings-section">
        <h2>About</h2>
        <p className="settings-desc">
          TextForge v0.1.0 — Text post-processing middleware
        </p>
      </div>
    </div>
  );
}
