import axios, { AxiosInstance, AxiosError } from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_BASE_URL } from '../constants/Config';

const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as any;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const refreshToken = await AsyncStorage.getItem('refresh_token');
        if (!refreshToken) throw new Error('No refresh token');
        const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });
        await AsyncStorage.setItem('access_token', data.access_token);
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
        return api(originalRequest);
      } catch {
        await AsyncStorage.removeItem('access_token');
        await AsyncStorage.removeItem('refresh_token');
      }
    }
    return Promise.reject(error);
  }
);

export const authAPI = {
  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),
  register: (email: string, password: string, nickname: string) =>
    api.post('/auth/register', { email, password, nickname }),
  me: () => api.get('/auth/me'),
  logout: () => api.post('/auth/logout'),
};

export const childrenAPI = {
  list: () => api.get('/children/'),
  create: (data: object) => api.post('/children/', data),
  update: (id: number, data: object) => api.patch(`/children/${id}`, data),
  delete: (id: number) => api.delete(`/children/${id}`),
};

export const chatAPI = {
  send: (childId: number, message: string, sessionId?: string | null) =>
    api.post('/chat/', { child_id: childId, message, session_id: sessionId }),
  history: (childId: number) => api.get(`/chat/history/${childId}`),
};

// 백엔드 파라미터: lat, lng (lon 아님), radius, category
export const hospitalsAPI = {
  nearbyStatic: (lat: number, lng: number, radius = 5000, category?: string) =>
    api.get('/hospitals/static/nearby', { params: { lat, lng, radius, category } }),
  search: (keyword: string, sido?: string, sggu?: string, category?: string) =>
    api.get('/hospitals/static/search', { params: { keyword, sido, sggu, category } }),
};

// 백엔드 파라미터: keyword (query 아님)
export const welfareAPI = {
  list: (offset = 0, limit = 20) =>
    api.get('/welfare/', { params: { offset, limit } }),
  search: (keyword: string) =>
    api.get('/welfare/search', { params: { keyword } }),
  byAge: (months: number) =>
    api.get(`/welfare/age/${months}`),
  categories: () => api.get('/welfare/categories'),
};

export const healthAPI = {
  getLogs: (childId: number) =>
    api.get(`/health/logs/${childId}`),
  getLogsByType: (childId: number, logType: string) =>
    api.get(`/health/logs/${childId}/type/${logType}`),
  addLog: (data: {
    child_id: number;
    log_type: string;
    value?: string;
    note?: string;
  }) => api.post('/health/logs/', data),
  getVaccinations: (childId: number) =>
    api.get(`/health/vaccinations/${childId}`),
  addVaccination: (data: {
    child_id: number;
    vaccine_name: string;
    vaccinated_at?: string;
    next_due?: string;
    note?: string;
  }) => api.post('/health/vaccinations/', data),
};

export default api;
