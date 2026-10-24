import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ApiserviceService, AuthTokenResponse } from './service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterOutlet],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css'
})
export class AppComponent implements OnInit {
  title = 'Library User Interface';
  books: Array<Record<string, unknown>> = [];
  loading = false;
  error = '';
  message = '';
  authMode: 'native' | 'cognito' = 'native';
  registering = false;
  needsConfirmation = false;
  authenticated = false;
  busy = false;
  username = '';
  email = '';
  password = '';
  confirmationCode = '';

  constructor(private apiService: ApiserviceService) {}

  ngOnInit(): void {
    if (this.apiService.hasAccessToken()) {
      this.authenticated = true;
      this.loadBooks();
    }
  }

  submitAuthentication(): void {
    this.error = '';
    this.message = '';
    this.busy = true;

    const request: Observable<AuthTokenResponse | { message: string }> = this.authMode === 'cognito'
      ? (this.registering
        ? this.apiService.registerCognito(this.email, this.password)
        : this.apiService.loginCognito(this.email, this.password))
      : (this.registering
        ? this.apiService.registerNative(this.username, this.email, this.password)
        : this.apiService.loginNative(this.username || this.email, this.password));

    request.subscribe({
      next: (response) => {
        this.busy = false;
        if (this.registering && this.authMode === 'cognito' && 'message' in response) {
          this.needsConfirmation = true;
          this.message = response.message;
          return;
        }
        if ('access_token' in response) {
          this.apiService.saveAccessToken(response.access_token);
          this.authenticated = true;
          this.password = '';
          this.loadBooks();
        }
      },
      error: (error: HttpErrorResponse) => {
        this.busy = false;
        this.error = this.errorMessage(error);
      }
    });
  }

  confirmCognitoAccount(): void {
    this.error = '';
    this.message = '';
    this.busy = true;
    this.apiService.confirmCognito(this.email, this.confirmationCode).subscribe({
      next: (response) => {
        this.busy = false;
        this.needsConfirmation = false;
        this.registering = false;
        this.confirmationCode = '';
        this.message = response.message;
      },
      error: (error: HttpErrorResponse) => {
        this.busy = false;
        this.error = this.errorMessage(error);
      }
    });
  }

  signOut(): void {
    this.apiService.clearAccessToken();
    this.authenticated = false;
    this.books = [];
    this.error = '';
    this.message = '';
  }

  private loadBooks(): void {
    this.loading = true;
    this.apiService.getBooks().subscribe({
      next: (response) => {
        this.books = Array.isArray(response.books) ? response.books : [];
        this.loading = false;
        this.error = '';
      },
      error: (error: HttpErrorResponse) => {
        this.loading = false;
        if (error.status === 401) {
          this.signOut();
          this.error = 'Your session has expired. Please sign in again.';
          return;
        }
        this.error = this.errorMessage(error);
      }
    });
  }

  private errorMessage(error: HttpErrorResponse): string {
    return error.error?.detail ?? 'The request could not be completed.';
  }
}
