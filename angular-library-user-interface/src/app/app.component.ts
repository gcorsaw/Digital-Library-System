import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet } from '@angular/router';
import { ApiserviceService } from './service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css'
})
export class AppComponent implements OnInit {
  title = 'Library User Interface';
  books: Array<Record<string, unknown>> = [];
  loading = true;
  error = '';

  constructor(private apiService: ApiserviceService) {}

  ngOnInit(): void {
    this.apiService.getBooks().subscribe({
      next: (response) => {
        this.books = Array.isArray(response.books) ? response.books : [];
        this.loading = false;
      },
      error: () => {
        this.error = 'Failed to load books from the API.';
        this.loading = false;
      }
    });
  }
}
