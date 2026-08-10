import { formatQuantity } from "../allocationUtils";
import type { AllocationResourceResult } from "../types";

export function AllocationResourceList({ resources }: { resources: readonly AllocationResourceResult[] }) {
  if (resources.length === 0) {
    return <p className="muted">Dağıtılan kaynak yok.</p>;
  }

  return (
    <dl className="allocation-resource-list">
      {resources.map(resource => (
        <div className="allocation-resource-row" key={resource.id}>
          <dt>{resource.name}</dt>
          <dd>{formatQuantity(resource.quantity, resource.unit)}</dd>
        </div>
      ))}
    </dl>
  );
}
