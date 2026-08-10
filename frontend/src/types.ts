export type PriorityLevel = "low" | "medium" | "high" | "critical";
export type RequestStatus = "RECEIVED" | "REVIEWED" | "ASSIGNED" | "IN_PROGRESS" | "RESOLVED" | "REJECTED";
export type LocationSource = "USER_COORDINATES" | "GEOCODED_ADDRESS" | "UNRESOLVED_ADDRESS";

export interface Needs {
  water: boolean;
  food: boolean;
  shelter: boolean;
  medical: boolean;
  electricity: boolean;
  baby_support: boolean;
}

export interface DisasterRequest {
  requestId: string;
  createdAt: string;
  updatedAt?: string;
  city: string;
  district?: string;
  address?: string;
  latitude?: number;
  longitude?: number;
  locationSource?: LocationSource;
  geocodeLabel?: string;
  message?: string;
  analysisStatus: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
  requestStatus: RequestStatus;
  peopleCount?: number;
  injuredCount?: number;
  needs?: Needs;
  summary?: string;
  priorityScore?: number;
  priorityLevel?: PriorityLevel;
  priorityReasons?: string[];
  aiConfidence?: number;
  requiresHumanReview?: boolean;
}

export interface GlobalStats {
  totalRequests: number;
  criticalRequests: number;
  highRequests: number;
  mediumRequests: number;
  lowRequests: number;
  waterRequests: number;
  foodRequests: number;
  shelterRequests: number;
  medicalRequests: number;
  electricityRequests: number;
  babySupportRequests: number;
  affectedPeople: number;
  injuredPeople: number;
}

export interface CityStats extends GlobalStats { scope: string; city: string; }
export interface DashboardResponse { global: GlobalStats; cities: CityStats[]; recentRequests: DisasterRequest[]; }
export interface AllocationResources { waterLiters: number; tents: number; medicalStaff: number; blankets: number; }
export interface CustomResourceInput { id: string; name: string; quantity: number; unit: string; }
export interface AllocationResourceResult extends CustomResourceInput { systemKey?: keyof AllocationResources; }
export interface AllocationRequestPayload { resources: AllocationResources; customResources?: CustomResourceInput[]; }
export interface AllocationInventory extends AllocationResources { customResources?: CustomResourceInput[]; }
export interface AllocationItem extends AllocationResources {
  city: string;
  resources?: AllocationResourceResult[];
  customResources?: AllocationResourceResult[];
  needScores: Record<keyof AllocationResources, number>;
}
export interface AllocationUnallocated extends Partial<AllocationResources> {
  resources?: AllocationResourceResult[];
  customResources?: AllocationResourceResult[];
}
export interface AllocationResponse {
  allocations: AllocationItem[];
  unallocated: AllocationUnallocated;
  inputResources: AllocationInventory;
  explanation: string;
  rulesVersion: string;
}
