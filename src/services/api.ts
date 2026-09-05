/**
 * API Service Layer
 * =================
 * Centralised FastAPI backend client.
 *
 * Authentication
 * --------------
 * Every protected request includes the Supabase access token as a
 * Bearer token in the `Authorization` header.  The token is read from
 * the session managed by `supabase.ts`.
 *
 * Usage
 * -----
 *   import { apiClient } from './api';
 *   // After login, store the session:
 *   import { setSupabaseSession } from './supabase';
 *   setSupabaseSession(loginResponse.session);
 *   // Then call any method — the token is attached automatically:
 *   const results = await apiClient.searchFlights(params);
 */

import { getAccessToken, supabase } from './supabase';

const FASTAPI_BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? '';

// ── Type definitions ──────────────────────────────────────────────────────────

export interface FlightSearchParams {
  origin: string;
  destination: string;
  departure_date: string;
  return_date?: string;
  passenger_count: number;
  travel_class: 'economy' | 'premium_economy' | 'business' | 'first';
}

export interface Flight {
  flight_id: string;
  airline: string;
  flight_number?: string;
  departure_time: string;
  arrival_time: string;
  duration: string;
  price?: number;
  price_currency: string;
  stops: number | string;
  raw_text?: string;
}

export interface FlightSearchResponse {
  success: boolean;
  provider: string;
  origin: string;
  destination: string;
  departure_date: string;
  return_date?: string;
  flights: Flight[];
  total_results: number;
  cached: boolean;
  timestamp: string;
  requested_by?: string;
  error?: string;
  error_type?: string;
}

export interface ConnectionTestResponse {
  connected: boolean;
  endpoint?: string;
  test_page_title?: string;
  customer_id?: string;
  zone?: string;
  error?: string;
}

export interface HotelDataRecord {
  hotel_name: string;
  hotel_location: string;
  hotel_city: string;
  hotel_country: string;
  hotel_rating?: number;
  hotel_category?: string;
  room_type: string;
  board_basis?: string;
  price_per_night: number;
  price_currency: string;
  special_offer_price?: number;
  available_from: string;
  available_to: string;
  booking_deadline?: string;
  max_occupancy?: number;
  available_rooms?: number;
  description?: string;
  terms_conditions?: string;
  cancellation_policy?: string;
}

export interface VisaApplicationCreate {
  client_name: string;
  passport_number: string;
  destination_country: string;
  email?: string;
  phone?: string;
  visa_type?: string;
  application_notes?: string;
  status?: number;
  appointment_date?: string;
  appointment_notes?: string;
}

export interface VisaApplication {
  id: string;
  client_name: string;
  passport_number: string;
  destination_country: string;
  status: number;
  status_name?: string;
  email?: string;
  phone?: string;
  visa_type?: string;
  application_notes?: string;
  appointment_date?: string;
  appointment_notes?: string;
  organization_id?: string;
  created_by?: string;
  created_at?: string;
  updated_at?: string;
}

export interface VisaSearchResponse {
  results: VisaApplication[];
  count: number;
  filters_applied: Record<string, any>;
}

// ── Payment types ─────────────────────────────────────────────────────────────

export type PaymentStatus = 'pending' | 'partial' | 'full' | 'refunded' | 'cancelled';
export type PaymentMethod = 'cash' | 'bank' | 'pos' | 'cheque';

export interface PaymentCreate {
  client_name: string;
  booking_reference?: string;
  amount: number;
  payment_method: PaymentMethod;
  status?: PaymentStatus;
  payment_date?: string;
  notes?: string;
}

export interface PaymentRecord {
  id: string;
  client_name: string;
  booking_reference?: string;
  amount: number;
  payment_method: PaymentMethod;
  status: PaymentStatus;
  payment_date?: string;
  notes?: string;
  organization_id?: string;
  created_by?: string;
  created_at?: string;
  updated_at?: string;
}

export interface PaymentSearchResponse {
  results: PaymentRecord[];
  count: number;
  filters_applied: Record<string, any>;
}

export interface DocumentParseResponse {
  success: boolean;
  file_name: string;
  file_type: string;
  records_count: number;
  records: HotelDataRecord[];
  errors: string[];
  /** user_id of the authenticated user who uploaded the file */
  parsed_by: string;
}

// ── Client class ──────────────────────────────────────────────────────────────

class FastAPIClient {
  private baseUrl: string;

