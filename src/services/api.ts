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

export const hospitalsAPI = {
  nearbyStatic: (lat: number, lon: number, radius = 5000, category?: string) =>
    api.get('/hospitals/static/nearby', { params: { lat, lon, radius, category } }),
  search: (query: string) =>
    api.get('/hospitals/static/search', { params: { query } }),
};

export const welfareAPI = {
  list: (offset = 0, limit = 20) =>
    api.get('/welfare/', { params: { offset, limit } }),
  search: (query: string) =>
    api.get('/welfare/search', { params: { query } }),
  byAge: (months: number) =>
    api.get(`/welfare/age/${months}`),
};

export default api;
