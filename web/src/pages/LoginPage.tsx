import { useEffect, useState } from "react";

import { api, Session } from "../api/client";

declare global {
  interface Window {
    onTelegramAuth?: (user: Record<string, unknown>) => void;
  }
}

type LoginPageProps = {
  onAuthenticated: (session: Session) => void;
};

export function LoginPage({ onAuthenticated }: LoginPageProps) {
  const [error, setError] = useState("");
  const [botUsername, setBotUsername] = useState("");

  useEffect(() => {
    api
      .authStart()
      .then((payload) => setBotUsername(payload.bot_username))
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!botUsername) return;

    window.onTelegramAuth = async (user) => {
      try {
        const session = await api.authVerify(user);
        onAuthenticated(session);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Auth failed");
      }
    };

    const container = document.getElementById("telegram-login-slot");
    if (!container) return;
    container.innerHTML = "";

    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.setAttribute("data-telegram-login", botUsername);
    script.setAttribute("data-size", "large");
    script.setAttribute("data-userpic", "false");
    script.setAttribute("data-request-access", "write");
    script.setAttribute("data-onauth", "onTelegramAuth(user)");
    container.appendChild(script);
  }, [botUsername, onAuthenticated]);

  return (
    <div className="login-screen">
      <div className="login-card">
        <span className="eyebrow">Remnawave + MobGuard</span>
        <h1>Веб-панель модерации и live-правил</h1>
        <p>
          Очередь спорных кейсов, quality-метрики и редактирование ASN/keywords/thresholds без
          рестарта core.
        </p>
        <div id="telegram-login-slot" className="telegram-slot" />
        {!botUsername && !error ? <p className="muted">Загружаю Telegram auth…</p> : null}
        {error ? <div className="error-box">{error}</div> : null}
      </div>
    </div>
  );
}
