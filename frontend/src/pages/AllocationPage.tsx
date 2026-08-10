import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { allocateResources } from "../api";
import type { AllocationResources, AllocationUnallocated, CustomResourceCategory, CustomResourceInput } from "../types";

const initial: AllocationResources = { waterLiters: 500, tents: 100, medicalStaff: 20, blankets: 50 };
const maxCustomResources = 20;
const categoryLabels: Record<CustomResourceCategory, string> = {
  water: "Su",
  food: "Gıda",
  shelter: "Barınma",
  medical: "Sağlık",
  electricity: "Elektrik",
  general: "Genel"
};
const customResourceCategories = Object.keys(categoryLabels) as CustomResourceCategory[];
const fixedResourceFields = [
  { key: "waterLiters", label: "Su (litre)" },
  { key: "tents", label: "Çadır" },
  { key: "medicalStaff", label: "Sağlık personeli" },
  { key: "blankets", label: "Battaniye" }
] satisfies ReadonlyArray<{ key: keyof AllocationResources; label: string }>;
const unallocatedResources = [
  { id: "waterLiters", key: "waterLiters", label: "Su", unit: "litre" },
  { id: "tents", key: "tents", label: "Çadır", unit: "adet" },
  { id: "medicalStaff", key: "medicalStaff", label: "Sağlık personeli", unit: "kişi" },
  { id: "blankets", key: "blankets", label: "Battaniye", unit: "adet" }
] satisfies ReadonlyArray<{ id: string; key: keyof AllocationResources; label: string; unit: string }>;
const confirmUnaddedResourcesMessage = "Eklediğiniz özel kaynakları dağıtıma dahil etmek için önce Ekle butonuna basın.";

type CustomResourceErrorField = "name" | "quantity" | "unit";
type CustomResourceErrors = Partial<Record<CustomResourceErrorField, string>>;

interface CustomResourceRow {
  id: string;
  name: string;
  quantity: string;
  unit: string;
  category: CustomResourceCategory;
  isAdded: boolean;
  errors: CustomResourceErrors;
}

type AllocationMutationPayload = {
  resources: AllocationResources;
  customResources: CustomResourceInput[];
};

type CustomResourceParseResult =
  | { ok: true; resources: CustomResourceInput[] }
  | { ok: false; message: string };

type UnallocatedRow = {
  id: string;
  label: string;
  unit: string;
  amount: number;
  category?: CustomResourceCategory;
};

