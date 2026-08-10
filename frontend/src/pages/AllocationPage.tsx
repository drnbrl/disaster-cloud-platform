import { useEffect, useRef, useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { allocateResources } from "../api";
import type { AllocationResources, AllocationUnallocated } from "../types";

type ResourceKey = keyof AllocationResources;
type InventoryState = Partial<Record<ResourceKey, number>>;
type InventoryDraft = Partial<Record<ResourceKey, string>>;

interface ResourceDefinition {
  key: ResourceKey;
  label: string;
  unit: string;
}

type AllocationMutationPayload = {
  resources: AllocationResources;
};

type UnallocatedRow = {
  id: string;
  label: string;
  unit: string;
  amount: number;
};

const inventoryStorageKey = "disaster-platform-resource-inventory-v1";
const inventoryStorageVersion = 1;
const defaultInventory: Readonly<AllocationResources> = { waterLiters: 500, tents: 100, medicalStaff: 20, blankets: 50 };
const resourceDefinitionByKey: Record<ResourceKey, ResourceDefinition> = {
  waterLiters: { key: "waterLiters", label: "Su", unit: "litre" },
  tents: { key: "tents", label: "Çadır", unit: "adet" },
  medicalStaff: { key: "medicalStaff", label: "Sağlık personeli", unit: "kişi" },
  blankets: { key: "blankets", label: "Battaniye", unit: "adet" }
};
const resourceDefinitions = Object.values(resourceDefinitionByKey);

export function AllocationPage() {
  const [initialInventoryLoad] = useState(loadInventoryFromStorage);
  const [inventory, setInventory] = useState<InventoryState>(initialInventoryLoad.inventory);
  const [inventoryMessage, setInventoryMessage] = useState<string | null>(initialInventoryLoad.message);
  const [addForm, setAddForm] = useState<{ resourceKey: "" | ResourceKey; quantity: string }>({ resourceKey: "", quantity: "" });
  const [addFormError, setAddFormError] = useState<string | null>(null);
  const [addSucceeded, setAddSucceeded] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editDraft, setEditDraft] = useState<InventoryDraft>({});
  const [editError, setEditError] = useState<string | null>(null);
  const addStatusTimeoutRef = useRef<number | null>(null);
  const editModalRef = useRef<HTMLFormElement | null>(null);
  const mutation = useMutation({
    mutationFn: ({ resources }: AllocationMutationPayload) => allocateResources(resources)
  });

  useEffect(() => () => clearAddStatusTimeout(), []);

  useEffect(() => {
    if (isEditOpen) editModalRef.current?.focus();
  }, [isEditOpen]);

  const allocationResult = mutation.data;
  const allocationItems = allocationResult?.allocations ?? [];
  const allocationError = mutation.error ? `Kaynak dağıtımı hesaplanamadı: ${mutation.error.message}` : null;
  const selectedResource = addForm.resourceKey ? resourceDefinitionByKey[addForm.resourceKey] : null;
  const addQuantityError = addForm.quantity.trim() && !isPositiveIntegerInput(addForm.quantity)
    ? "Miktar 1 veya daha büyük tam sayı olmalıdır."
    : null;
  const addResourceTypeError = addForm.quantity.trim() && !selectedResource ? "Kaynak türü seçilmelidir." : null;
  const canAddResource = Boolean(selectedResource) && isPositiveIntegerInput(addForm.quantity);
  const activeInventoryRows = resourceDefinitions
    .filter(resource => hasOwnResource(inventory, resource.key))
    .map(resource => ({ ...resource, amount: toSafeAmount(inventory[resource.key]) }));
  const editRows = resourceDefinitions.filter(resource => hasOwnResource(editDraft, resource.key));
  const canSaveEditDraft = editRows.every(resource => isZeroOrPositiveIntegerInput(editDraft[resource.key] ?? ""));

  function clearAddStatusTimeout() {
    if (addStatusTimeoutRef.current !== null) {
      window.clearTimeout(addStatusTimeoutRef.current);
      addStatusTimeoutRef.current = null;
    }
  }

  function clearAddSuccess() {
    clearAddStatusTimeout();
    setAddSucceeded(false);
  }

  function updateAddResourceKey(value: string) {
    clearAddSuccess();
    setAddFormError(null);
    setAddForm(current => ({ ...current, resourceKey: isResourceKey(value) ? value : "" }));
  }

  function updateAddQuantity(value: string) {
    clearAddSuccess();
    setAddFormError(null);
    setAddForm(current => ({ ...current, quantity: value }));
  }

  function commitInventory(nextInventory: InventoryState): boolean {
    const persistResult = saveInventoryToStorage(nextInventory);
    if (!persistResult.ok) {
      setInventoryMessage(persistResult.message);
      return false;
    }
    setInventory(nextInventory);
    setInventoryMessage(null);
    mutation.reset();
    return true;
  }

  function submitAddResource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedResource) {
      setAddFormError("Kaynak türü seçilmelidir.");
      return;
    }
    const quantity = parsePositiveIntegerInput(addForm.quantity);
    if (quantity === null) {
      setAddFormError("Miktar 1 veya daha büyük tam sayı olmalıdır.");
      return;
    }

    const nextInventory: InventoryState = {
      ...inventory,
      [selectedResource.key]: toSafeAmount(inventory[selectedResource.key]) + quantity
    };
    if (!commitInventory(nextInventory)) return;

    setAddForm({ resourceKey: "", quantity: "" });
    setAddFormError(null);
    setAddSucceeded(true);
    clearAddStatusTimeout();
    addStatusTimeoutRef.current = window.setTimeout(() => {
      setAddSucceeded(false);
      addStatusTimeoutRef.current = null;
    }, 1400);
  }

  function openEditInventory() {
    const nextDraft: InventoryDraft = {};
    for (const resource of resourceDefinitions) {
      if (hasOwnResource(inventory, resource.key)) nextDraft[resource.key] = String(toSafeAmount(inventory[resource.key]));
    }
    setEditDraft(nextDraft);
    setEditError(null);
    setIsEditOpen(true);
  }

  function cancelEditInventory() {
    setIsEditOpen(false);
    setEditDraft({});
    setEditError(null);
  }

  function updateEditQuantity(key: ResourceKey, value: string) {
    setEditError(null);
    setEditDraft(current => ({ ...current, [key]: value }));
  }

  function deleteDraftResource(key: ResourceKey) {
    const resource = resourceDefinitionByKey[key];
    const confirmed = window.confirm(`${resource.label} kaynağını envanterden kaldırmak istediğinize emin misiniz?`);
    if (!confirmed) return;
    setEditError(null);
    setEditDraft(current => {
      const nextDraft = { ...current };
      delete nextDraft[key];
      return nextDraft;
    });
  }

  function saveEditInventory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextInventory: InventoryState = {};
    for (const resource of resourceDefinitions) {
      if (!hasOwnResource(editDraft, resource.key)) continue;
      const amount = parseZeroOrPositiveIntegerInput(editDraft[resource.key] ?? "");
      if (amount === null) {
        setEditError("Miktarlar sıfır veya daha büyük tam sayı olmalıdır.");
        return;
      }
      nextInventory[resource.key] = amount;
    }
    if (!commitInventory(nextInventory)) return;
    setIsEditOpen(false);
    setEditDraft({});
    setEditError(null);
  }

  function submitAllocation() {
    setAddFormError(null);
    mutation.mutate({ resources: toAllocationResources(inventory) });
  }

  return (
    <main className="page">
      <Link to="/admin">← Dashboard</Link>
      <header className="hero compact"><h1>Kaynak dağıtım copilot’u</h1><p>Miktarları algoritma hesaplar; AI yalnızca sonucu açıklar.</p></header>

      <section className="panel allocation-control-panel">
        <div className="inventory-heading">
          <h2>Mevcut kaynaklar</h2>
          <button className="button secondary" type="button" onClick={openEditInventory}>
            Kaynakları düzenle
          </button>
        </div>

        {inventoryMessage && <p className="error-box" role="alert">{inventoryMessage}</p>}

        {activeInventoryRows.length > 0 ? (
          <div className="current-resource-grid" aria-label="Mevcut kaynaklar">
            {activeInventoryRows.map(resource => (
              <article className="current-resource-card" key={resource.key}>
                <span>{resource.label}</span>
                <strong>{formatQuantity(resource.amount, resource.unit)}</strong>
              </article>
            ))}
          </div>
        ) : (
          <p className="empty-state">Henüz kullanılabilir kaynak bulunmuyor.</p>
        )}

        <form className="resource-add-section" onSubmit={submitAddResource} noValidate>
          <div className="resource-add-header">
            <h2>Kaynak ekle</h2>
            <p className="field-helper">* Zorunlu alan</p>
          </div>

          <div className="resource-add-form">
            <label>
              <span className="field-label">Kaynak türü <span className="required-marker" aria-hidden="true">*</span></span>
              <select required value={addForm.resourceKey} onChange={event => updateAddResourceKey(event.target.value)} aria-invalid={Boolean(addResourceTypeError)}>
                <option value="">Seçiniz</option>
                {resourceDefinitions.map(resource => (
                  <option key={resource.key} value={resource.key}>{resource.label}</option>
                ))}
              </select>
              {addResourceTypeError && <span className="field-error">{addResourceTypeError}</span>}
            </label>

            <label>
              <span className="field-label">Miktar <span className="required-marker" aria-hidden="true">*</span></span>
              <input
                inputMode="numeric"
                min={1}
                pattern="[1-9][0-9]*"
                required
                step={1}
                type="number"
                value={addForm.quantity}
                onChange={event => updateAddQuantity(event.target.value)}
                aria-invalid={Boolean(addQuantityError)}
              />
              {addQuantityError && <span className="field-error">{addQuantityError}</span>}
            </label>

            <div className="resource-unit-display" aria-live="polite">
              <span>Birim</span>
              <strong>{selectedResource?.unit ?? "-"}</strong>
            </div>

            <button className={`button resource-add-submit${addSucceeded ? " success" : ""}`} type="submit" disabled={!canAddResource || addSucceeded}>
              {addSucceeded ? "Eklendi ✓" : "Ekle"}
            </button>
          </div>

          {addFormError && <p className="error-box" role="alert">{addFormError}</p>}
        </form>

        <div className="allocation-actions">
          <button className="button" type="button" disabled={mutation.isPending} onClick={submitAllocation}>
            {mutation.isPending ? "Hesaplanıyor…" : "Dağıtımı hesapla"}
          </button>
        </div>
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
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <UnallocatedResourcesTable resources={allocationResult.unallocated} />
      </>}

      {isEditOpen && (
        <div className="modal-backdrop">
          <form
            className="modal-panel resource-edit-panel"
            ref={editModalRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="resource-edit-title"
            tabIndex={-1}
            onKeyDown={event => {
              if (event.key === "Escape") cancelEditInventory();
            }}
            onSubmit={saveEditInventory}
          >
            <div className="modal-header">
              <h2 id="resource-edit-title">Kaynakları düzenle</h2>
              <button className="link-button" type="button" onClick={cancelEditInventory}>Kapat</button>
            </div>

            {editRows.length > 0 ? (
              <div className="edit-resource-list">
                {editRows.map(resource => {
                  const value = editDraft[resource.key] ?? "";
                  const hasError = !isZeroOrPositiveIntegerInput(value);
                  return (
                    <div className="edit-resource-row" key={resource.key}>
                      <div className="edit-resource-meta">
                        <strong>{resource.label}</strong>
                        <span>{resource.unit}</span>
                      </div>
                      <label>
                        Miktar
                        <input
                          aria-invalid={hasError}
                          inputMode="numeric"
                          min={0}
                          pattern="[0-9]+"
                          required
                          step={1}
                          type="number"
                          value={value}
                          onChange={event => updateEditQuantity(resource.key, event.target.value)}
                        />
                        {hasError && <span className="field-error">Miktar sıfır veya daha büyük tam sayı olmalıdır.</span>}
                      </label>
                      <button className="button danger edit-resource-delete" type="button" onClick={() => deleteDraftResource(resource.key)}>Sil</button>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="empty-state">Henüz kullanılabilir kaynak bulunmuyor.</p>
            )}

            {editError && <p className="error-box" role="alert">{editError}</p>}

            <div className="modal-actions">
              <button className="button secondary" type="button" onClick={cancelEditInventory}>İptal</button>
              <button className="button" type="submit" disabled={!canSaveEditDraft}>Değişiklikleri kaydet</button>
            </div>
          </form>
        </div>
      )}
    </main>
  );
}

function UnallocatedResourcesTable({ resources }: { resources?: AllocationUnallocated }) {
  const rows: UnallocatedRow[] = resourceDefinitions.map(resource => ({
    id: resource.key,
    label: resource.label,
    unit: resource.unit,
    amount: toSafeAmount(resources?.[resource.key])
  }));
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
                    <td><strong>{row.label}</strong></td>
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

function loadInventoryFromStorage(): { inventory: InventoryState; message: string | null } {
  if (typeof window === "undefined") return { inventory: createDefaultInventory(), message: null };
  try {
    const savedInventory = window.localStorage.getItem(inventoryStorageKey);
    if (!savedInventory) return { inventory: createDefaultInventory(), message: null };
    const parsedInventory = JSON.parse(savedInventory) as unknown;
    const inventory = parseStoredInventory(parsedInventory);
    if (!inventory) {
      return {
        inventory: createDefaultInventory(),
        message: "Kayıtlı kaynak envanteri geçersiz. Varsayılan kaynaklar yüklendi."
      };
    }
    return { inventory, message: null };
  } catch {
    return {
      inventory: createDefaultInventory(),
      message: "Kayıtlı kaynak envanteri okunamadı. Varsayılan kaynaklar yüklendi."
    };
  }
}

function saveInventoryToStorage(inventory: InventoryState): { ok: true } | { ok: false; message: string } {
  if (typeof window === "undefined") return { ok: true };
  try {
    window.localStorage.setItem(inventoryStorageKey, JSON.stringify({ version: inventoryStorageVersion, inventory }));
    return { ok: true };
  } catch {
    return {
      ok: false,
      message: "Kaynak envanteri tarayıcıya kaydedilemedi. Değişiklikler uygulanmadı."
    };
  }
}

function parseStoredInventory(value: unknown): InventoryState | null {
  if (!isRecord(value) || value.version !== inventoryStorageVersion || !isRecord(value.inventory)) return null;
  const inventory: InventoryState = {};
  for (const [key, quantity] of Object.entries(value.inventory)) {
    if (!isResourceKey(key) || !isInventoryQuantity(quantity)) return null;
    inventory[key] = quantity;
  }
  return inventory;
}

function createDefaultInventory(): InventoryState {
  return { ...defaultInventory };
}

function toAllocationResources(inventory: InventoryState): AllocationResources {
  return {
    waterLiters: toSafeAmount(inventory.waterLiters),
    tents: toSafeAmount(inventory.tents),
    medicalStaff: toSafeAmount(inventory.medicalStaff),
    blankets: toSafeAmount(inventory.blankets)
  };
}

function parsePositiveIntegerInput(value: string): number | null {
  if (!isPositiveIntegerInput(value)) return null;
  const amount = Number(value);
  return Number.isSafeInteger(amount) ? amount : null;
}

function parseZeroOrPositiveIntegerInput(value: string): number | null {
  if (!isZeroOrPositiveIntegerInput(value)) return null;
  const amount = Number(value);
  return Number.isSafeInteger(amount) ? amount : null;
}

function isPositiveIntegerInput(value: string): boolean {
  return /^[1-9]\d*$/.test(value.trim());
}

function isZeroOrPositiveIntegerInput(value: string): boolean {
  return /^(0|[1-9]\d*)$/.test(value.trim());
}

function isInventoryQuantity(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function isResourceKey(value: string): value is ResourceKey {
  return Object.prototype.hasOwnProperty.call(resourceDefinitionByKey, value);
}

function hasOwnResource<T extends Partial<Record<ResourceKey, unknown>>>(inventory: T, key: ResourceKey): boolean {
  return Object.prototype.hasOwnProperty.call(inventory, key);
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object";
}