  constructor(baseUrl: string = FASTAPI_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  // ── Auth header ─────────────────────────────────────────────────────────────

  /**
   * Build auth headers using the live Supabase session.
   * Uses the SDK's getSession() so the token is always fresh (auto-refreshed).
   *
   * @param required - Set to false for public endpoints that don't need auth.
   */
  private async authHeaders(required = true): Promise<Record<string, string>> {
    // Prefer the SDK's session (always up-to-date after auto-refresh)
    const { data } = await supabase.auth.getSession()
    const token = data.session?.access_token ?? getAccessToken()

    if (!token) {
      if (required) {
        throw new Error(
          'Authentication required: No active session found. ' +
          'Please log in before making this request.',
        );
      }
      return {};
    }

    return { Authorization: `Bearer ${token}` };
  }

  // ── Generic fetch wrapper ───────────────────────────────────────────────────

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    requiresAuth = true,
  ): Promise<T> {
    if (!this.baseUrl) {
      throw new Error(
        'No backend URL configured. Set VITE_API_URL in your environment variables.',
      );
    }

    const url = `${this.baseUrl}${endpoint}`;

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(await this.authHeaders(requiresAuth)),
      ...(options.headers as Record<string, string> | undefined),
    };

    try {
      console.log(`[API] ${options.method ?? 'GET'} ${url}`);

      const response = await fetch(url, { ...options, headers });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));

        if (response.status === 401) {
          throw new Error('Session expired or invalid. Please log in again.');
        }

        // detail may be a string OR a nested object (e.g. from 503 flight errors)
        const detail = (errorData as any).detail;
        const message =
          typeof detail === 'string'
            ? detail
            : typeof detail?.error === 'string'
              ? detail.error
              : detail
                ? JSON.stringify(detail)
                : `API request failed: ${response.status} ${response.statusText}`;

        throw new Error(message);
      }

      return (await response.json()) as T;
    } catch (error) {
      if (error instanceof TypeError && error.message.includes('fetch')) {
        console.error(`[API] Network Error — cannot reach backend at ${this.baseUrl}`);
        throw new Error(
          `Network Error: Cannot reach backend at ${this.baseUrl}. ` +
          'Is the FastAPI server running?',
        );
      }

      console.error(`[API] Request failed: ${url}`, error);
      throw error;
    }
  }

  // ── Flight endpoints ────────────────────────────────────────────────────────

  /** 🔒 Protected — requires authentication */
  async searchFlights(params: FlightSearchParams): Promise<FlightSearchResponse> {
    return this.request<FlightSearchResponse>('/flights/search', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  /** Public — monitoring / health checks */
  async testBrightDataConnection(): Promise<ConnectionTestResponse> {
    return this.request<ConnectionTestResponse>(
      '/flights/test-connection',
      { method: 'GET' },
      false, // public endpoint
    );
  }

  /** Public */
  async getFlightServiceHealth(): Promise<unknown> {
    return this.request('/flights/health', { method: 'GET' }, false);
  }

  /** 🔒 Protected */
  async clearFlightCache(): Promise<unknown> {
    return this.request('/flights/clear-cache', { method: 'POST' });
  }

  // ── Document endpoints ──────────────────────────────────────────────────────

  /** 🔒 Protected — requires authentication */
  async parseHotelDocument(file: File): Promise<DocumentParseResponse> {
    if (!this.baseUrl) {
      throw new Error('No backend URL configured. Set VITE_API_URL in your environment variables.');
    }

    const { data } = await supabase.auth.getSession()
    const token = data.session?.access_token ?? getAccessToken();

    if (!token) {
      throw new Error(
        'Authentication required: No active session found. Please log in.',
      );
    }

    const url = `${this.baseUrl}/documents/parse-hotel-data`;
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          // NOTE: Do NOT set Content-Type for multipart — the browser adds
          //       the boundary automatically when using FormData.
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Session expired or invalid. Please log in again.');
        }
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          (errorData as { detail?: string }).detail ??
          `Document parsing failed: ${response.status}`,
        );
      }

      return (await response.json()) as DocumentParseResponse;
    } catch (error) {
      console.error('[API] Document parsing failed:', error);
      throw error;
    }
  }

  // ── Hotel endpoints ─────────────────────────────────────────────────────────

  /** 🔒 Protected */
  async bulkInsertHotels(hotels: HotelDataRecord[]): Promise<unknown> {
    return this.request('/hotels/bulk-insert', {
      method: 'POST',
      body: JSON.stringify(hotels),
    });
  }

  /** 🔒 Protected */
  async searchHotels(filters: {
    city?: string;
    country?: string;
    min_price?: number;
    max_price?: number;
    available_from?: string;
    available_to?: string;
    limit?: number;
  }): Promise<unknown> {
    const queryParams = new URLSearchParams();

    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== null) {
        queryParams.append(key, String(value));
      }
    }

    return this.request(`/hotels/search?${queryParams.toString()}`, {
      method: 'GET',
    });
  }

  /** 🔒 Protected */
  async deleteHotel(hotelId: string): Promise<unknown> {
    return this.request(`/hotels/offers/${hotelId}`, {
      method: 'DELETE',
    });
  }

  // ── Visa Application endpoints ──────────────────────────────────────────────

  /** 🔒 Protected */
  async createVisaApplication(data: VisaApplicationCreate): Promise<VisaApplication> {
    return this.request<VisaApplication>('/visa/applications', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /** 🔒 Protected */
  async searchVisaApplications(filters: {
    client_name?: string;
    passport_number?: string;
    destination_country?: string;
    status?: number;
    limit?: number;
    offset?: number;
  }): Promise<VisaSearchResponse> {
    const queryParams = new URLSearchParams();

    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== null) {
        queryParams.append(key, String(value));
      }
    }

    return this.request<VisaSearchResponse>(
      `/visa/applications?${queryParams.toString()}`,
      { method: 'GET' }
    );
  }

  /** 🔒 Protected */
  async getVisaApplication(applicationId: string): Promise<VisaApplication> {
    return this.request<VisaApplication>(`/visa/applications/${applicationId}`, {
      method: 'GET',
    });
  }

  /** 🔒 Protected */
  async updateVisaApplication(
    applicationId: string,
    updates: Partial<VisaApplicationCreate>
  ): Promise<VisaApplication> {
    return this.request<VisaApplication>(`/visa/applications/${applicationId}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  }

  /** 🔒 Protected */
  async updateVisaStatus(
    applicationId: string,
    newStatus: number
  ): Promise<{ success: boolean; new_status: number; status_name: string }> {
    return this.request(`/visa/applications/${applicationId}/status?new_status=${newStatus}`, {
      method: 'PATCH',
    });
  }

  /** 🔒 Protected */
  async updateVisaAppointment(
    applicationId: string,
    appointmentDate: string,
    notes?: string
  ): Promise<{ success: boolean }> {
    const params = new URLSearchParams({ appointment_date: appointmentDate });
    if (notes) params.append('appointment_notes', notes);

    return this.request(`/visa/applications/${applicationId}/appointment?${params.toString()}`, {
      method: 'PATCH',
    });
  }

  /** 🔒 Protected */
  async deleteVisaApplication(applicationId: string): Promise<{ success: boolean }> {
    return this.request(`/visa/applications/${applicationId}`, {
      method: 'DELETE',
    });
  }

  /** 🔒 Protected */
  async getVisaStatusSummary(): Promise<{
    total: number;
    by_status: Record<string, number>;
    status_counts: Record<number, number>;
  }> {
    return this.request('/visa/status-summary', { method: 'GET' });
  }

  // ── Payment endpoints ───────────────────────────────────────────────────────

  /** 🔒 Protected */
  async createPayment(data: PaymentCreate): Promise<PaymentRecord> {
    return this.request<PaymentRecord>('/payments', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /** 🔒 Protected */
  async searchPayments(filters: {
    client_name?: string;
    booking_reference?: string;
    status?: string;
    payment_method?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<PaymentSearchResponse> {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(filters)) {
      if (v !== undefined && v !== null && v !== '') q.append(k, String(v));
    }
    return this.request<PaymentSearchResponse>(`/payments?${q.toString()}`, { method: 'GET' });
  }

  /** 🔒 Protected */
  async getPaymentsSummary(): Promise<{ total: number; by_status: Record<string, number> }> {
    return this.request('/payments/summary', { method: 'GET' });
  }

  /** 🔒 Protected */
  async updatePayment(id: string, updates: Partial<PaymentCreate>): Promise<PaymentRecord> {
    return this.request<PaymentRecord>(`/payments/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  }

  /** 🔒 Protected */
  async deletePayment(id: string): Promise<{ success: boolean }> {
    return this.request(`/payments/${id}`, { method: 'DELETE' });
  }

  // ── Health (public) ─────────────────────────────────────────────────────────

  async healthCheck(): Promise<{ status: string }> {
    return this.request('/health', { method: 'GET' }, false);
  }
}

// ── Singleton ─────────────────────────────────────────────────────────────────
export const apiClient = new FastAPIClient();

// Export class for testing / custom instances
export { FastAPIClient };
