import { initializeApp } from "https://www.gstatic.com/firebasejs/12.19.0/firebase-app.js";
import {
  initializeAuth,
  browserLocalPersistence,
  isSignInWithEmailLink,
  sendSignInLinkToEmail,
  signInWithEmailLink
} from "https://www.gstatic.com/firebasejs/12.19.0/firebase-auth.js";

const root = document.querySelector("[data-firebase-email-link]");
const form = root?.querySelector("[data-email-form]");
const emailInput = root?.querySelector("[data-email]");
const status = root?.querySelector("[data-auth-status]");
const submit = root?.querySelector("[data-email-submit]");

function setStatus(message, kind = "info") {
  if (!status) return;
  status.textContent = message;
  status.dataset.kind = kind;
}

function friendlyError(error) {
  const code = String(error?.code || error?.message || "unknown_error");
  if (code.includes("operation-not-allowed")) return "Passwordless email sign-in is not enabled.";
  if (code.includes("unauthorized-domain")) return "This Mesh hostname is not authorized for Firebase sign-in.";
  if (code.includes("invalid-api-key")) return "Firebase web configuration is invalid.";
  if (code.includes("network-request-failed")) return "Firebase could not be reached from this browser.";
  if (code.includes("invalid-action-code") || code.includes("expired-action-code")) return "This sign-in link is invalid or expired.";
  return `Cloud sign-in initialization failed (${code}).`;
}

async function loadConfig() {
  const response = await fetch("/api/auth/firebase/config", {credentials: "same-origin"});
  const body = await response.json();
  if (!response.ok || !body.ok) throw new Error(body.error || `config_${response.status}`);
  return body.config;
}

async function establishServerSession(user) {
  const idToken = await user.getIdToken(true);
  const response = await fetch("/api/auth/firebase/session", {
    method: "POST",
    credentials: "same-origin",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({idToken})
  });
  const body = await response.json();
  if (!response.ok || !body.ok) throw new Error(body.error || `session_${response.status}`);
}

async function bootstrap() {
  if (!root) return;

  const config = await loadConfig();
  const app = initializeApp(config);

  // Email-link authentication does not need popup/redirect OAuth machinery.
  // initializeAuth with only browser persistence avoids Firebase's default
  // redirect/auth-domain iframe bootstrap on Cloud Run.
  const auth = initializeAuth(app, {
    persistence: browserLocalPersistence
  });

  setStatus("Passwordless cloud sign-in is ready.", "success");
  if (submit) submit.disabled = false;

  if (isSignInWithEmailLink(auth, window.location.href)) {
    let email = window.localStorage.getItem("meshEmailForSignIn");
    if (!email) email = window.prompt("Confirm the email address that received this sign-in link:");
    if (!email) return setStatus("Email confirmation is required.", "error");

    setStatus("Completing sign-in…");
    try {
      const result = await signInWithEmailLink(auth, email, window.location.href);
      await establishServerSession(result.user);
      window.localStorage.removeItem("meshEmailForSignIn");
      window.location.replace("/");
    } catch (error) {
      console.error("Mesh Firebase email-link completion failed", error);
      setStatus(friendlyError(error), "error");
    }
    return;
  }

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = String(emailInput?.value || "").trim().toLowerCase();
    if (!email) return;

    submit.disabled = true;
    setStatus("Sending secure sign-in link…");

    try {
      await sendSignInLinkToEmail(auth, email, {
        url: `${window.location.origin}/login`,
        handleCodeInApp: true
      });
      window.localStorage.setItem("meshEmailForSignIn", email);
      setStatus("Check your email for the Mesh sign-in link.", "success");
    } catch (error) {
      console.error("Mesh Firebase email-link send failed", error);
      setStatus(friendlyError(error), "error");
      submit.disabled = false;
    }
  });
}

bootstrap().catch((error) => {
  console.error("Mesh Firebase bootstrap failed", error);
  setStatus(friendlyError(error), "error");
  if (submit) submit.disabled = true;
});
