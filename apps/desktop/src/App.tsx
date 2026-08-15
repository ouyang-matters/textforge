import React, { useState, useEffect } from "react";
import { RewriteView } from "./views/Rewrite";
import { ClaudeView } from "./views/Claude";
import { CompareView } from "./views/Compare";
import { SettingsView } from "./views/Settings";
import { api, getApiKey } from "./api";

type Tab = "rewrite" | "claude" | "compare" | "settings";

export default function App() {
  const [tab, setTab] = useState<Tab>("rewrite");
  const [configured, setConfigured] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const key = await getApiKey();
        if (key) {
          await api.configureProvider(key);
          setConfigured(true);
        }
      } catch { /* ignore */ }
      // Also check health
      try {
        const h = await api.health();
        setConfigured(h.provider_configured);
      } catch { /* server not ready yet, retry */ }
      setLoading(false);
    })();
  }, []);

  const tabs: { id: Tab; label: string }[] = [
    { id: "rewrite", label: "Rewrite" },
    { id: "claude", label: "Claude" },
    { id: "compare", label: "Compare" },
    { id: "settings", label: "Settings" },
  ];

  return (
    <div className="app">
      <nav className="sidebar">
        <div className="sidebar-brand">TextForge</div>
        {tabs.map((t) => (
          <button
            key={t.id}
            className={`sidebar-tab ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
        <div className="sidebar-spacer" />
        <div className="sidebar-status">
          <span className={`dot ${configured ? "green" : "amber"}`} />
          {configured ? "Connected" : "No API Key"}
        </div>
      </nav>
      <main className="content">
        {loading ? (
          <div className="center-message">Starting TextForge engine…</div>
        ) : (
          <>
            {tab === "rewrite" && <RewriteView configured={configured} />}
            {tab === "claude" && <ClaudeView configured={configured} />}
            {tab === "compare" && <CompareView />}
            {tab === "settings" && (
              <SettingsView
                configured={configured}
                onConfigured={() => setConfigured(true)}
              />
            )}
          </>
        )}
      </main>
    </div>
  );
}
