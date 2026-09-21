* Angular is a platform and framework for building single-page client applications using HTML and TypeScript. Angular is written in TypeScript. It implements core and optional functionality as a set of TypeScript libraries that you import into your applications.
    * The single page application (SPA) is a web app that loads content dynamically without refreshing the whole page. It uses JavaScript to update only the required parts of the screeen based on user actions. This will then create a smooth, fast, and app-like user experience.
        1. Eliminates full page reloads for better performance
        1. Sends and updates only the necessary data from the server
        1. Provides a more responsive and seamless interface
    * The architecutre of an Angular application relies on certain fundamental concepts. The basic building blocks of the Angular framework are Angular components.
        * Components define **views**, whcih are sets of screen elements that Angular can choose among and modify according to your program logic and data.
        * Components use **services**, which provide background functionality not directly related to views such as fetching data. Such services can be **injected** into components as **dependencies**, making your code modular, reusable, and efficient.
    * From what I understand about Angular currently, Angular is going to be used to create an application that utilizes HTML and Typescipt for applications. 
* Nginx won't have node, vite, or vitest, but it does have Nginx. The nginx.conf is the configuration file. 
* npm run build is going to store the information into the dist directory.
* In the Docker multistage
    * 1st image --> build
        * has build tools
        * creates compiled code
    * 2nd image --> run
        * bare infrastructure, no build tools
* Vite outputs javascript and html 
* Comparisions
    * node --> python
    * vite --> runs like uv
    * vitest --> pytest
        * javascript and html are the pyc
* daemon off; --> turns on interactive mode and turns off daemon on.
* daemon on; --> turns of interactive mode and turns on the daemon.