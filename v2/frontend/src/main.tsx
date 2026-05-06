import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { MsalProvider, MsalAuthenticationTemplate } from "@azure/msal-react";
import { InteractionType } from "@azure/msal-browser";
import { authEnabled, initializeMsal, loginRequest, getMsalInstance, isMsalTimeout } from "@/lib/auth";
import App from "./App";
import "./index.css";

const TIMEOUT_REDIRECT_KEY = "qs_auth_timeout_retries";
const MAX_TIMEOUT_RETRIES = 2;

function LoadingScreen() {
  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}>
      <p>Signing in…</p>
    </div>
  );
}

function AuthError({ error }: { error: Error | null }) {
  const isTimeout = isMsalTimeout(error);

  useEffect(() => {
    if (!isTimeout) return;

    const attempts = parseInt(sessionStorage.getItem(TIMEOUT_REDIRECT_KEY) || "0", 10);
    if (attempts >= MAX_TIMEOUT_RETRIES) {
      sessionStorage.removeItem(TIMEOUT_REDIRECT_KEY);
      return;
    }
    sessionStorage.setItem(TIMEOUT_REDIRECT_KEY, String(attempts + 1));

    const msal = getMsalInstance();
    msal.acquireTokenRedirect(loginRequest).catch(() => {});
  }, [isTimeout]);

  if (isTimeout) {
    const attempts = parseInt(sessionStorage.getItem(TIMEOUT_REDIRECT_KEY) || "0", 10);
    if (attempts < MAX_TIMEOUT_RETRIES) {
      return (
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}>
          <p>Signing in…</p>
        </div>
      );
    }
  }

  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh", flexDirection: "column", gap: "1rem" }}>
      <p>Authentication error</p>
      <p style={{ fontSize: "0.875rem", color: "#666" }}>{error?.message}</p>
      <button onClick={() => {
        sessionStorage.removeItem(TIMEOUT_REDIRECT_KEY);
        window.location.reload();
      }}>Retry</button>
    </div>
  );
}

async function bootstrap() {
  const root = createRoot(document.getElementById("root")!);

  if (authEnabled) {
    const msalInstance = await initializeMsal();
    root.render(
      <StrictMode>
        <MsalProvider instance={msalInstance}>
          <MsalAuthenticationTemplate
            interactionType={InteractionType.Redirect}
            authenticationRequest={loginRequest}
            loadingComponent={LoadingScreen}
            errorComponent={AuthError as never}
          >
            <App />
          </MsalAuthenticationTemplate>
        </MsalProvider>
      </StrictMode>,
    );
  } else {
    root.render(
      <StrictMode>
        <App />
      </StrictMode>,
    );
  }
}

bootstrap();
