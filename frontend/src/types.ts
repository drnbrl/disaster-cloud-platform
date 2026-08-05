export type PriorityLevel = "low" | "medium" | "high" | "critical";
export type RequestStatus = "RECEIVED" | "REVIEWED" | "ASSIGNED" | "IN_PROGRESS" | "RESOLVED" | "REJECTED";

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
export type CustomResourceCategory = "water" | "food" | "shelter" | "medical" | "electricity" | "general";
export interface CustomResourceInput { name: string; quantity: number; unit: string; category: CustomResourceCategory; }
export interface AllocationInventory extends AllocationResources { customResources?: CustomResourceInput[]; }
export interface AllocationItem extends AllocationResources { city: string; customResources?: CustomResourceInput[]; needScores: Record<keyof AllocationResources, number>; }
export interface AllocationUnallocated extends Partial<AllocationResources> { customResources?: CustomResourceInput[]; }
export interface AllocationResponse {
  allocations: AllocationItem[];
  unallocated: AllocationUnallocated;
  inputResources: AllocationInventory;
  explanation: string;
  rulesVersion: string;
}
