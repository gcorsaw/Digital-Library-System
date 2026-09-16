import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface BookResponse {
  message?: string;
  books?: Array<Record<string, unknown>>;
}

@Injectable({
  providedIn: 'root'
})
export class ApiserviceService {
  private readonly apiUrl = 'http://localhost:8000';
// Replace whatever address is currently there with your actual host mapping:
  constructor(private http: HttpClient) {}

  getBooks(): Observable<BookResponse> {
    return this.http.get<BookResponse>(`${this.apiUrl}/books`);
  }
}