// Digital-Library-System-main/angular-library-user-interface/src/app/service.ts
import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { fetchAuthSession } from 'aws-amplify/auth';
import { from, Observable } from 'rxjs';
import { switchMap } from 'rxjs/operators';

@Injectable({
  providedIn: 'root'
})
export class LibraryService {
  // Targets your library_fastapi_backend mapped to port 8001 inside docker-compose
  private apiBaseUrl = 'http://localhost:8001'; 

  constructor(private http: HttpClient) {}

  /**
   * Fetches books by manually resolving the local Cognito token and assigning headers
   */
  getBooks(): Observable<any> {
    // 1. Convert Amplify's Promise-based session fetch into an RxJS Observable stream
    return from(fetchAuthSession()).pipe(
      switchMap(session => {
        // 2. Extract the active JWT token string
        const jwtToken = session.tokens?.idToken?.toString();
        
        // 3. Put your second TypeScript code block right here to craft the header metadata
        const headers = new HttpHeaders({
          'Authorization': `Bearer ${jwtToken}`
        });

        // 4. Pass the custom headers block directly inside your backend HTTP transaction
        return this.http.get(`${this.apiBaseUrl}/books`, { headers });
      })
    );
  }
}
