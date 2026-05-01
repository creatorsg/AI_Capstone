export interface User {
  id: number;
  email: string;
  nickname: string;
}

export interface Child {
  id: number;
  name: string;
  birth_date: string;
  gender: '남' | '여' | null;
  allergies: string[];
  conditions: string[];
  notes: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  is_emergency?: boolean;
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
  phone?: string;
  distance?: number | string;
  lat?: number;
  lon?: number;
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
}

export type RootStackParamList = {
  Auth: undefined;
  Main: undefined;
  ChildManagement: undefined;
  AddChild: { childId?: number };
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
