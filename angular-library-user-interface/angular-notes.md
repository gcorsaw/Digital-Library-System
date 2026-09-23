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
    * Team Google decided to introduce Incremental DOM to acheive two goals:
        * Smaller bundle size
        * Reduce the RAM requirements of the rendering engine
    * Incremental DOM involves recompiling each component into a set of instructions. THe instructions allow us to create a DOM tree and then update the parts with muted data. This approach allows us to get rid of the Angular interpreter from the final bundle. Additionally, the way the instructions are used to upate the DOM requires less memory compared to the Virtual DOM used among others, by React, which generates full new versions of DOM trees.
* __What makes Incremental DOM allow the use of Tree Shaking?__ [DOM and Tree Shaking](https://angular.love/angular-tree-shaking-2)
    * By introducing instructions, during compilation, we can check if there is a reference from our component to a particular instruction. IF there is no reference, we are able to perform Tree Shaking. In comparison, Virtual DOM relies on the interpreter, which is not able to chekc whehter a given piece of code will be used in the application or not.
    * Example:
        * Angular application with a single component that uses interpolation and date pipe:
            import { Component } from '@angular/core';

            @Component({
            selector: 'app-root',
            template: `
                <h1>Title: {{ title }}</h1>
                <h2>{{ date | date }}</h2>
            `,
            })
            export class AppComponent {
            title = 'Tree shaking with Angular Ivy';
            date = new Date();
            }
        * The usage of Angular Compiler CLI to generate the Js files which will contain our component in the form of instructions. After executing the `ngc -p tsconfig.json` command, the component now looks like this:
            import { Component } from "@angular/core";
            import * as i0 from "@angular/core";
            import * as i1 from "@angular/common";
            export class AppComponent {
                constructor() {
                    this.title = "Tree shaking with Angular Ivy";
                    this.date = new Date();
                }
                }
            AppComponent.ɵfac = function AppComponent_Factory(t) {
                return new (t || AppComponent)();
            };
            AppComponent.ɵcmp = i0.ɵɵdefineComponent({
                type: AppComponent,
                selectors: [["app-root"]],
                decls: 5,
                vars: 4,
                template: function AppComponent_Template(rf, ctx) {
                    if (rf & 1) {
                    i0.ɵɵelementStart(0, "h1");
                    i0.ɵɵtext(1);
                    i0.ɵɵelementEnd();
                    i0.ɵɵelementStart(2, "h2");
                    i0.ɵɵtext(3);
                    i0.ɵɵpipe(4, "date");
                    i0.ɵɵelementEnd();
                    }
                    if (rf & 2) {
                    i0.ɵɵadvance(1);
                    i0.ɵɵtextInterpolate1("Title: ", ctx.title, "");
                    i0.ɵɵadvance(2);
                    i0.ɵɵtextInterpolate(i0.ɵɵpipeBind1(4, 2, ctx.date));
                    }
                },
                pipes: [i1.DatePipe],
                encapsulation: 2,
                });
                /*@__PURE__*/ (function () {
                i0.ɵsetClassMetadata(
                    AppComponent,
                    [
                    {
                        type: Component,
                        args: [
                        {
                            selector: "app-root",
                            template: `
                    <h1>Title: {{ title }}</h1>
                    <h2>{{ date | date }}</h2>
                `,
                        },
                        ],
                    },
                    ],
                    null,
                    null
                );
            })();
    * The first argument of the rf function stands for renderFlags, we can distinguish two modes 1 for RenderFlags.Create and 2 for RenderFlags.Update. When creating a component, we go from line 18 to line 24 (according to the article), adding our elements to an array called Logical View (LView), which holds the DOM elements, bound values, and directive instances.
        * This array is created per componenet and then used for Change Detection. When we enter the update mode, the advance instructions allow us to find the postion of the updated element in the LView array. The values are stored in the cache, and the change detection process compares the new value with the current value. [How Angular Works](https://www.youtube.com/watch?v=S0o-4yc2n-8)
* __Virtual Dom vs Incremental Dom in Angular__ [Virtual Dom vs Incremental Dom in Angular](https://www.angularminds.com/blog/virtual-dom-vs-incremental-dom-in-angular)
    * The primary aim of any Angular project is to have an application or software that fits modern web development scenarios. The Angular application is supposed to be futuristic, innovative, client-centric, user-friendly. Therefore, Google introduce Angular Ivy, a new Angular renderer that is certainly different from most other frameworks. An interesting aspect of Angular is Google team discarded virtual dom and utilized incremental dom mainly to enhance performance in mobile devices. So let's compare both virtual dom and incremental dom to gain better insigts and understanding into both aspects.
    * __What is Incremental DOM in Angular?__
        * Before Angular version 4, the framework used traditional DOM to update and diffing approach, but after Angular version 4, the framework started working on incremental DOM. One of the most powerful advantages of incremental DOM is it is more memory-efficient.
        * Whenever the state of the application changes, the incremental DOM approach changes the actual DOM tree directly, it does not create the new DOM tree representation for changes like the virtual DOM, Incremental DOM gets instructions to update the DOM tree and these instructions are executed directly on the actual DOM.
        * While Angular does not use Incremental DOM by default, principles of incremental updates can still be applied within Angular applications through strategies like OnPush change detection, optimizing *ngFor with trackBy, and minimizing unnecessary DOM updates. 
        * One of the main advantages of Incremental dom is that it's designed to be tree-shakable. The term tree-shaking is commonly used in JavaScript to descirbe the process of elminiating dead code (refer to prior notes for a more in-depth explanation) from the final bundle during the build process. 
            * This partiuclarly helps in optimizing application performance by reducing the size of the JavaScript files that need to be downloaded and exectued. Incremental DOM is build with a modular architecutre, meaning its functions can be imported individually. This modularity allows modern JavaScript bundlers (like Webpack and Rollup) to analyze and remove unused code.
    * __Advantages of using Incremental DOM__
        1. __Efficient Memory Management__
            * The Incremental DOM framework does not use separate memory to represent the component. It modifies the original DOM only so it minimizes memory usage and helps for memory management.
        1. __Selective Updates__
            * Incremental DOM updates only that part of DOM that has changed, it doesn't re-render the whole DOM tree. This can significantly reduce the maount of work the browser or rendering engine has to do, leading to better performance.
        1. __Faster Rendering__
            * Unlike the Virtual DOM, which creates a full represenation of the DOM in memory and then applies changes in a batch, Incremental DOM directly updates the real DOM as changes occur and does not create a new DOM tree in memory. This method can lead to faster rendering.
    * __What is a Virtual DOM in Angular?__
        * The Virtual DOM is a lightweight copy of the actual DOM. The DOM tree represents the elements of a webpage, these elements include headers, headings, videos, and images. For large and complex applications with frequent updates, directly manipulating the DOM creates performance issues.
        * The virtual DOM concept solves this issue by creating another copy of the original virtual DOM object in memory. Instead of updating the real DOM directly, changes are first applied to the Virtual DOM. Then, the new virtual DOM tree is compared with the previous Virtual DOM, and whatever changes are made only that part of the elements are changed in the real DOM tree and updated elements will get rendered on the web page again.
        * __Advantages of using the Virtual DOM__
            * The Virtual DOM approach offers several key benefits that contribute to more efficient, performant, and maintainable web applications:
                1. __Improved Performance__
                    * The real DOM is slow to manipulate directly. By reducing the number of direct interactions with the real and new entire virtual DOM, the Virtual DOM significantly improves the performance of your application. The selective updates ensure that your UI remians responsive, even in complex applications with frequent stage changes.
                1. __Smoother User Experience__
                    * The efficiency of the Virtual DOM in handling updates leads to a smoother user experience. UI updates happen almost instantly, with reduced lag, providing a seamless interaction for users across mobile devices. Additionally, the Virtual DOM can batch multiple updates together, further optimizing performance.
                1. __Simplified Development__
                    * The Virtual DOM allows developers to adopt a declarative approach to building UIs. Instead of worrying about how to efficiently update the entire virtual DOM itself, developers can focus on what hte UI should look like at any given state. This simplifies the development process and reduces the potential for errors.
                1. __Reduced Complexity__
                    * Manually optimizing the entire DOM tree for updates is complex and error-prone. The Virtual DOM abstracts this complexity, automatically optimizing updates and making the codebase easier to maintain. THis also makes debugging simpler, as the Virtual DOM provides a clear and consistent path from state changes to UI updates.
                1. __Cross-platform Consistency__
                    * Different browsers and platforms handle DOM manipulation in slighly different ways, which can lead to inconsistencies in how UIs are rendered. The Virtual DOM abstracts these differences, ensuring that the UI behaves consistently across all platforms.