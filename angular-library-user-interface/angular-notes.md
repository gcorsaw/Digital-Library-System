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
* The reason why we would have 2 separate images (such as nginx as runner and node as the builder) would be for smaller image sizes, caching efficiency, cleaner maintenance, and better security. The smaller image size and the better security is going to allow for a smaller attack surface, which is going to beneficial since there is no 'direct' path to the other image. The attacker would have to know how to get to the other image in order to attack both images. The cleaner maintence is going to be usefule because there is going to be less code to use for either image and there's going to be more cache space as the layers are going to be reused. The caching efficiency can also be tied into this as well because there can be more.
* In the Dockerfile.dev file, the `FROM node:${NODE_VERSION} AS dev` command, it's going to set the base image for development with the node as the image name and the image is going to have the version of 24.12.0 Alpine Angular. The NODE_VERSION is a 'variable' that is going to define the version that we're going to use. In this case the `ARG NODE_VERSION=24.12.0-alpine` is going to define the Node.js version to use and it's going to use Alpine for a small footprint.

* __Minification for Angular__ [Minification](https://www.c-sharpcorner.com/article/minification-and-tree-shaking-in-angular)
    * In Angular, minification is the process of removing unnecessary characters from your code, such as whitespace, and commnents, and renaming variables to shorter names. This reduces the size of your code files, leading to faster download times. Angular applications are typically written in TypeScript, which is then transpiled to JavaScript. The minification process is applied to the resulting JavaScript code.
        * __Transpiling (source-to-source compiling)__ is the process of converting source code written in one high-level programming language into another high-level language or a different version of the same language, maintaining a similar level of abstraction.
        * Enabling Minification in Angular:
            1. Production build
                * Angular CLI provides a build command that you can use to build your production application. When you build for production, the Angular CLI automatically applies minification.
                    * Command: `ng build --prod`
                * This command generates a production-ready bundle with minified and optimized code.
            1. Terser Plugin
                * The Terser plugin, used for minification in Angular, comes with various configuration options. You can customize the minification process by providing options in your angular.json file.
                    * Example:
                        "architect": {
                            "build": {
                                "options": {
                                "optimization": true,
                                "outputPath": "dist/my-app",
                                "terserOptions": {
                                    "compress": {
                                    "pure_funcs": ["console.log"],
                                    "drop_console": true
                                    },
                                    "mangle": true
                                }
                                }
                            }
                        }
                    * In the example above, the pure_funcs option is used to specify functions that are pure and safely removed. The drop_console option removes all console statements, and mangle is set to true to obfuscate variable names. 
            1. Angular AOT (Ahead-Of-Time) Compilation
                * Angular applications can be compiled in either JIT (Just-In-Time) or AOT (Ahead-Of-Time) mode. AOT compilation is preferred for production builds as it allows for better tree shaking and optimization. It compiles Angular templates and components during the build process, resulting in smaller bundle sizes.
                * We can neable AOT compilation by default in your tsconfig.json file
                    * Command/Example:
                    "angularCompilerOptions": {
                        "fullTemplateTypeCheck": true,
                        "strictInjectionParameters": true
                    }

* __Tree Shaking for Angular__ [Tree Shaking](https://angular.love/angular-tree-shaking-2)
    * Tree shaking - What is it?
        * Tree shaking, also called dead code elimination, is a processs during which unused code is removed from our build. This technique allos us to reduce the final size of our application.
    * Tree shaking in Angular Ivy 
        * What is Angular Ivy [Angular Ivy](https://v12.angular.io/guide/ivy)
            * Ivy is the code name for Angular's next-generation compilation and rendering pipeline. With the version 9 release of Angular, the new compiler and reuntime instructions are used by default instead of the older compiler and runtime, known as View Engine.
        * AOT and Ivy
            * AOT compilation with Ivy is faster and should be used by default. In the `angular.json` workspace configuration file, set the default build options for your project to always use AOT compilation. When using application internationalization (i18n) with Ivy, translation merging also requires the use of AOT compilation.
                * Merge Translation into the application:
                    * To merge the completed translations into your project, complete the following actions
                        1. Use the Angular CLI to build a copy of the distributable files of your project
                        1. Use the `localize` option to replace all of the i18n messages with the valid translations and build a localized variant application. A variant application is a complete a copy of the distributable files of your application translated for a single locale.
            * After you merge the translations, serve each distributable copy of the application using server-side language detection or different subdirectories.
    * The insertion of tree shaking to the new Ivy rendering engine was a big step towards application optimization. Now let's explain how Angular recognizes code fragments which it doesn't need. First, we need to understand what is the incremental DOM, on which the Ivy rendering engine is based.
    * Team Google decided to introduce Incremental DOM to achieve two goals:
        * Smaller bundle size
        * Reduce the RAM requirements of the rendering engine.
    * Incremental DOM involves recompiling each componenet into a set of instructions. The instructions allow us to create a DOM tree and then update the parts with muted data. This approach allows us to get rid of the Angular interpreter from the final bundle. Additionally, the way the instructions are used to update the DOM requires less memory compared to the Virtual DOM used among others, by React, which generates full new versions of DOM trees.
    * What makes Incremental DOM allow the use of Tree Shaking?
        * By introducing instructions, during compilation, we can track if there is a reference from our component to a particular instruction. If there is not reference, we are able to perform Tree Shaking. In comparison, Virtual DOM relies on the interpreter, which is not able to check whether a given piece of code will be used in the application or not. 
        * In Angular, the **DOM (Document Object Model)** is the browser-based tree structure of HTML elements, and Angular's core philosophy is to let the framework manage it automatically through **data binding** rather than directly manipulating it.