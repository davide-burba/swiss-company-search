import { useEffect, useRef, useState } from "react";

const API = "";
const PAGE_SIZE = 50;


interface Company {
  uid: string;
  org: string;
  legal_name: string;
  legal_form: string;
  canton: string;
  city: string;
  street: string | null;
  zip: string | null;
  description: string | null;
  description_lang: string | null;
  description_en: string | null;
  sector_section: string | null;
  sector_division: string | null;
  lat: number | null;
  lng: number | null;
  cantonal_excerpt_url: string;
}

function FilterSelect({ value, onChange, options, placeholder, disabled, alignRight }: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  placeholder: string;
  disabled?: boolean;
  alignRight?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    function onOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onOutside);
    return () => document.removeEventListener("mousedown", onOutside);
  }, []);
  const selectedLabel = options.find((o) => o.value === value)?.label;
  return (
    <div className="filter-multiselect-wrap" ref={ref}>
      <button className="filter-multiselect-btn" onClick={() => !disabled && setOpen((o) => !o)} disabled={disabled}>
        {selectedLabel ?? placeholder}
      </button>
      {open && (
        <div className={`filter-multiselect-dropdown${alignRight ? " filter-multiselect-dropdown--right" : ""}`}>
          <div className={`filter-multiselect-item${!value ? " filter-multiselect-item--active" : ""}`} onClick={() => { onChange(""); setOpen(false); }}>
            {placeholder}
          </div>
          {options.map((o) => (
            <div key={o.value} className={`filter-multiselect-item${value === o.value ? " filter-multiselect-item--active" : ""}`} onClick={() => { onChange(o.value); setOpen(false); }}>
              {o.label}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [results, setResults] = useState<Company[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [legalForms, setLegalForms] = useState<Record<string, string>>({});
  const [cantons, setCantons] = useState<{ id: string; name: string }[]>([]);
  const [cities, setCities] = useState<{ name: string; zip: string | null }[]>([]);
  const [sectors, setSectors] = useState<{ id: string; name: string }[]>([]);
  const [divisions, setDivisions] = useState<{ id: string; name: string }[]>([]);
  const [divisionMap, setDivisionMap] = useState<Record<string, Record<string, string>>>({});
  const fetchedSectionsRef = useRef<Set<string>>(new Set());

  const [q, setQ] = useState("");
  const [legalForm, setLegalForm] = useState<string[]>([]);
  const [legalFormOpen, setLegalFormOpen] = useState(false);
  const legalFormRef = useRef<HTMLDivElement>(null);
  const [cityOpen, setCityOpen] = useState(false);
  const cityWrapRef = useRef<HTMLDivElement>(null);
  const [canton, setCanton] = useState("");
  const [city, setCity] = useState("");
  const [sectorSection, setSectorSection] = useState("");
  const [sectorDivision, setSectorDivision] = useState("");
  const [page, setPage] = useState(1);
  const [searchMode, setSearchMode] = useState<"text" | "hybrid">("text");

  const [locationLat, setLocationLat] = useState<number | null>(null);
  const [locationLng, setLocationLng] = useState<number | null>(null);
  const [locationLabel, setLocationLabel] = useState<string | null>(null);
  const [radiusKm, setRadiusKm] = useState(10);
  const [locationStatus, setLocationStatus] = useState<"idle" | "loading" | "error">("idle");
  const [customAddress, setCustomAddress] = useState("");
  const [locationSuggestions, setLocationSuggestions] = useState<{ lat: string; lon: string; display_name: string }[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const locationDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    fetch(`${API}/legal-forms`)
      .then((r) => r.json())
      .then((data: Record<string, string>) => setLegalForms(data))
      .catch(() => {});
    fetch(`${API}/cantons`)
      .then((r) => r.json())
      .then((data: { id: string; name: string }[]) => setCantons(data))
      .catch(() => {});
    fetch(`${API}/sectors`)
      .then((r) => r.json())
      .then((data: { id: string; name: string }[]) => setSectors(data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    setCity("");
    fetch(`${API}/cantons/${canton || "-"}/cities`)
      .then((r) => r.json())
      .then((data: { name: string; zip: string | null }[]) => setCities(data))
      .catch(() => setCities([]));
  }, [canton]);

  useEffect(() => {
    setSectorDivision("");
    if (!sectorSection) {
      setDivisions([]);
      return;
    }
    fetch(`${API}/sectors/${sectorSection}/divisions`)
      .then((r) => r.json())
      .then((data: { id: string; name: string }[]) => setDivisions(data))
      .catch(() => setDivisions([]));
  }, [sectorSection]);

  useEffect(() => {
    function onOutside(e: MouseEvent) {
      if (legalFormRef.current && !legalFormRef.current.contains(e.target as Node)) setLegalFormOpen(false);
      if (cityWrapRef.current && !cityWrapRef.current.contains(e.target as Node)) setCityOpen(false);
    }
    document.addEventListener("mousedown", onOutside);
    return () => document.removeEventListener("mousedown", onOutside);
  }, []);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      const params = new URLSearchParams({
        q,
        canton,
        city,
        sector_section: sectorSection,
        sector_division: sectorDivision,
        limit: String(PAGE_SIZE),
        offset: String((page - 1) * PAGE_SIZE),
        ...(q ? { search: searchMode } : {}),
        ...(locationLat !== null && locationLng !== null
          ? { lat: String(locationLat), lng: String(locationLng), radius_km: String(radiusKm) }
          : {}),
      });
      legalForm.forEach((f) => params.append("legal_form", f));
      // Remove empty params
      for (const [k, v] of [...params.entries()]) {
        if (!v) params.delete(k);
      }
      setLoading(true);
      setError(null);
      fetch(`${API}/companies?${params}`)
        .then((r) => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          return r.json();
        })
        .then((data: { items: Company[]; total: number }) => {
          setResults(data.items);
          setTotal(data.total);
          setLoading(false);
          const newSections = [...new Set(data.items.map((c) => c.sector_section).filter(Boolean) as string[])]
            .filter((s) => !fetchedSectionsRef.current.has(s));
          newSections.forEach((s) => {
            fetchedSectionsRef.current.add(s);
            fetch(`${API}/sectors/${s}/divisions`)
              .then((r) => r.json())
              .then((divs: { id: string; name: string }[]) => {
                setDivisionMap((prev) => ({
                  ...prev,
                  [s]: Object.fromEntries(divs.map((d) => [d.id, d.name])),
                }));
              })
              .catch(() => {});
          });
        })
        .catch(() => {
          setError("Failed to fetch results — is the API running?");
          setLoading(false);
        });
    }, 300);
  }, [q, legalForm, canton, city, sectorSection, sectorDivision, page, locationLat, locationLng, radiusKm, searchMode]);

  function applyLocation(lat: number, lng: number, label: string) {
    setLocationLat(lat);
    setLocationLng(lng);
    setLocationLabel(label);
    setLocationStatus("idle");
    setCustomAddress("");
    setPage(1);
  }

  function useMyLocation() {
    if (!navigator.geolocation) {
      setLocationStatus("error");
      return;
    }
    setLocationStatus("loading");
    navigator.geolocation.getCurrentPosition(
      (pos) => applyLocation(pos.coords.latitude, pos.coords.longitude, "Current location"),
      () => setLocationStatus("error"),
    );
  }

  function handleLocationInput(val: string) {
    setCustomAddress(val);
    setShowSuggestions(false);
    if (locationDebounceRef.current) clearTimeout(locationDebounceRef.current);
    if (!val.trim()) { setLocationSuggestions([]); return; }
    locationDebounceRef.current = setTimeout(() => {
      const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(val)}&format=json&limit=5&countrycodes=ch`;
      fetch(url, { headers: { "Accept-Language": "en" } })
        .then((r) => r.json())
        .then((data: { lat: string; lon: string; display_name: string }[]) => {
          setLocationSuggestions(data);
          setShowSuggestions(data.length > 0);
        })
        .catch(() => setLocationSuggestions([]));
    }, 350);
  }

  function clearLocation() {
    setLocationLat(null);
    setLocationLng(null);
    setLocationLabel(null);
    setLocationStatus("idle");
    setCustomAddress("");
    setPage(1);
  }

  function handleSearchChange(val: string) {
    setQ(val);
    setPage(1);
  }

  function filterChange(setter: (v: string) => void) {
    return (v: string) => { setter(v); setPage(1); };
  }

  const totalPages = Math.ceil(total / PAGE_SIZE) || 1;
  const hasMore = page < totalPages;

  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [origDescOpen, setOrigDescOpen] = useState(false);

  type ColKey = "uid" | "address" | "legalForm" | "canton" | "sector" | "division" | "description" | "links";
  const ALL_COLS: { key: ColKey; label: string }[] = [
    { key: "uid", label: "UID" },
    { key: "address", label: "Address" },
    { key: "legalForm", label: "Legal form" },
    { key: "canton", label: "Canton" },
    { key: "sector", label: "Sector" },
    { key: "division", label: "Division" },
    { key: "description", label: "Description" },
    { key: "links", label: "Links" },
  ];
  const [cols, setCols] = useState<Record<ColKey, boolean>>({
    uid: false, address: true, legalForm: true, canton: false, sector: false, division: true, description: true, links: true,
  });
  const [colsOpen, setColsOpen] = useState(false);
  const toggleCol = (k: ColKey) => setCols((prev) => ({ ...prev, [k]: !prev[k] }));
  const visibleCount = 1 + ALL_COLS.filter((c) => cols[c.key]).length;

  return (
    <>
      <header>
        <div className="header-icon">
          <svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
            <rect x="8" y="2" width="4" height="16" rx="1"/>
            <rect x="2" y="8" width="16" height="4" rx="1"/>
          </svg>
        </div>
        <div className="header-text">
          <h1>Swiss Companies</h1>
          <p>Explore <em style={{color: '#555', fontWeight: 700, textDecoration: 'underline', textDecorationColor: 'var(--red)'}}>every</em> company in Switzerland</p>
        </div>
      </header>

      <div className="filters-panel">
        <div className="filters-row">
          <input
            className="search-input"
            type="text"
            placeholder="Search company…"
            value={q}
            onChange={(e) => handleSearchChange(e.target.value)}
          />
          <label className="search-mode-label">
            <input
              type="checkbox"
              checked={searchMode === "hybrid"}
              onChange={(e) => setSearchMode(e.target.checked ? "hybrid" : "text")}
            />
            Hybrid search
          </label>
          <div className="filter-multiselect-wrap" ref={legalFormRef}>
            <button className="filter-multiselect-btn" onClick={() => setLegalFormOpen((o) => !o)}>
              {legalForm.length === 0
                ? "All legal forms"
                : legalForm.length === 1
                  ? (legalForms[legalForm[0]] ?? legalForm[0])
                  : `${legalForm.length} forms`}
            </button>
            {legalFormOpen && (
              <div className="filter-multiselect-dropdown">
                {Object.entries(legalForms).map(([code, label]) => (
                  <label key={code} className="filter-multiselect-item">
                    <input
                      type="checkbox"
                      checked={legalForm.includes(code)}
                      onChange={() => {
                        setLegalForm((prev) =>
                          prev.includes(code) ? prev.filter((f) => f !== code) : [...prev, code]
                        );
                        setPage(1);
                      }}
                    />
                    <span>
                      {label}
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>
          <span className="filter-sep filter-sep--tall">|</span>
          <div className="filter-group">
            <span className="filter-label">Sector</span>
            <FilterSelect
              value={sectorSection}
              onChange={filterChange(setSectorSection)}
              options={sectors.map(({ id, name }) => ({ value: id, label: `${id} – ${name}` }))}
              placeholder="All sectors"
              alignRight
            />
            {sectorSection && (
              <FilterSelect
                value={sectorDivision}
                onChange={filterChange(setSectorDivision)}
                options={divisions.map(({ id, name }) => ({ value: id, label: `${id} – ${name}` }))}
                placeholder="All divisions"
                disabled={divisions.length === 0}
                alignRight
              />
            )}
          </div>
        </div>
        <div className="filters-row">
          <span className="filter-label">Location</span>
          <FilterSelect
            value={canton}
            onChange={filterChange(setCanton)}
            options={cantons.map(({ id, name }) => ({ value: id, label: `${name} (${id})` }))}
            placeholder="All cantons"
          />
          <div className="filter-multiselect-wrap" ref={cityWrapRef}>
            <input
              type="text"
              placeholder="City…"
              value={city}
              onChange={(e) => { setCity(e.target.value); setPage(1); setCityOpen(true); }}
              onFocus={() => setCityOpen(true)}
            />
            {cityOpen && cities.filter((c) => c.name.toLowerCase().includes(city.toLowerCase())).length > 0 && (
              <div className="filter-multiselect-dropdown">
                {cities
                  .filter((c) => c.name.toLowerCase().includes(city.toLowerCase()))
                  .slice(0, 20)
                  .map(({ name, zip }) => (
                    <div key={`${name}-${zip}`} className="filter-multiselect-item" onMouseDown={() => { setCity(name); setCityOpen(false); setPage(1); }}>
                      {name}{zip ? ` (${zip})` : ""}
                    </div>
                  ))}
              </div>
            )}
          </div>
          <span className="filter-sep">or</span>
          {locationLat !== null ? (
            <div className="location-active-group">
              <span className="location-active" title={`${locationLat.toFixed(6)}, ${locationLng!.toFixed(6)}`}>
                📍 {locationLabel}
              </span>
              <label>
                within
                <input
                  type="number"
                  min={1}
                  max={500}
                  value={radiusKm}
                  onChange={(e) => { setRadiusKm(Number(e.target.value)); setPage(1); }}
                />
                km
              </label>
              <button className="location-clear" onClick={clearLocation} title="Clear location">✕</button>
            </div>
          ) : (
            <div className="location-search-form">
              <div className="location-input-wrap">
                <div className="location-input-group">
                  <input
                    type="text"
                    className="location-custom-input"
                    placeholder="Enter address or city…"
                    value={customAddress}
                    onChange={(e) => handleLocationInput(e.target.value)}
                    onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
                    onFocus={() => locationSuggestions.length > 0 && setShowSuggestions(true)}
                  />
                </div>
                <button
                  type="button"
                  className="location-use-mine"
                  onClick={useMyLocation}
                  disabled={locationStatus === "loading"}
                >
                  {locationStatus === "loading" ? "detecting…" : "use my location"}
                </button>
              </div>
              {showSuggestions && (
                <ul className="location-suggestions">
                  {locationSuggestions.map((s, i) => (
                    <li key={i} onMouseDown={() => applyLocation(parseFloat(s.lat), parseFloat(s.lon), s.display_name)}>
                      {s.display_name}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {locationStatus === "error" && (
            <span className="location-error">Location not found</span>
          )}
        </div>
      </div>

      {error && <div className="error">{error}</div>}
      {loading && <div className="loading">Loading…</div>}

      {selectedCompany && (
        <div className="modal-backdrop" onClick={() => setSelectedCompany(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2 className="modal-title">{selectedCompany.legal_name}</h2>
                <span className="modal-uid">{selectedCompany.uid}</span>
              </div>
              <button className="modal-close" onClick={() => setSelectedCompany(null)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="modal-grid">
                <div className="modal-field">
                  <span className="modal-label">Legal form</span>
                  <span className="badge">{legalForms[selectedCompany.legal_form] ?? selectedCompany.legal_form}</span>
                </div>
                <div className="modal-field">
                  <span className="modal-label">Canton</span>
                  <span>{selectedCompany.canton}</span>
                </div>
                <div className="modal-field">
                  <span className="modal-label">Address</span>
                  <span>
                    {(() => {
                      const parts = [selectedCompany.street, [selectedCompany.zip, selectedCompany.city].filter(Boolean).join(" ")].filter(Boolean);
                      const address = parts.join(", ");
                      const query = encodeURIComponent(`${address}, Switzerland`);
                      return (
                        <a href={`https://www.google.com/maps/search/?api=1&query=${query}`} target="_blank" rel="noreferrer">
                          {address || selectedCompany.city}
                        </a>
                      );
                    })()}
                  </span>
                </div>
                {selectedCompany.sector_section && (
                  <div className="modal-field">
                    <span className="modal-label">Sector</span>
                    <span>
                      {sectors.find((s) => s.id === selectedCompany.sector_section)?.name ?? selectedCompany.sector_section}
                      {selectedCompany.sector_division && (
                        <> › {divisionMap[selectedCompany.sector_section!]?.[selectedCompany.sector_division] ?? selectedCompany.sector_division}</>
                      )}
                    </span>
                  </div>
                )}
              </div>

              {(selectedCompany.description_en ?? selectedCompany.description) && (
                <div className="modal-section">
                  <span className="modal-label">Description</span>
                  <p className="modal-description">{selectedCompany.description_en ?? selectedCompany.description}</p>
                  {selectedCompany.description_en && selectedCompany.description && selectedCompany.description_lang !== "en" && (
                    <div className="modal-orig-desc">
                      <button className="modal-orig-desc-toggle" onClick={() => setOrigDescOpen((o) => !o)}>
                        Original language {origDescOpen ? "▲" : "▼"}
                      </button>
                      {origDescOpen && (
                        <p className="modal-description modal-description--original">{selectedCompany.description}</p>
                      )}
                    </div>
                  )}
                </div>
              )}

              <div className="modal-links">
                <a className="link-chip" href={`https://www.uid.admin.ch/Detail.aspx?uid_id=${selectedCompany.uid.replace(/[-\.]/g, "")}`} target="_blank" rel="noreferrer">UID Registry ↗</a>
                <a className="link-chip" href={selectedCompany.cantonal_excerpt_url} target="_blank" rel="noreferrer">Commercial Registry ↗</a>
              </div>
            </div>
          </div>
        </div>
      )}

      {!loading && (
        <>
          <div className="table-toolbar">
            <div className="col-toggle-wrap">
              <button className="col-toggle-btn" onClick={() => setColsOpen((o) => !o)}>
                Columns {colsOpen ? "▲" : "▼"}
              </button>
              {colsOpen && (
                <div className="col-toggle-dropdown">
                  {ALL_COLS.map(({ key, label }) => (
                    <label key={key} className="col-toggle-item">
                      <input type="checkbox" checked={cols[key]} onChange={() => toggleCol(key)} />
                      {label}
                    </label>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Company name</th>
                  {cols.uid && <th>UID</th>}
                  {cols.address && <th>Address</th>}
                  {cols.legalForm && <th>Legal form</th>}
                  {cols.canton && <th>Canton</th>}
                  {cols.sector && <th>Sector</th>}
                  {cols.division && <th>Division</th>}
                  {cols.description && <th>Description</th>}
                  {cols.links && <th>Links</th>}
                </tr>
              </thead>
              <tbody>
                {results.length === 0 ? (
                  <tr><td colSpan={visibleCount} className="empty-state">No companies found</td></tr>
                ) : results.map((c) => (
                  <tr key={c.uid} className="tr-clickable" onClick={() => { setSelectedCompany(c); setOrigDescOpen(false); }}>
                    <td className="td-name">{c.legal_name}</td>
                    {cols.uid && <td className="td-uid">{c.uid}</td>}
                    {cols.address && (
                      <td className="td-address">
                        {(() => {
                          const parts = [c.street, [c.zip, c.city].filter(Boolean).join(" ")].filter(Boolean);
                          const address = parts.join(", ");
                          const query = encodeURIComponent(`${address}, Switzerland`);
                          return (
                            <a href={`https://www.google.com/maps/search/?api=1&query=${query}`} target="_blank" rel="noreferrer">
                              {address || c.city}
                            </a>
                          );
                        })()}
                      </td>
                    )}
                    {cols.legalForm && (
                      <td><span className="badge">{legalForms[c.legal_form] ?? c.legal_form}</span></td>
                    )}
                    {cols.canton && <td>{c.canton}</td>}
                    {cols.sector && (
                      <td>{c.sector_section ? (sectors.find((s) => s.id === c.sector_section)?.name ?? c.sector_section) : "—"}</td>
                    )}
                    {cols.division && (
                      <td>{c.sector_division ? (divisionMap[c.sector_section!]?.[c.sector_division] ?? c.sector_division) : "—"}</td>
                    )}
                    {cols.description && (
                      <td className="td-description">
                        <span className="td-description-text">
                          {c.description_en ?? c.description ?? "—"}
                        </span>
                      </td>
                    )}
                    {cols.links && (
                      <td className="td-links" onClick={(e) => e.stopPropagation()}>
                        <div className="links-row">
                          <a className="link-chip" href={`https://www.uid.admin.ch/Detail.aspx?uid_id=${c.uid.replace(/[-\.]/g, "")}`} target="_blank" rel="noreferrer">UID Registry ↗</a>
                          <a className="link-chip" href={c.cantonal_excerpt_url} target="_blank" rel="noreferrer">Commercial Registry ↗</a>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="pagination">
            <button onClick={() => setPage(1)} disabled={page === 1}>«</button>
            <button onClick={() => setPage((p) => p - 1)} disabled={page === 1}>‹</button>
            <span className="page-info">Page {page} of {totalPages} <span className="page-total">({total.toLocaleString()} companies)</span></span>
            <button onClick={() => setPage((p) => p + 1)} disabled={!hasMore}>›</button>
            <button onClick={() => setPage(totalPages)} disabled={page === totalPages}>»</button>
          </div>
        </>
      )}
    </>
  );
}
