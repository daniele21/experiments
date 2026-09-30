import { useEffect, useMemo, useState } from "react";

const TYPE_LABELS = {
  private_person: "Personal names",
  private_email: "Email addresses",
  private_phone: "Phone numbers",
  private_address: "Addresses & locations",
  private_date: "Dates",
  private_url: "Personal URLs",
  account_number: "Identifiers & account numbers",
  personal_demographic: "Demographic information",
  secret: "Private access information",
  health_condition: "Health conditions",
  health_treatment: "Treatments & medications",
  health_lab_result: "Lab & clinical results",
  personal_measurement: "Body & biometric measurements",
  lifestyle_info: "Lifestyle information",
};

function typeLabel(type) {
  if (TYPE_LABELS[type]) return TYPE_LABELS[type];
  return String(type ?? "Sensitive data")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function profileLabel(profile) {
  return String(profile ?? "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function PIIScopeDrawer({
  open,
  taxonomy,
  initialProfile = "general",
  focusedType = null,
  onClose,
}) {
  const profiles = taxonomy?.profiles ?? {};
  const profileNames = Object.keys(profiles);
  const fallbackProfile = profileNames.includes(initialProfile)
    ? initialProfile
    : profileNames[0] ?? "general";
  const [activeProfile, setActiveProfile] = useState(fallbackProfile);
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!open) return;
    setActiveProfile(
      profileNames.includes(initialProfile)
        ? initialProfile
        : profileNames[0] ?? "general",
    );
    setSearch("");
  }, [open, initialProfile, profileNames.join("|")]);

  useEffect(() => {
    if (!open || !focusedType) return;
    window.requestAnimationFrame(() => {
      document
        .getElementById(`pii-definition-${focusedType}`)
        ?.scrollIntoView({ block: "center", behavior: "smooth" });
    });
  }, [open, focusedType, activeProfile]);

  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => {
      if (event.key === "Escape") onClose?.();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  const definitions = profiles[activeProfile] ?? {};
  const rows = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase();
    return Object.entries(definitions)
      .map(([type, spec]) => ({
        type,
        label: typeLabel(type),
        description: spec?.description ?? "",
        examples: spec?.examples ?? [],
      }))
      .filter((row) => {
        if (!needle) return true;
        return [row.type, row.label, row.description, ...row.examples].some(
          (value) =>
            String(value ?? "").toLocaleLowerCase().includes(needle),
        );
      });
  }, [definitions, search]);

  if (!open) return null;

  return (
    <div className="pii-scope-overlay" onMouseDown={onClose}>
      <aside
        className="pii-scope-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="pii-scope-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="pii-scope-drawer__header">
          <div>
            <span className="client-journey-kicker">Detection scope</span>
            <h2 id="pii-scope-title">PII definitions</h2>
            <p>Definitions used by this benchmark when evaluating detection.</p>
          </div>
          <button
            type="button"
            className="pii-scope-close"
            onClick={onClose}
            aria-label="Close PII definitions"
          >
            ×
          </button>
        </header>

        <div className="pii-scope-provenance">
          <span>{taxonomy?.source?.contract_version ?? "Detection contract"}</span>
          {taxonomy?.source?.ref ? (
            <code>{String(taxonomy.source.ref).slice(0, 8)}</code>
          ) : null}
        </div>

        <nav className="pii-scope-profiles" aria-label="PII profile">
          {profileNames.map((profile) => (
            <button
              key={profile}
              type="button"
              className={profile === activeProfile ? "active" : ""}
              onClick={() => setActiveProfile(profile)}
            >
              {profileLabel(profile)}
              <span>{Object.keys(profiles[profile] ?? {}).length}</span>
            </button>
          ))}
        </nav>

        <label className="pii-scope-search">
          <span>Search definitions</span>
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Name, definition, example…"
          />
        </label>

        <div className="pii-scope-list">
          {rows.map((row) => (
            <article
              id={`pii-definition-${row.type}`}
              key={row.type}
              className={`pii-definition-card ${
                focusedType === row.type ? "pii-definition-card--focused" : ""
              }`}
            >
              <div className="pii-definition-card__title">
                <strong>{row.label}</strong>
                <code>{row.type}</code>
              </div>
              <p>{row.description}</p>
              {row.examples.length ? (
                <details>
                  <summary>Examples ({row.examples.length})</summary>
                  <div className="pii-definition-examples">
                    {row.examples.map((example) => (
                      <span key={example}>{example}</span>
                    ))}
                  </div>
                </details>
              ) : null}
            </article>
          ))}
          {!rows.length ? (
            <div className="pii-scope-empty">No matching definitions.</div>
          ) : null}
        </div>

        <footer className="pii-scope-drawer__footer">
          Definitions are profile-specific: the same PII type can change scope with
          the active policy.
        </footer>
      </aside>
    </div>
  );
}

export default PIIScopeDrawer;
