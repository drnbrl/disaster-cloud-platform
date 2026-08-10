import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { build } from "esbuild";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

const frontendRoot = fileURLToPath(new URL("..", import.meta.url));

async function importSource(entry, external = []) {
  const tempDir = await mkdtemp(path.join(tmpdir(), "allocation-frontend-test-"));
  const outfile = path.join(tempDir, "module.mjs");
  await build({
    entryPoints: [path.join(frontendRoot, entry)],
    outfile,
    bundle: true,
    platform: "node",
    format: "esm",
    jsx: "automatic",
    external,
    logLevel: "silent"
  });
  try {
    return await import(pathToFileURL(outfile).href);
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
}

test("frontend allocation request includes customResources from inventory", async () => {
  const { buildAllocationRequestFromInventory, allocationRequestPayload } = await importSource("src/allocationUtils.ts");

  const request = buildAllocationRequestFromInventory([
    { id: "system-waterLiters", name: "Su", quantity: 700, unit: "litre", systemKey: "waterLiters" },
    { id: "system-tents", name: "Çadır", quantity: 20, unit: "adet", systemKey: "tents" },
    { id: "fuel-1", name: " Yakıt ", quantity: 250, unit: " litre " },
    { id: "generator-1", name: "Jeneratör", quantity: 5, unit: "adet" }
  ]);

  assert.deepEqual(allocationRequestPayload(request), {
    resources: { waterLiters: 700, tents: 20, medicalStaff: 0, blankets: 0 },
    customResources: [
      { id: "fuel-1", name: "Yakıt", quantity: 250, unit: "litre" },
      { id: "generator-1", name: "Jeneratör", quantity: 5, unit: "adet" }
    ]
  });
});

test("frontend resource renderer displays a returned custom resource", async () => {
  const { allocationDisplayResources } = await importSource("src/allocationUtils.ts");
  const { AllocationResourceList } = await importSource("src/components/AllocationResourceList.tsx");
  const item = {
    city: "Hatay",
    waterLiters: 400,
    tents: 12,
    medicalStaff: 0,
    blankets: 0,
    needScores: { waterLiters: 10, tents: 8, medicalStaff: 0, blankets: 7 },
    resources: [
      { id: "water", name: "Su", quantity: 400, unit: "litre", systemKey: "waterLiters" },
      { id: "fuel-1", name: "Yakıt", quantity: 150, unit: "litre" },
      { id: "generator-1", name: "Jeneratör", quantity: 3, unit: "adet" }
    ]
  };

  const html = renderToStaticMarkup(React.createElement(AllocationResourceList, { resources: allocationDisplayResources(item) }));

  assert.match(html, /Yakıt/);
  assert.match(html, /150 litre/);
  assert.match(html, /Jeneratör/);
  assert.match(html, /3 adet/);
});

test("inventory changes clear stale allocation results", async () => {
  const { resetAllocationResultAfterInventoryChange } = await importSource("src/allocationUtils.ts");
  const pageSource = await readFile(path.join(frontendRoot, "src/pages/AllocationPage.tsx"), "utf8");
  let resetCalled = false;

  resetAllocationResultAfterInventoryChange(() => {
    resetCalled = true;
  });

  assert.equal(resetCalled, true);
  assert.match(pageSource, /resetAllocationResultAfterInventoryChange\(\(\) => mutation\.reset\(\)\)/);
});
