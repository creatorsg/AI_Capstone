export interface User {
  id: number;
  email: string;
  nickname: string;
}

export interface Child {
  id: number;
  name: string;
  birth_date: string;
  gender: 'male' | 'female' | null;
  height_cm?: number | null;
  weight_kg?: number | null;
  allergies: string[];
  conditions: string[];
  notes: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  is_emergency?: boolean;
  needs_more_context?: boolean;
}

export interface ChatResponse {
  session_id: string;
  message: string;
  is_emergency: boolean;
  needs_more_context: boolean;
  is_final: boolean;
}

export interface Hospital {
  title?: string;
  place_name?: string;
  address?: string;
  road_address?: string;
  address_name?: string;
  phone?: string;
  distance?: number | string;
  lat?: number;
  lon?: number;
  x?: string;
  y?: string;
  category?: string;
  location?: {
    type: string;
    coordinates: [number, number];
  };
}

export interface WelfarePolicy {
  title: string;
  content: string;
  department?: string;
  url?: string;
  target_age_min_months?: number;
  target_age_max_months?: number;
  category?: string;
  contact?: string;
  benefit?: string;
  how_to_apply?: string;
  target?: string;
}

export interface HealthLog {
  id: number;
  child_id: number;
  log_type: 'fever' | 'meal' | 'sleep' | 'breastfeed' | 'formula';
  value?: string;
  note?: string;
  recorded_at: string;
}

export interface VaccinationRecord {
  id: number;
  child_id: number;
  vaccine_name: string;
  vaccinated_at?: string;
  next_due?: string;
  note?: string;
}

export type RootStackParamList = {
  Auth: undefined;
  Main: undefined;
  ChildManagement: undefined;
  AddChild: { childId?: number };
  HealthRecord: { childId: number };
};

export type AuthStackParamList = {
  Login: undefined;
  Signup: undefined;
};

export type MainTabParamList = {
  Chat: undefined;
  Hospitals: undefined;
  Welfare: undefined;
  MyPage: undefined;
};
