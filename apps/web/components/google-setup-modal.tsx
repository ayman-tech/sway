"use client";

import { useEffect, useState } from "react";
import { Copy, Loader2, X } from "lucide-react";
import { api } from "@/lib/api";

export function GoogleSetupModal({
  clientId,
  open,
  redirectUri,
  onClose,
}: {
  clientId?: string | null;
  open: boolean;
  redirectUri: string;
  onClose: () => void;
}) {
  const [id, setId] = useState("");
  const [secret, setSecret] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setId(clientId ?? "");
    setSecret("");
    setError("");
    setSaving(false);
  }, [clientId, open]);

  if (!open) return null;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!id.trim() || !secret.trim()) {
      setError("Client ID and client secret are required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const result = await api<{ url: string }>("/integrations/google/credentials", {
        method: "PUT",
        body: JSON.stringify({ client_id: id.trim(), client_secret: secret.trim() }),
      });
      window.location.href = result.url;
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Unable to save Google credentials.");
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/45 px-4 py-8">
      <form className="panel max-h-[92vh] w-full max-w-[560px] overflow-auto p-5 shadow-2xl" onSubmit={submit}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-black">Set up Google Calendar</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Create an OAuth client of type Web application in Google Cloud, then paste its credentials here.
            </p>
          </div>
          <button className="btn btn-secondary min-w-10 px-2" onClick={onClose} type="button">
            <X size={18} />
          </button>
        </div>

        <ol className="mt-4 list-decimal space-y-1 pl-5 text-sm text-[var(--muted)]">
          <li>Enable the Google Calendar API and configure the OAuth consent screen.</li>
          <li>Create an OAuth client ID of type Web application.</li>
          <li>Add the callback URI below as an authorized redirect URI.</li>
        </ol>

        <label className="mt-4 block text-sm font-bold">
          Callback URI
          <div className="mt-1 flex gap-2">
            <input className="field" readOnly value={redirectUri} />
            <button
              className="btn btn-secondary px-3"
              onClick={() => navigator.clipboard.writeText(redirectUri)}
              title="Copy callback URI"
              type="button"
            >
              <Copy size={17} />
            </button>
          </div>
        </label>
        <label className="mt-3 block text-sm font-bold">
          Client ID
          <input
            autoComplete="off"
            className="field mt-1"
            onChange={(event) => setId(event.target.value)}
            placeholder="xxxx.apps.googleusercontent.com"
            value={id}
          />
        </label>
        <label className="mt-3 block text-sm font-bold">
          Client secret
          <input
            autoComplete="new-password"
            className="field mt-1"
            onChange={(event) => setSecret(event.target.value)}
            placeholder="GOCSPX-..."
            type="password"
            value={secret}
          />
        </label>
        {error ? <p className="mt-3 text-sm font-bold text-[#b42318]">{error}</p> : null}
        <div className="mt-5 flex justify-end gap-3">
          <button className="btn btn-secondary" onClick={onClose} type="button">Cancel</button>
          <button className="btn btn-primary" disabled={saving} type="submit">
            {saving ? <Loader2 className="animate-spin" size={18} /> : null}
            Save & Connect
          </button>
        </div>
      </form>
    </div>
  );
}
