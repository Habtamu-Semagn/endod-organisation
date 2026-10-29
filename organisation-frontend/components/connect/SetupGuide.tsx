"use client";

import { ErrorBanner, useApi } from "@/components/ui";
import { isConnectionId, type ApiInfo, type Connection } from "@/lib/connect";

/**
 * A printable page for the company's IT team: the connection's details,
 * where to get a token, and the developer guide. Never the secret (it was
 * shown once, when the system was connected).
 */
export default function SetupGuide({ id }: { id: string }) {
  const valid = isConnectionId(id);
  const { data, error } = useApi<ApiInfo & { connection: Connection }>(valid ? `connections/${id}` : null);

  if (!valid) return <Frame><ErrorBanner message="Unknown connection." /></Frame>;
  if (error) return <Frame><ErrorBanner message={error} /></Frame>;
  if (!data) return <Frame><p className="font-body-sm text-body-sm text-on-surface-variant">Preparing the setup guide…</p></Frame>;
  const c = data.connection;
  const rows: [string, string][] = [
    ["System", c.name],
    ["Mode", c.mode === "live" ? "Live (real data)" : "Test (checks everything, saves nothing)"],
    ["Client ID", c.client_id],
    ["Client secret", "Not in this guide: it was shown once, when the system was connected. Keep it in your secret store."],
    [
      "Authentication",
      c.auth_method === "private_key_jwt"
        ? "Signed client assertion (private_key_jwt, ES256 or RS256)"
        : "Client secret (OAuth 2.0 client credentials: HTTP Basic or form)",
    ],
    ["Token URL", data.token_url],
    ["API base URL", data.api_url],
    ["OpenAPI", data.openapi_url],
    ["Token signing keys", data.jwks_url],
    ["Developer guide", data.docs_url],
  ];
  if (c.webhook_url) rows.push(["Webhook URL", c.webhook_url]);
  if (c.allowed_ips.length) rows.push(["Allowed addresses", c.allowed_ips.join(", ")]);
  const granted = data.scopes.filter((s) => c.scopes.includes(s.scope));

  return (
    <Frame>
      <div data-testid="setup-guide" className="flex flex-col gap-space-lg">
        <div className="flex items-start justify-between gap-space-md">
          <div>
            <p className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold">TenaCare by Endod Health</p>
            <h1 className="font-headline-lg text-headline-lg text-on-surface font-bold">Setup guide: {c.name}</h1>
          </div>
          <button
            type="button"
            onClick={() => window.print()}
            className="print:hidden px-4 py-2 rounded-lg bg-primary text-on-primary font-label-lg text-label-lg font-semibold hover:bg-secondary"
          >
            Print or save as PDF
          </button>
        </div>
        <table className="w-full border-collapse text-left">
          <tbody>
            {rows.map(([label, value]) => (
              <tr key={label} className="border-t border-surface-variant align-top">
                <th className="w-56 py-2 pr-4 font-label-lg text-label-lg text-on-surface-variant font-semibold">{label}</th>
                <td className="break-all py-2 font-mono text-xs">{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <section>
          <h2 className="mb-2 font-headline-sm text-headline-sm font-semibold">What it may do (scopes)</h2>
          <table className="w-full border-collapse text-left">
            <tbody>
              {granted.map((s) => (
                <tr key={s.scope} className="border-t border-surface-variant align-top">
                  <th className="w-56 py-2 pr-4 font-label-lg text-label-lg text-on-surface-variant font-semibold">{s.label}</th>
                  <td className="py-2">
                    <code className="font-mono text-xs">{s.scope}</code>
                    <span className="block font-body-sm text-body-sm text-on-surface-variant">{s.description}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section>
          <h2 className="mb-2 font-headline-sm text-headline-sm font-semibold">Get a token</h2>
          <pre className="overflow-x-auto rounded-lg bg-surface-container-low p-3 text-xs">
            {`curl -s ${data.token_url} \\\n  -u "${c.client_id}:$CLIENT_SECRET" \\\n  -d grant_type=client_credentials`}
          </pre>
        </section>
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          The full guide (employees, claims, payments, notifications, errors and limits): {data.docs_url}
        </p>
      </div>
    </Frame>
  );
}

function Frame({ children }: { children: React.ReactNode }) {
  return <main className="mx-auto w-full max-w-3xl bg-surface-container-lowest p-8 text-on-surface print:p-0">{children}</main>;
}
