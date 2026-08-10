import { useEffect, useRef, useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { allocateResources } from "../api";
import type { AllocationResources, AllocationUnallocated } from "../types";

type ResourceKey = keyof AllocationResources;

type InventoryResource = {
  id: string;
  name: string;
  quantity: number;
  unit: string;
  systemKey?: ResourceKey;
};

type AddResourceForm = {
  name: string;
  quantity: string;
  unit: string;
};

type ResourceFormErrors = Partial<Record<"name" | "quantity" | "unit" | "form", string>>;

type InventoryEditDraftResource = {
  id: string;
  name: string;
  quantity: string;
  unit: string;
  systemKey?: ResourceKey;
};

interface ResourceDefinition {
  key: ResourceKey;
  name: string;
  unit: string;
  defaultQuantity: number;
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

type InventoryStorageLoad = {
  inventory: InventoryResource[];
  message: string | null;
};

type StoredInventoryParseResult = {
  inventory: InventoryResource[];
  warning: string | null;
};

type StoredResourceParseResult = {
  resources: InventoryResource[];
  warning: string | null;
};

type TextValidationResult = { ok: true; value: string } | { ok: false; message: string };
type QuantityValidationResult = { ok: true; value: number } | { ok: false; message: string };
type ResourceValidationResult =
  | { ok: true; name: string; quantity: number; unit: string }
  | { ok: false; errors: ResourceFormErrors };
type InventoryUpdateResult = { ok: true; inventory: InventoryResource[] } | { ok: false; message: string };
type EditDraftValidationResult = { ok: true; inventory: InventoryResource[] } | { ok: false; message: string };

const inventoryStorageKey = "disaster-platform-resource-inventory-v2";
const legacyInventoryStorageKeys = ["disaster-platform-resource-inventory-v1"] as const;
const inventoryStorageVersion = 2;
const legacyInventoryStorageVersion = 1;
const resourceNameMaxLength = 60;
const resourceUnitMaxLength = 30;
const resourceNameSuggestionsId = "resource-name-suggestions";
const resourceUnitSuggestionsId = "resource-unit-suggestions";
const defaultInventory: Readonly<AllocationResources> = { waterLiters: 500, tents: 100, medicalStaff: 20, blankets: 50 };
const resourceDefinitionByKey: Record<ResourceKey, ResourceDefinition> = {
  waterLiters: { key: "waterLiters", name: "Su", unit: "litre", defaultQuantity: defaultInventory.waterLiters },
  tents: { key: "tents", name: "Çadır", unit: "adet", defaultQuantity: defaultInventory.tents },
  medicalStaff: { key: "medicalStaff", name: "Sağlık personeli", unit: "kişi", defaultQuantity: defaultInventory.medicalStaff },
  blankets: { key: "blankets", name: "Battaniye", unit: "adet", defaultQuantity: defaultInventory.blankets }
};
const resourceDefinitions = Object.values(resourceDefinitionByKey);
const resourceNameSuggestions = resourceDefinitions.map(resource => resource.name);
const resourceUnitSuggestions = Array.from(new Set([...resourceDefinitions.map(resource => resource.unit), "litre", "adet", "kişi", "araç", "kutu", "paket"]));

export function AllocationPage() {
  const [initialInventoryLoad] = useState(loadInventoryFromStorage);
  const [inventory, setInventory] = useState<InventoryResource[]>(initialInventoryLoad.inventory);
  const [inventoryMessage, setInventoryMessage] = useState<string | null>(initialInventoryLoad.message);
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [addForm, setAddForm] = useState<AddResourceForm>(createEmptyAddForm);
  const [addFormErrors, setAddFormErrors] = useState<ResourceFormErrors>({});
  const [addSucceeded, setAddSucceeded] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editDraft, setEditDraft] = useState<InventoryEditDraftResource[]>([]);
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
  const activeInventoryRows = inventory.map(resource => ({ ...resource, quantity: toSafeAmount(resource.quantity) }));
  const customResourceCount = inventory.filter(resource => !resource.systemKey).length;
  const hasCustomResources = customResourceCount > 0;
  const canSaveEditDraft = editDraft.every(isEditDraftResourceFieldValid);

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

  function showAddSuccessMessage() {
    setAddSucceeded(true);
    clearAddStatusTimeout();
    addStatusTimeoutRef.current = window.setTimeout(() => {
      setAddSucceeded(false);
      addStatusTimeoutRef.current = null;
    }, 1600);
  }

  function openAddResourceForm() {
    clearAddSuccess();
    setAddForm(createEmptyAddForm());
    setAddFormErrors({});
    setIsAddOpen(true);
  }

  function cancelAddResource() {
    setIsAddOpen(false);
    setAddForm(createEmptyAddForm());
    setAddFormErrors({});
    clearAddSuccess();
  }

  function updateAddFormField(field: keyof AddResourceForm, value: string) {
    clearAddSuccess();
    setAddFormErrors(current => ({ ...current, [field]: undefined, form: undefined }));
    setAddForm(current => ({ ...current, [field]: value }));
  }

  function commitInventory(nextInventory: InventoryResource[]): boolean {
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
    const validation = validateAddResourceForm(addForm);
    if (!validation.ok) {
      setAddFormErrors(validation.errors);
      return;
    }

    const updateResult = addResourceToInventory(inventory, {
      name: validation.name,
      quantity: validation.quantity,
      unit: validation.unit
    });
    if (!updateResult.ok) {
      setAddFormErrors({ form: updateResult.message });
      return;
    }
    if (!commitInventory(updateResult.inventory)) return;

    setAddForm(createEmptyAddForm());
    setAddFormErrors({});
    setIsAddOpen(false);
    showAddSuccessMessage();
  }

  function openEditInventory() {
    setEditDraft(inventory.map(resource => ({
      id: resource.id,
      name: resource.name,
      quantity: String(toSafeAmount(resource.quantity)),
      unit: resource.unit,
      systemKey: resource.systemKey
    })));
    setEditError(null);
    setIsEditOpen(true);
  }

  function cancelEditInventory() {
    setIsEditOpen(false);
    setEditDraft([]);
    setEditError(null);
  }

  function updateEditDraftField(id: string, field: "name" | "quantity" | "unit", value: string) {
    setEditError(null);
    setEditDraft(current => current.map(resource => (
      resource.id === id ? { ...resource, [field]: value } : resource
    )));
  }

  function deleteDraftResource(id: string) {
    const resource = editDraft.find(item => item.id === id);
    if (!resource) return;
    const confirmed = window.confirm(`${resource.name} kaynağını envanterden kaldırmak istediğinize emin misiniz?`);
    if (!confirmed) return;
    setEditError(null);
    setEditDraft(current => current.filter(item => item.id !== id));
  }

  function saveEditInventory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validation = validateEditDraft(editDraft);
    if (!validation.ok) {
      setEditError(validation.message);
      return;
    }
    if (!commitInventory(validation.inventory)) return;
    setIsEditOpen(false);
    setEditDraft([]);
    setEditError(null);
  }

  function submitAllocation() {
    setAddFormErrors({});
    mutation.mutate({ resources: toAllocationResources(inventory) });
  }

  return (
    <main className="page">
      <Link to="/admin">← Dashboard</Link>
      <header className="hero compact"><h1>Kaynak dağıtım copilot’u</h1><p>Miktarları algoritma hesaplar; AI yalnızca sonucu açıklar.</p></header>

      <section className="panel allocation-control-panel">
        <div className="inventory-heading">
          <h2>Mevcut kaynaklar</h2>
          <div className="inventory-actions">
            <button className="button secondary" type="button" onClick={openEditInventory}>
              Kaynakları düzenle
            </button>
            {!isAddOpen && (
              <button className="button" type="button" onClick={openAddResourceForm}>
                Kaynak ekle
              </button>
            )}
          </div>
        </div>

        {inventoryMessage && <p className="error-box" role="alert">{inventoryMessage}</p>}
        {addSucceeded && <p className="success-message" role="status">Kaynak eklendi ✓</p>}

        {activeInventoryRows.length > 0 ? (
          <div className="current-resource-grid" aria-label="Mevcut kaynaklar">
            {activeInventoryRows.map(resource => (
              <article className="current-resource-card" key={resource.id}>
                <span>{resource.name}</span>
                <strong>{formatQuantity(resource.quantity, resource.unit)}</strong>
              </article>
            ))}
          </div>
        ) : (
          <p className="empty-state">Henüz kullanılabilir kaynak bulunmuyor.</p>
        )}

        <ResourceDatalists />

        {isAddOpen && (
          <form className="resource-add-section" onSubmit={submitAddResource} noValidate>
            <div className="resource-add-form">
              <label>
                <span className="field-label">Kaynak adı <span className="required-marker" aria-hidden="true">*</span></span>
                <input
                  autoFocus
                  list={resourceNameSuggestionsId}
                  maxLength={resourceNameMaxLength}
                  required
                  type="text"
                  value={addForm.name}
                  onChange={event => updateAddFormField("name", event.target.value)}
                  aria-invalid={Boolean(addFormErrors.name)}
                />
                {addFormErrors.name && <span className="field-error">{addFormErrors.name}</span>}
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
                  onChange={event => updateAddFormField("quantity", event.target.value)}
                  aria-invalid={Boolean(addFormErrors.quantity)}
                />
                {addFormErrors.quantity && <span className="field-error">{addFormErrors.quantity}</span>}
              </label>

              <label>
                <span className="field-label">Birim <span className="required-marker" aria-hidden="true">*</span></span>
                <input
                  list={resourceUnitSuggestionsId}
                  maxLength={resourceUnitMaxLength}
                  placeholder="litre, adet, kişi..."
                  required
                  type="text"
                  value={addForm.unit}
                  onChange={event => updateAddFormField("unit", event.target.value)}
                  aria-invalid={Boolean(addFormErrors.unit)}
                />
                {addFormErrors.unit && <span className="field-error">{addFormErrors.unit}</span>}
              </label>
            </div>

            <p className="field-helper">* Zorunlu alan</p>
            {addFormErrors.form && <p className="error-box" role="alert">{addFormErrors.form}</p>}

            <div className="resource-add-actions">
              <button className="button secondary" type="button" onClick={cancelAddResource}>İptal</button>
              <button className="button" type="submit">Ekle</button>
            </div>
          </form>
        )}

        <div className="allocation-actions">
          <button className="button" type="button" disabled={mutation.isPending} onClick={submitAllocation}>
            {mutation.isPending ? "Hesaplanıyor…" : "Dağıtımı hesapla"}
          </button>
        </div>
        {hasCustomResources && (
          <p className="allocation-note">
            Özel kaynaklar envanterde saklanır. Mevcut dağıtım hesabı standart kaynakları kullanır.
          </p>
        )}
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
              <div className="modal-title">
                <h2 id="resource-edit-title">Kaynakları düzenle</h2>
                <p className="field-helper">* Zorunlu alan</p>
              </div>
              <button className="link-button" type="button" onClick={cancelEditInventory}>Kapat</button>
            </div>

            {editDraft.length > 0 ? (
              <div className="edit-resource-list">
                {editDraft.map(resource => {
                  const quantityError = getZeroOrPositiveQuantityError(resource.quantity);
                  if (resource.systemKey) {
                    return (
                      <div className="edit-resource-row" key={resource.id}>
                        <div className="edit-resource-meta">
                          <strong>{resource.name}</strong>
                          <span>{resource.unit}</span>
                          <span>Standart kaynak</span>
                        </div>
                        <label>
                          <span className="field-label">Miktar <span className="required-marker" aria-hidden="true">*</span></span>
                          <input
                            aria-invalid={Boolean(quantityError)}
                            inputMode="numeric"
                            min={0}
                            pattern="[0-9]+"
                            required
                            step={1}
                            type="number"
                            value={resource.quantity}
                            onChange={event => updateEditDraftField(resource.id, "quantity", event.target.value)}
                          />
                          {quantityError && <span className="field-error">{quantityError}</span>}
                        </label>
                        <button className="button danger edit-resource-delete" type="button" onClick={() => deleteDraftResource(resource.id)}>Sil</button>
                      </div>
                    );
                  }

                  const nameError = getResourceNameError(resource.name);
                  const unitError = getResourceUnitError(resource.unit);
                  return (
                    <div className="edit-resource-row custom" key={resource.id}>
                      <label>
                        <span className="field-label">Kaynak adı <span className="required-marker" aria-hidden="true">*</span></span>
                        <input
                          aria-invalid={Boolean(nameError)}
                          list={resourceNameSuggestionsId}
                          maxLength={resourceNameMaxLength}
                          required
                          type="text"
                          value={resource.name}
                          onChange={event => updateEditDraftField(resource.id, "name", event.target.value)}
                        />
                        {nameError && <span className="field-error">{nameError}</span>}
                      </label>
                      <label>
                        <span className="field-label">Miktar <span className="required-marker" aria-hidden="true">*</span></span>
                        <input
                          aria-invalid={Boolean(quantityError)}
                          inputMode="numeric"
                          min={0}
                          pattern="[0-9]+"
                          required
                          step={1}
                          type="number"
                          value={resource.quantity}
                          onChange={event => updateEditDraftField(resource.id, "quantity", event.target.value)}
                        />
                        {quantityError && <span className="field-error">{quantityError}</span>}
                      </label>
                      <label>
                        <span className="field-label">Birim <span className="required-marker" aria-hidden="true">*</span></span>
                        <input
                          aria-invalid={Boolean(unitError)}
                          list={resourceUnitSuggestionsId}
                          maxLength={resourceUnitMaxLength}
                          required
                          type="text"
                          value={resource.unit}
                          onChange={event => updateEditDraftField(resource.id, "unit", event.target.value)}
                        />
                        {unitError && <span className="field-error">{unitError}</span>}
                      </label>
                      <button className="button danger edit-resource-delete" type="button" onClick={() => deleteDraftResource(resource.id)}>Sil</button>
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

function ResourceDatalists() {
  return (
    <>
      <datalist id={resourceNameSuggestionsId}>
        {resourceNameSuggestions.map(name => <option key={name} value={name} />)}
      </datalist>
      <datalist id={resourceUnitSuggestionsId}>
        {resourceUnitSuggestions.map(unit => <option key={unit} value={unit} />)}
      </datalist>
    </>
  );
}

function UnallocatedResourcesTable({ resources }: { resources?: AllocationUnallocated }) {
  const rows: UnallocatedRow[] = resourceDefinitions.map(resource => ({
    id: resource.key,
    label: resource.name,
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

function createEmptyAddForm(): AddResourceForm {
  return { name: "", quantity: "", unit: "" };
}

function loadInventoryFromStorage(): InventoryStorageLoad {
  if (typeof window === "undefined") return { inventory: createDefaultInventory(), message: null };
  try {
    const savedInventory = window.localStorage.getItem(inventoryStorageKey);
    if (savedInventory !== null) return parseInventoryStorageValue(savedInventory, false);

    for (const legacyKey of legacyInventoryStorageKeys) {
      const savedLegacyInventory = window.localStorage.getItem(legacyKey);
      if (savedLegacyInventory === null) continue;
      const parsedLegacy = parseInventoryStorageValue(savedLegacyInventory, true);
      if (parsedLegacy.message) return parsedLegacy;

      const migrationSave = saveInventoryToStorage(parsedLegacy.inventory);
      if (!migrationSave.ok) {
        return {
          inventory: parsedLegacy.inventory,
          message: "Kayıtlı kaynak envanteri yeni biçime taşındı ancak tarayıcıya kaydedilemedi. Değişiklik yapınca tekrar kaydedilecek."
        };
      }
      return parsedLegacy;
    }
    return { inventory: createDefaultInventory(), message: null };
  } catch {
    return {
      inventory: createDefaultInventory(),
      message: "Kayıtlı kaynak envanteri okunamadı. Varsayılan kaynaklar yüklendi."
    };
  }
}

function parseInventoryStorageValue(savedInventory: string, isLegacySource: boolean): InventoryStorageLoad {
  try {
    const parsedInventory = JSON.parse(savedInventory) as unknown;
    const inventory = parseStoredInventory(parsedInventory);
    if (!inventory) {
      return {
        inventory: createDefaultInventory(),
        message: isLegacySource
          ? "Kayıtlı eski kaynak envanteri geçersiz. Varsayılan kaynaklar yüklendi."
          : "Kayıtlı kaynak envanteri geçersiz. Varsayılan kaynaklar yüklendi."
      };
    }
    return { inventory: inventory.inventory, message: inventory.warning };
  } catch {
    return {
      inventory: createDefaultInventory(),
      message: "Kayıtlı kaynak envanteri okunamadı. Varsayılan kaynaklar yüklendi."
    };
  }
}

function saveInventoryToStorage(inventory: InventoryResource[]): { ok: true } | { ok: false; message: string } {
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

function parseStoredInventory(value: unknown): StoredInventoryParseResult | null {
  if (!isRecord(value)) return null;
  if (value.version === inventoryStorageVersion) {
    const parsedResources = parseStoredResourceArray(value.inventory);
    if (!parsedResources) return null;
    return { inventory: parsedResources.resources, warning: parsedResources.warning };
  }
  if (value.version === legacyInventoryStorageVersion && isRecord(value.inventory)) {
    const migratedInventory = migrateLegacyInventory(value.inventory);
    if (!migratedInventory) return null;
    return { inventory: migratedInventory, warning: null };
  }
  if (isRecord(value.inventory)) {
    const migratedInventory = migrateLegacyInventory(value.inventory);
    if (!migratedInventory) return null;
    return { inventory: migratedInventory, warning: null };
  }
  return null;
}

function parseStoredResourceArray(value: unknown): StoredResourceParseResult | null {
  if (!Array.isArray(value)) return null;

  let skippedInvalidRow = false;
  const resources: InventoryResource[] = [];
  const seenIds = new Set<string>();
  for (const item of value) {
    const resource = parseStoredResource(item);
    if (!resource) {
      skippedInvalidRow = true;
      continue;
    }
    const id = seenIds.has(resource.id) ? createResourceId(resource.name) : resource.id;
    seenIds.add(id);
    resources.push({ ...resource, id });
  }

  if (resources.length === 0 && value.length > 0) return null;

  const normalized = normalizeLoadedInventory(resources);
  const warning = skippedInvalidRow || normalized.skippedConflict
    ? "Kayıtlı kaynak envanterindeki bazı satırlar geçersiz olduğu için atlandı."
    : null;
  return { resources: normalized.inventory, warning };
}

function parseStoredResource(value: unknown): InventoryResource | null {
  if (!isRecord(value)) return null;
  const systemKey = typeof value.systemKey === "string" && isResourceKey(value.systemKey) ? value.systemKey : undefined;
  const quantity = value.quantity;
  if (!isStoredInventoryQuantity(quantity)) return null;

  if (systemKey) {
    return buildSystemResource(resourceDefinitionByKey[systemKey], quantity);
  }

  const name = readStoredText(value.name, resourceNameMaxLength);
  const unit = readStoredText(value.unit, resourceUnitMaxLength);
  if (!name || !unit) return null;
  const id = typeof value.id === "string" && value.id.trim() ? value.id.trim() : createResourceId(name);
  return { id, name, quantity, unit };
}

function normalizeLoadedInventory(resources: InventoryResource[]): { inventory: InventoryResource[]; skippedConflict: boolean } {
  const inventory: InventoryResource[] = [];
  let skippedConflict = false;

  for (const resource of resources) {
    const existingSystem = resource.systemKey ? inventory.find(item => item.systemKey === resource.systemKey) : undefined;
    if (existingSystem) {
      if (isSameResourceAndUnit(existingSystem, resource)) {
        existingSystem.quantity = toSafeAmount(existingSystem.quantity) + toSafeAmount(resource.quantity);
      } else {
        skippedConflict = true;
      }
      continue;
    }

    const sameName = inventory.find(item => normalizeForComparison(item.name) === normalizeForComparison(resource.name));
    if (sameName) {
      if (normalizeForComparison(sameName.unit) !== normalizeForComparison(resource.unit)) {
        skippedConflict = true;
        continue;
      }
      sameName.quantity = toSafeAmount(sameName.quantity) + toSafeAmount(resource.quantity);
      if (!sameName.systemKey && resource.systemKey) sameName.systemKey = resource.systemKey;
      continue;
    }

    inventory.push(resource);
  }

  return { inventory, skippedConflict };
}

function migrateLegacyInventory(value: Record<string, unknown>): InventoryResource[] | null {
  const inventory: InventoryResource[] = [];
  for (const resource of resourceDefinitions) {
    if (!hasOwn(value, resource.key)) continue;
    const quantity = value[resource.key];
    if (!isStoredInventoryQuantity(quantity)) return null;
    inventory.push(buildSystemResource(resource, quantity));
  }
  return inventory;
}

function createDefaultInventory(): InventoryResource[] {
  return resourceDefinitions.map(resource => buildSystemResource(resource, resource.defaultQuantity));
}

function buildSystemResource(resource: ResourceDefinition, quantity: number): InventoryResource {
  return {
    id: `system-${resource.key}`,
    name: resource.name,
    quantity: toSafeAmount(quantity),
    unit: resource.unit,
    systemKey: resource.key
  };
}

function addResourceToInventory(inventory: InventoryResource[], resource: { name: string; quantity: number; unit: string }): InventoryUpdateResult {
  const existingResource = inventory.find(item => normalizeForComparison(item.name) === normalizeForComparison(resource.name));
  if (existingResource) {
    if (normalizeForComparison(existingResource.unit) !== normalizeForComparison(resource.unit)) {
      return { ok: false, message: "Bu kaynak zaten farklı bir birimle kayıtlı." };
    }

    const systemMatch = findSystemResource(resource.name, resource.unit);
    return {
      ok: true,
      inventory: inventory.map(item => {
        if (item.id !== existingResource.id) return item;
        return {
          ...item,
          quantity: toSafeAmount(item.quantity) + resource.quantity,
          systemKey: item.systemKey ?? systemMatch?.key
        };
      })
    };
  }

  const systemMatch = findSystemResource(resource.name, resource.unit);
  const newResource = systemMatch
    ? buildSystemResource(systemMatch, resource.quantity)
    : { id: createResourceId(resource.name), name: resource.name, quantity: resource.quantity, unit: resource.unit };
  return { ok: true, inventory: [...inventory, newResource] };
}

function findSystemResource(name: string, unit: string): ResourceDefinition | undefined {
  const normalizedName = normalizeForComparison(name);
  const normalizedUnit = normalizeForComparison(unit);
  return resourceDefinitions.find(resource => (
    normalizeForComparison(resource.name) === normalizedName
    && normalizeForComparison(resource.unit) === normalizedUnit
  ));
}

function validateAddResourceForm(form: AddResourceForm): ResourceValidationResult {
  const errors: ResourceFormErrors = {};
  const name = validateResourceName(form.name);
  if (!name.ok) errors.name = name.message;
  const quantity = parsePositiveIntegerQuantityInput(form.quantity);
  if (!quantity.ok) errors.quantity = quantity.message;
  const unit = validateResourceUnit(form.unit);
  if (!unit.ok) errors.unit = unit.message;

  if (!name.ok || !quantity.ok || !unit.ok) return { ok: false, errors };
  return { ok: true, name: name.value, quantity: quantity.value, unit: unit.value };
}

function validateEditDraft(draft: InventoryEditDraftResource[]): EditDraftValidationResult {
  const inventory: InventoryResource[] = [];

  for (const resource of draft) {
    const quantity = parseZeroOrPositiveIntegerQuantityInput(resource.quantity);
    if (!quantity.ok) return { ok: false, message: quantity.message };

    if (resource.systemKey) {
      const definition = resourceDefinitionByKey[resource.systemKey];
      inventory.push(buildSystemResource(definition, quantity.value));
      continue;
    }

    const name = validateResourceName(resource.name);
    if (!name.ok) return { ok: false, message: name.message };
    const unit = validateResourceUnit(resource.unit);
    if (!unit.ok) return { ok: false, message: unit.message };
    const systemMatch = findSystemResource(name.value, unit.value);
    const existingSystemMatch = systemMatch
      ? draft.some(item => item.id !== resource.id && item.systemKey === systemMatch.key)
      : false;
    inventory.push(systemMatch && !existingSystemMatch
      ? buildSystemResource(systemMatch, quantity.value)
      : {
          id: resource.id,
          name: name.value,
          quantity: quantity.value,
          unit: unit.value
        });
  }

  const duplicateMessage = getDuplicateInventoryMessage(inventory);
  if (duplicateMessage) return { ok: false, message: duplicateMessage };
  return { ok: true, inventory };
}

function getDuplicateInventoryMessage(inventory: InventoryResource[]): string | null {
  const byName = new Map<string, string>();
  const byNameAndUnit = new Set<string>();
  const systemKeys = new Set<ResourceKey>();

  for (const resource of inventory) {
    if (resource.systemKey) {
      if (systemKeys.has(resource.systemKey)) return "Standart kaynak eşlemesi birden fazla satırda olamaz.";
      systemKeys.add(resource.systemKey);
    }

    const nameKey = normalizeForComparison(resource.name);
    const unitKey = normalizeForComparison(resource.unit);
    const existingUnit = byName.get(nameKey);
    if (existingUnit && existingUnit !== unitKey) return "Bu kaynak zaten farklı bir birimle kayıtlı.";

    const rowKey = `${nameKey}\u0000${unitKey}`;
    if (byNameAndUnit.has(rowKey)) return "Aynı kaynak adı ve birim birden fazla satırda olamaz.";
    byNameAndUnit.add(rowKey);
    byName.set(nameKey, unitKey);
  }

  return null;
}

function validateResourceName(value: string): TextValidationResult {
  const normalized = normalizeDisplayText(value);
  if (!normalized) return { ok: false, message: "Kaynak adı zorunludur." };
  if (normalized.length > resourceNameMaxLength) return { ok: false, message: `Kaynak adı en fazla ${resourceNameMaxLength} karakter olabilir.` };
  return { ok: true, value: normalized };
}

function validateResourceUnit(value: string): TextValidationResult {
  const normalized = normalizeDisplayText(value);
  if (!normalized) return { ok: false, message: "Birim zorunludur." };
  if (normalized.length > resourceUnitMaxLength) return { ok: false, message: `Birim en fazla ${resourceUnitMaxLength} karakter olabilir.` };
  return { ok: true, value: normalized };
}

function getResourceNameError(value: string): string | null {
  const validation = validateResourceName(value);
  return validation.ok ? null : validation.message;
}

function getResourceUnitError(value: string): string | null {
  const validation = validateResourceUnit(value);
  return validation.ok ? null : validation.message;
}

function parsePositiveIntegerQuantityInput(value: string): QuantityValidationResult {
  const trimmed = value.trim();
  if (!trimmed) return { ok: false, message: "Miktar zorunludur." };
  const numeric = Number(trimmed);
  if (!Number.isFinite(numeric)) return { ok: false, message: "Miktar geçerli bir sayı olmalıdır." };
  if (numeric <= 0) return { ok: false, message: "Miktar 0'dan büyük olmalıdır." };
  if (!/^\d+$/.test(trimmed)) return { ok: false, message: "Miktar tam sayı olmalıdır." };
  if (!Number.isSafeInteger(numeric)) return { ok: false, message: "Miktar güvenli tam sayı aralığında olmalıdır." };
  return { ok: true, value: numeric };
}

function parseZeroOrPositiveIntegerQuantityInput(value: string): QuantityValidationResult {
  const trimmed = value.trim();
  if (!trimmed) return { ok: false, message: "Miktar zorunludur." };
  const numeric = Number(trimmed);
  if (!Number.isFinite(numeric)) return { ok: false, message: "Miktar geçerli bir sayı olmalıdır." };
  if (numeric < 0) return { ok: false, message: "Miktar negatif olamaz." };
  if (!/^\d+$/.test(trimmed)) return { ok: false, message: "Miktar sıfır veya daha büyük tam sayı olmalıdır." };
  if (!Number.isSafeInteger(numeric)) return { ok: false, message: "Miktar güvenli tam sayı aralığında olmalıdır." };
  return { ok: true, value: numeric };
}

function getZeroOrPositiveQuantityError(value: string): string | null {
  const validation = parseZeroOrPositiveIntegerQuantityInput(value);
  return validation.ok ? null : validation.message;
}

function isEditDraftResourceFieldValid(resource: InventoryEditDraftResource): boolean {
  if (!parseZeroOrPositiveIntegerQuantityInput(resource.quantity).ok) return false;
  if (resource.systemKey) return true;
  return validateResourceName(resource.name).ok && validateResourceUnit(resource.unit).ok;
}

function toAllocationResources(inventory: InventoryResource[]): AllocationResources {
  return {
    waterLiters: systemResourceAmount(inventory, "waterLiters"),
    tents: systemResourceAmount(inventory, "tents"),
    medicalStaff: systemResourceAmount(inventory, "medicalStaff"),
    blankets: systemResourceAmount(inventory, "blankets")
  };
}

function systemResourceAmount(inventory: InventoryResource[], systemKey: ResourceKey): number {
  return toSafeAmount(inventory.find(resource => resource.systemKey === systemKey)?.quantity);
}

function isStoredInventoryQuantity(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function isResourceKey(value: string): value is ResourceKey {
  return Object.prototype.hasOwnProperty.call(resourceDefinitionByKey, value);
}

function hasOwn(value: Record<string, unknown>, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(value, key);
}

function readStoredText(value: unknown, maxLength: number): string | null {
  if (typeof value !== "string") return null;
  const normalized = normalizeDisplayText(value);
  if (!normalized || normalized.length > maxLength) return null;
  return normalized;
}

function isSameResourceAndUnit(left: InventoryResource, right: InventoryResource): boolean {
  return normalizeForComparison(left.name) === normalizeForComparison(right.name)
    && normalizeForComparison(left.unit) === normalizeForComparison(right.unit);
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

function normalizeDisplayText(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}

function normalizeForComparison(value: string): string {
  return normalizeDisplayText(value).toLocaleLowerCase("tr-TR");
}

function createResourceId(name: string): string {
  if (typeof globalThis.crypto?.randomUUID === "function") return `resource-${globalThis.crypto.randomUUID()}`;
  const normalizedName = normalizeForComparison(name).replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "");
  return `resource-${normalizedName || "custom"}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object";
}
