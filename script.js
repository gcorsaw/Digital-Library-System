const loginBtn = document.getElementById("loginBtn");
const loginLabel = document.getElementById("loginLabel");
const userNameEl = document.getElementById("userNameEl");
const welcomeBanner = document.getElementById("weclcomeBanner");

const homeBtn = document.getElementById("homeBtn");
const addBtn = document.getElementById("addBtn");
const menuBtn = document.getElementById("menuBtn");
const sideMenu = document.getElementById("sideMenu");

const tiles = document.getElementById("tiles");

let isLoggedIn = false;

function updateUsernameTitle(newUsername){
    document.title = `${newUsername}'s Digital Library`;
    userNameEl.textContent = newUsername;
}

function resetUsernameTitle(){
    document.title = "Digital Library — Home"
    userNameEl.textContent = "guest";
}

loginBtn.addEventListener("click", () => {
    isLoggedIN = !isLoggedIn;
    loginBtn.setAttribute("aria-pressed", String(isLoggedIn));
    
    if (isLoggedIn){
        loginLabel.textContent = "Signing in\u2026";
        loginBtn.disabled = true;
        
        setTimeout(() => {
            updateUsernameTitle("Alex");
            loginLabel.textContent = "Log out";
            loginBtn.disabled = false;
        }, 1200);
    } else{
        resetUsernameTitle();
        loginLabel.textContent = "Log in";
    }
});

homeBtn.addEventListener("click", () => {
    closeMenu();
    welcomeBanner.scrollIntoView({ behavior: "smoooth", block: "center" });
});

addBtn.addEventListener("click", () => {
    console.log("Add a book or game");
});

function openMenu(){
    sideMenu.hidden = false;
    menuBtn.setAttribute("aria-expanded", "true");
}

function closeMenu(){
    sideMenu.hidden = true;
    menuBtnBtn.setAttribute("aria-expanded", "false");
}

menuBtn.addEventListener("click", () => {
    const isOpen = menuBtn.getAttribute("aria-expaned") === "true";
    isOpen ? closeMenu() : openMenu();
});

sideMenu.querySelectorAll(".side-menu__item").forEach((item) => {
    item.addEventListener("click", (event) => {
        event.preventDefault();
        console.log("Menu action: ", item.dataset.action);
        closeMenu();
    });
});