import { useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { api, Session } from "./api/client";
import { Layout } from "./components/Layout";
import { LoginPage } from "./pages/LoginPage";
import { QualityPage } from "./pages/QualityPage";
import { ReviewDetailPage } from "./pages/ReviewDetailPage";
import { ReviewQueuePage } from "./pages/ReviewQueuePage";
import { RulesPage } from "./pages/RulesPage";

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "guest">("loading");

  useEffect(() => {
    api
      .me()
      .then((payload) => {
        setSession(payload);
        setState("ready");
      })
      .catch(() => {
        setSession(null);
        setState("guest");
      });
  }, []);

  const displayName = useMemo(
    () => session?.username || session?.first_name || `tg:${session?.telegram_id ?? "?"}`,
    [session]
  );

  if (state === "loading") {
    return <div className="login-screen"><div className="login-card">Loading session…</div></div>;
  }

  if (!session) {
    return (
      <LoginPage
        onAuthenticated={(nextSession) => {
          setSession(nextSession);
          setState("ready");
        }}
      />
    );
  }

  return (
    <Routes>
      <Route
        element={
          <Layout
            username={displayName}
            onLogout={async () => {
              await api.logout().catch(() => undefined);
              setSession(null);
              setState("guest");
            }}
          />
        }
      >
        <Route path="/" element={<ReviewQueuePage />} />
        <Route path="/reviews/:caseId" element={<ReviewDetailPage />} />
        <Route path="/rules" element={<RulesPage />} />
        <Route path="/quality" element={<QualityPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
