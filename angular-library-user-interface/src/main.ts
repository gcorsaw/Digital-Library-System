import { bootstrapApplication } from '@angular/platform-browser';
import { Amplify } from 'aws-amplify';
import { appConfig } from './app/app.config';
import { AppComponent } from './app/app.component';

Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: 'local_XXXXXXXX',         // Replace with your generated ID
      userPoolClientId: 'local_mockclientid123', // Replace with your generated Client ID
      userPoolEndpoint: 'http://localhost:9229'
    }
  }
});

bootstrapApplication(AppComponent, appConfig)
  .catch((err) => console.error(err));
