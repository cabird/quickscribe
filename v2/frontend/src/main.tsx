import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { MsalProvider, MsalAuthenticationTemplate } from "@azure/msal-react";
import { InteractionType } from "@azure/msal-browser";
import { authEnabled, initializeMsal, loginRequest } from "@/lib/auth";
import App from "./App";
import "./index.css";

function LoadingScreen() {
  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}>
      <p>Signing in…</p>
    </div>
  );
}

function AuthError({ error }: { error: Error | null }) {
  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh", flexDirection: "column", gap: "1rem" }}>
      <p>Authentication error</p>
      <p style={{ fontSize: "0.875rem", color: "#666" }}>{error?.message}</p>
      <button onClick={() => window.location.reload()}>Retry</button>
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