export function AllocationPage() {
  const [resources, setResources] = useState(initial);
  const [customResources, setCustomResources] = useState<CustomResourceRow[]>([]);
  const [customResourceError, setCustomResourceError] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: ({ resources: fixedResources, customResources: parsedCustomResources }: AllocationMutationPayload) =>
      allocateResources(fixedResources, parsedCustomResources)
  });
  const allocationResult = mutation.data;
  const allocationItems = allocationResult?.allocations ?? [];
  const allocationError = mutation.error ? `Kaynak dağıtımı hesaplanamadı: ${mutation.error.message}` : null;
  function update(field: keyof AllocationResources, value: string) {
    setResources(current => ({ ...current, [field]: parseNonNegativeInteger(value) }));
  }
  function addCustomResource() {
    if (customResources.length >= maxCustomResources) {
      setCustomResourceError("En fazla 20 özel kaynak ekleyebilirsiniz.");
      return;
    }
    setCustomResourceError(null);
    setCustomResources(current => [
      ...current,
      { id: crypto.randomUUID(), name: "", quantity: "", unit: "", category: "general", isAdded: false, errors: {} }
    ]);
  }
  function updateCustomResource<K extends keyof Omit<CustomResourceRow, "id">>(id: string, field: K, value: CustomResourceRow[K]) {
    setCustomResourceError(null);
    setCustomResources(current => current.map(row => {
      if (row.id !== id) return row;
      const errors = { ...row.errors };
      if (isCustomResourceErrorField(field)) delete errors[field];
      return { ...row, [field]: value, isAdded: false, errors };
    }));
  }
  function confirmCustomResource(id: string) {
    setCustomResourceError(null);
    setCustomResources(current => current.map(row => {
      if (row.id !== id) return row;
      const errors = validateCustomResourceRow(row);
      return Object.keys(errors).length ? { ...row, isAdded: false, errors } : { ...row, isAdded: true, errors: {} };
    }));
  }
  function removeCustomResource(id: string) {
    setCustomResourceError(null);
    setCustomResources(current => current.filter(row => row.id !== id));
  }
  function submitAllocation() {
    const parsedCustomResources = parseCustomResources(customResources);
    if (!parsedCustomResources.ok) {
      setCustomResourceError(parsedCustomResources.message);
      return;
    }
    setCustomResourceError(null);
    mutation.mutate({ resources, customResources: parsedCustomResources.resources });
  }
  return (
    <main className="page">
      <Link to="/admin">← Dashboard</Link>
      <header className="hero compact"><h1>Kaynak dağıtım copilot’u</h1><p>Miktarları algoritma hesaplar; AI yalnızca sonucu açıklar.</p></header>
      <section className="panel">
        <div className="resource-grid">
          {fixedResourceFields.map(field => (
            <Resource key={field.key} label={field.label} value={resources[field.key]} change={value => update(field.key, value)} />
          ))}
        </div>
        <button className="button secondary add-resource-button" type="button" disabled={customResources.length >= maxCustomResources} onClick={addCustomResource}>
          + Kaynak Ekle
        </button>
        {customResources.length > 0 && (
          <div className="custom-resource-list">
            {customResources.map(row => (
              <div className="custom-resource-row" key={row.id}>
                <label>Kaynak adı<input type="text" value={row.name} onChange={event => updateCustomResource(row.id, "name", event.target.value)} />{row.errors.name && <span className="field-error">{row.errors.name}</span>}</label>
                <label>Miktar<input type="number" min={1} step={1} value={row.quantity} onChange={event => updateCustomResource(row.id, "quantity", event.target.value)} />{row.errors.quantity && <span className="field-error">{row.errors.quantity}</span>}</label>
                <label>Birim<input type="text" value={row.unit} onChange={event => updateCustomResource(row.id, "unit", event.target.value)} />{row.errors.unit && <span className="field-error">{row.errors.unit}</span>}</label>
                <label>
                  İhtiyaç kategorisi
                  <select value={row.category} onChange={event => updateCustomResource(row.id, "category", event.target.value as CustomResourceCategory)}>
                    {customResourceCategories.map(category => <option key={category} value={category}>{categoryLabels[category]}</option>)}
                  </select>
                </label>
                <div className="custom-resource-actions">
                  <button className={`button custom-resource-confirm${row.isAdded ? " success" : ""}`} type="button" disabled={row.isAdded} onClick={() => confirmCustomResource(row.id)}>
                    {row.isAdded ? "✓ Eklendi" : "Ekle"}
                  </button>
                  <button className="button danger custom-resource-delete" type="button" onClick={() => removeCustomResource(row.id)}>Sil</button>
                </div>
              </div>
            ))}
          </div>
        )}
        {customResourceError && <p className="error-box">{customResourceError}</p>}
        <button className="button" disabled={mutation.isPending} onClick={submitAllocation}>{mutation.isPending ? "Hesaplanıyor…" : "Dağıtımı hesapla"}</button>
        {allocationError && <p className="error-box" role="alert">{allocationError}</p>}
      </section>
      {allocationResult && <>
        <section className="panel"><h2>Açıklama</h2><p>{allocationResult.explanation}</p></section>
        <section className="panel table-panel">
          <h2>Önerilen dağıtım</h2>
          <div className="table-scroll">
            <table className="city-allocation-table">
              <thead>
                <tr>
                  <th>Şehir</th>
                  <th>Su</th>
                  <th>Çadır</th>
                  <th>Sağlık</th>
                  <th>Battaniye</th>
                  <th>Ek kaynaklar</th>
                </tr>
              </thead>
              <tbody>
                {allocationItems.map(item => (
                  <tr key={item.city}>
                    <td><strong>{item.city}</strong></td>
                    <td>{item.waterLiters}</td>
                    <td>{item.tents}</td>
                    <td>{item.medicalStaff}</td>
                    <td>{item.blankets}</td>
                    <td><CustomResourceAllocationList resources={item.customResources} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <UnallocatedResourcesTable resources={allocationResult.unallocated} />
      </>}
    </main>
  );
}

function Resource({ label, value, change }: { label: string; value: number; change: (value: string) => void }) {
  return <label>{label}<input type="number" min={0} step={1} value={value} onChange={e => change(e.target.value)} /></label>;
}

function CustomResourceAllocationList({ resources }: { resources?: CustomResourceInput[] }) {
  const visibleResources = (resources ?? []).filter(resource => toSafeAmount(resource.quantity) > 0);
  if (!visibleResources.length) return <span className="muted">-</span>;

  return (
    <ul className="custom-allocation-list">
      {visibleResources.map((resource, index) => (
        <li key={`${resource.name}-${index}`}>
          <strong>{String(resource.name ?? "").trim() || "Özel kaynak"}</strong>
          <span>{formatQuantity(toSafeAmount(resource.quantity), resource.unit)}</span>
        </li>
      ))}
    </ul>
  );
}

function UnallocatedResourcesTable({ resources }: { resources?: AllocationUnallocated }) {
  const fixedRows: UnallocatedRow[] = unallocatedResources.map(resource => ({
    id: resource.id,
    label: resource.label,
    unit: resource.unit,
    amount: toSafeAmount(resources?.[resource.key])
  }));
  const customRows: UnallocatedRow[] = (resources?.customResources ?? []).map((resource, index) => ({
    id: `custom-${index}-${resource.name}`,
    label: String(resource.name ?? "").trim() || "Özel kaynak",
    unit: String(resource.unit ?? "").trim(),
    category: resource.category,
    amount: toSafeAmount(resource.quantity)
  }));
  const rows = [...fixedRows, ...customRows];
  const allAllocated = rows.every(row => row.amount === 0);

  return (
    <>
      {allAllocated && (
        <section className="panel allocation-success-card">
          Mevcut kaynakların tamamı ihtiyaç bölgelerine dağıtıldı.
        </section>
      )}
      <section className="panel table-panel">
        <h2>Dağıtılmayan</h2>
        <div className="table-scroll allocation-table-scroll">
          <table className="allocation-table">
            <thead>
              <tr>
                <th>Kaynak</th>
                <th>Dağıtılamayan miktar</th>
                <th>Durum</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => {
                const hasRemaining = row.amount > 0;
                return (
                  <tr key={row.id}>
                    <td>
                      <strong>{row.label}</strong>
                      {row.category && <small>{categoryLabel(row.category)}</small>}
                    </td>
                    <td>{formatQuantity(row.amount, row.unit)}</td>
                    <td>
                      <span className={`badge ${hasRemaining ? "badge-allocation-remaining" : "badge-allocation-complete"}`}>
                        {hasRemaining ? "Dağıtım dışında kaldı" : "Tamamı dağıtıldı"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

function parseNonNegativeInteger(value: string): number {
  const parsed = Number.parseInt(value || "0", 10);
  return Number.isFinite(parsed) ? Math.max(0, parsed) : 0;
}

function parseCustomResources(rows: CustomResourceRow[]): CustomResourceParseResult {
  if (rows.length > maxCustomResources) {
    return { ok: false, message: "En fazla 20 özel kaynak ekleyebilirsiniz." };
  }
  if (rows.some(row => !row.isAdded && hasCustomResourceInput(row))) {
    return { ok: false, message: confirmUnaddedResourcesMessage };
  }
  const resources = rows.filter(row => row.isAdded).map(row => {
    const quantity = Number(row.quantity);
    return {
      name: row.name.trim(),
      quantity,
      unit: row.unit.trim(),
      category: row.category
    };
  });
  const invalid = resources.find(resource => !resource.name || !resource.unit || !Number.isInteger(resource.quantity) || resource.quantity <= 0);
  if (invalid) {
    return { ok: false, message: "Özel kaynaklarda ad ve birim zorunludur; miktar sıfırdan büyük tam sayı olmalıdır." };
  }
  return { ok: true, resources };
}

function validateCustomResourceRow(row: CustomResourceRow): CustomResourceErrors {
  const errors: CustomResourceErrors = {};
  if (!row.name.trim()) errors.name = "Kaynak adı zorunludur.";
  if (!Number.isInteger(Number(row.quantity)) || Number(row.quantity) <= 0) errors.quantity = "Miktar sıfırdan büyük olmalıdır.";
  if (!row.unit.trim()) errors.unit = "Birim zorunludur.";
  return errors;
}

function hasCustomResourceInput(row: CustomResourceRow): boolean {
  return Boolean(row.name.trim() || row.quantity.trim() || row.unit.trim());
}

function isCustomResourceErrorField(field: PropertyKey): field is CustomResourceErrorField {
  return field === "name" || field === "quantity" || field === "unit";
}

function toSafeAmount(value: number | undefined): number {
  const amount = Number(value ?? 0);
  return Number.isFinite(amount) ? Math.max(0, Math.trunc(amount)) : 0;
}

function formatQuantity(amount: number, unit: string | undefined): string {
  const trimmedUnit = String(unit ?? "").trim();
  const formattedAmount = amount.toLocaleString("tr-TR");
  return trimmedUnit ? `${formattedAmount} ${trimmedUnit}` : formattedAmount;
}

function categoryLabel(category: string): string {
  return customResourceCategories.includes(category as CustomResourceCategory)
    ? categoryLabels[category as CustomResourceCategory]
    : categoryLabels.general;
}
