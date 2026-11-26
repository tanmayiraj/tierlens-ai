import axios, { AxiosError } from 'axios';
import { ApiErrorResponse } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000,
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorResponse>) => {
    // Standardized error normalization matching API_SPEC.md Section 1.3
    const apiError = error.response?.data?.error;
    const message = apiError?.message || error.message || 'An unexpected API error occurred';
    return Promise.reject(new Error(message));
  }
);

export default apiClient;
