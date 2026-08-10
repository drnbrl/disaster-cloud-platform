import type {
  AllocationItem,
  AllocationRequestPayload,
  AllocationResourceResult,
  AllocationResources,
  AllocationUnallocated,
  CustomResourceInput
} from "./types";

export type ResourceKey = keyof AllocationResources;

export type InventoryAllocationResource = {
  id: string;
  name: string;
  quantity: number;
  unit: string;
  systemKey?: ResourceKey;
};

type StandardResourceDefinition = {
  key: ResourceKey;
  id: string;
  name: string;
  unit: string;
};

export const standardResourceDefinitions: readonly StandardResourceDefinition[] = [
  { key: "waterLiters", id: "water", name: "Su", unit: "litre" },
  { key: "tents", id: "tents", name: "Çadır", unit: "adet" },
  { key: "medicalStaff", id: "medical-staff", name: "Sağlık personeli", unit: "kişi" },
  { key: "blankets", id: "blankets", name: "Battaniye", unit: "adet" }
] as const;

export const standardResourceDefinitionByKey: Record<ResourceKey, StandardResourceDefinition> = {
  waterLiters: { key: "waterLiters", id: "water", name: "Su", unit: "litre" },
  tents: { key: "tents", id: "tents", name: "Çadır", unit: "adet" },
  medicalStaff: { key: "medicalStaff", id: "medical-staff", name: "Sağlık personeli", unit: "kişi" },
  blankets: { key: "blankets", id: "blankets", name: "Battaniye", unit: "adet" }
};

export function buildAllocationRequestFromInventory(inventory: readonly InventoryAllocationResource[]): AllocationRequestPayload {
  const resources: AllocationResources = {
    waterLiters: systemResourceAmount(inventory, "waterLiters"),
    tents: systemResourceAmount(inventory, "tents"),
    medicalStaff: systemResourceAmount(inventory, "medicalStaff"),
    blankets: systemResourceAmount(inventory, "blankets")
  };
  const customResources = inventory
    .filter(resource => !resource.systemKey)
    .map(resource => ({
      id: resource.id.trim(),
      name: normalizeDisplayText(resource.name),
      quantity: toSafeAmount(resource.quantity),
      unit: normalizeDisplayText(resource.unit)
    }));

  return customResources.length > 0 ? { resources, customResources } : { resources };
}

export function allocationRequestPayload(input: AllocationResources | AllocationRequestPayload): AllocationRequestPayload {
  const sourceResources = isAllocationRequestPayload(input) ? input.resources : input;
  const resources: AllocationResources = {
    waterLiters: toSafeAmount(sourceResources.waterLiters),
    tents: toSafeAmount(sourceResources.tents),
    medicalStaff: toSafeAmount(sourceResources.medicalStaff),
    blankets: toSafeAmount(sourceResources.blankets)
  };
  const customResources = isAllocationRequestPayload(input)
    ? sanitizeCustomResourceInputs(input.customResources)
    : [];
  return customResources.length > 0 ? { resources, customResources } : { resources };
}

export function allocationDisplayResources(item: AllocationItem): AllocationResourceResult[] {
  const canonicalResources = readResourceArray(item.resources, true);
  if (canonicalResources) return canonicalResources;
  return [
    ...standardResourceDefinitions
      .map(resource => ({
        id: resource.id,
        name: resource.name,
        quantity: toSafeAmount(item[resource.key]),
        unit: resource.unit,
        systemKey: resource.key
      }))
      .filter(resource => resource.quantity > 0),
    ...(readResourceArray(item.customResources, true) ?? [])
  ];
}

export function unallocatedDisplayResources(resources?: AllocationUnallocated): AllocationResourceResult[] {
  if (!resources) return [];
  const canonicalResources = readResourceArray(resources.resources, false);
  if (canonicalResources) return canonicalResources;
  return [
    ...standardResourceDefinitions.map(resource => ({
      id: resource.id,
      name: resource.name,
      quantity: toSafeAmount(resources[resource.key]),
      unit: resource.unit,
      systemKey: resource.key
    })),
    ...(readResourceArray(resources.customResources, false) ?? [])
  ];
}

export function resetAllocationResultAfterInventoryChange(resetAllocationResult: () => void): void {
  resetAllocationResult();
}

export function formatQuantity(amount: number, unit: string | undefined): string {
  const trimmedUnit = String(unit ?? "").trim();
  const formattedAmount = amount.toLocaleString("tr-TR");
  return trimmedUnit ? `${formattedAmount} ${trimmedUnit}` : formattedAmount;
}

export function toSafeAmount(value: unknown): number {
  const amount = Number(value ?? 0);
  return Number.isFinite(amount) ? Math.max(0, Math.trunc(amount)) : 0;
}

function systemResourceAmount(inventory: readonly InventoryAllocationResource[], systemKey: ResourceKey): number {
  return toSafeAmount(inventory.find(resource => resource.systemKey === systemKey)?.quantity);
}

function sanitizeCustomResourceInputs(resources: readonly CustomResourceInput[] | undefined): CustomResourceInput[] {
  if (!Array.isArray(resources)) return [];
  return resources.map(resource => ({
    id: resource.id.trim(),
    name: normalizeDisplayText(resource.name),
    quantity: toSafeAmount(resource.quantity),
    unit: normalizeDisplayText(resource.unit)
  }));
}

function readResourceArray(value: unknown, positiveOnly: boolean): AllocationResourceResult[] | null {
  if (!Array.isArray(value)) return null;
  return value.reduce<AllocationResourceResult[]>((rows, item) => {
    const row = readResource(item);
    if (!row || (positiveOnly && row.quantity <= 0)) return rows;
    rows.push(row);
    return rows;
  }, []);
}

function readResource(value: unknown): AllocationResourceResult | null {
  if (!isRecord(value)) return null;
  const name = typeof value.name === "string" ? normalizeDisplayText(value.name) : "";
  const unit = typeof value.unit === "string" ? normalizeDisplayText(value.unit) : "";
  if (!name || !unit) return null;
  const id = typeof value.id === "string" && value.id.trim()
    ? value.id.trim()
    : `resource-${normalizeForFallbackId(name)}-${normalizeForFallbackId(unit)}`;
  const systemKey = typeof value.systemKey === "string" && isResourceKey(value.systemKey) ? value.systemKey : undefined;
  return { id, name, quantity: toSafeAmount(value.quantity), unit, systemKey };
}

function isAllocationRequestPayload(value: AllocationResources | AllocationRequestPayload): value is AllocationRequestPayload {
  return isRecord(value) && isRecord(value.resources);
}

function isResourceKey(value: string): value is ResourceKey {
  return Object.prototype.hasOwnProperty.call(standardResourceDefinitionByKey, value);
}

function normalizeDisplayText(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}

function normalizeForFallbackId(value: string): string {
  return normalizeDisplayText(value).replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "").toLocaleLowerCase("tr-TR") || "custom";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object";
}
