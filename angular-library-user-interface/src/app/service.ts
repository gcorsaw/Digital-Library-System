import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  expires_in?: number;
  refresh_token?: string;
}

export interface AuthMessageResponse {
  message: string;
  delivery_medium?: string;
}

export interface BooksResponse {
  books: Array<Record<string, unknown>>;
}

@Injectable({ providedIn: 'root' })
export class ApiserviceService {
  private readonly apiBaseUrl = 'http://localhost:8001';
  private readonly accessTokenKey = 'library_access_token';

  constructor(private readonly http: HttpClient) {}

  registerNative(username: string, email: string, password: string): Observable<AuthTokenResponse> {
    return this.http.post<AuthTokenResponse>(`${this.apiBaseUrl}/auth/register`, {
      username,
      email,
      password
    });
  }

  loginNative(username: string, password: string): Observable<AuthTokenResponse> {
    return this.http.post<AuthTokenResponse>(`${this.apiBaseUrl}/auth/login`, {
      username,
      password
    });
  }

  registerCognito(email: string, password: string): Observable<AuthMessageResponse> {
    return this.http.post<AuthMessageResponse>(`${this.apiBaseUrl}/auth/cognito/register`, {
      email,
      password
    });
  }

  confirmCognito(email: string, confirmationCode: string): Observable<AuthMessageResponse> {
    return this.http.post<AuthMessageResponse>(`${this.apiBaseUrl}/auth/cognito/confirm`, {
      email,
      confirmation_code: confirmationCode
    });
  }

  loginCognito(email: string, password: string): Observable<AuthTokenResponse> {
    return this.http.post<AuthTokenResponse>(`${this.apiBaseUrl}/auth/cognito/login`, {
      email,
      password
    });
  }

  getBooks(): Observable<BooksResponse> {
    const token = this.getAccessToken();
    const headers = token
      ? new HttpHeaders({ Authorization: `Bearer ${token}` })
      : new HttpHeaders();

    return this.http.get<BooksResponse>(`${this.apiBaseUrl}/books`, { headers });
  }

  hasAccessToken(): boolean {
    return this.getAccessToken() !== null;
  }

  saveAccessToken(token: string): void {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(this.accessTokenKey, token);
    }
  }

  clearAccessToken(): void {
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem(this.accessTokenKey);
    }
  }

  private getAccessToken(): string | null {
    return typeof localStorage === 'undefined'
      ? null
      : localStorage.getItem(this.accessTokenKey);
  }
}
