import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';

declare global {
  interface Window {
    DIGITAL_LIBRARY_API_URL?: string;
  }
}

export interface BookResponse {
  message?: string;
  books?: Array<Record<string, unknown>>;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  expires_in?: number;
  refresh_token?: string;
  user?: Record<string, unknown>;
}

@Injectable({
  providedIn: 'root'
})
export class ApiserviceService {
  private readonly apiUrl =
    typeof window !== 'undefined' && window.DIGITAL_LIBRARY_API_URL
      ? window.DIGITAL_LIBRARY_API_URL
      : 'http://localhost:8000';
  constructor(private http: HttpClient) {}

  getBooks(): Observable<BookResponse> {
    return this.http.get<BookResponse>(`${this.apiUrl}/books`, {
      headers: this.authorizationHeaders()
    });
  }

  registerNative(username: string, email: string, password: string): Observable<AuthTokenResponse> {
    return this.http.post<AuthTokenResponse>(`${this.apiUrl}/auth/register`, {
      username,
      email,
      password
    });
  }

  loginNative(username: string, password: string): Observable<AuthTokenResponse> {
    return this.http.post<AuthTokenResponse>(`${this.apiUrl}/auth/login`, {
      username,
      password
    });
  }

  registerCognito(email: string, password: string): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(`${this.apiUrl}/auth/cognito/register`, {
      email,
      password
    });
  }

  confirmCognito(email: string, confirmation_code: string): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(`${this.apiUrl}/auth/cognito/confirm`, {
      email,
      confirmation_code
    });
  }

  loginCognito(email: string, password: string): Observable<AuthTokenResponse> {
    return this.http.post<AuthTokenResponse>(`${this.apiUrl}/auth/cognito/login`, {
      email,
      password
    });
  }

  saveAccessToken(token: string): void {
    if (typeof sessionStorage !== 'undefined') {
      sessionStorage.setItem('access_token', token);
    }
  }

  hasAccessToken(): boolean {
    return typeof sessionStorage !== 'undefined' && !!sessionStorage.getItem('access_token');
  }

  clearAccessToken(): void {
    if (typeof sessionStorage !== 'undefined') {
      sessionStorage.removeItem('access_token');
    }
  }

  private authorizationHeaders(): HttpHeaders {
    const token = typeof sessionStorage === 'undefined'
      ? null
      : sessionStorage.getItem('access_token');
    return token ? new HttpHeaders({ Authorization: `Bearer ${token}` }) : new HttpHeaders();
  }
}