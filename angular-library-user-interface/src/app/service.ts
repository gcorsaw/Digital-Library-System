import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

declare global {
  interface Window {
    DIGITAL_LIBRARY_API_URL?: string;
  }
}

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
  books: Book[];
}

export interface Book {
  book_id: number;
  book_title: string;
  read_status: 'want' | 'reading' | 'finished';
  rating: number | null;
}

export interface BookProgressResponse {
  updated_record: Book;
}

@Injectable({ providedIn: 'root' })
export class ApiserviceService {
  private readonly apiBaseUrl =
    typeof window !== 'undefined' ? window.DIGITAL_LIBRARY_API_URL ?? '' : '';
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

  updateBookProgress(
    bookId: number,
    readStatus: Book['read_status'],
    rating: number | null
  ): Observable<BookProgressResponse> {
    const token = this.getAccessToken();
    const headers = token
      ? new HttpHeaders({ Authorization: `Bearer ${token}` })
      : new HttpHeaders();

    return this.http.put<BookProgressResponse>(
      `${this.apiBaseUrl}/books/${bookId}/progress`,
      { read_status: readStatus, rating },
      { headers }
    );
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
