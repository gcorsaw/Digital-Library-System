// ============================================================
// Digital Library — home screen interactions (Fully Integrated)
// ============================================================

const loginBtn = document.getElementById("loginBtn");
const loginLabel = document.getElementById("loginLabel");
const userNameEl = document.getElementById("userName");
const welcomeBanner = document.getElementById("welcomeBanner");

const homeBtn = document.getElementById("homeBtn");
const addBtn = document.getElementById("addBtn");
const addModal = document.getElementById("addModal"); 
const addModalClose = document.getElementById("addModalClose"); 
const menuBtn = document.getElementById("menuBtn");
const sideMenu = document.getElementById("sideMenu");

const tiles = document.querySelectorAll(".tile");
const resultsSection = document.getElementById("results");
const resultsTitle = document.getElementById("resultsTitle");
const resultsList = document.getElementById("resultsList");

const API_BASE = "http://127.0.0.1:8000";

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8000/api'
    : '/api'

// --- Live Authentication Configuration ---
const signupBtn = document.getElementById("signupBtn");
const signupLabel = document.getElementById("signupLabel");

let currentAuthToken = localStorage.getItem("library_auth_token") || null;
let currentUsername = localStorage.getItem("library_username") || "guest";

function updateUsernameTitle(newUsername) {
  document.title = `${newUsername}'s Digital Library`;
  userNameEl.textContent = newUsername;
}

function resetUsernameTitle() {
  document.title = "Digital Library — Home";
  userNameEl.textContent = "guest";
}

function syncAuthState() {
  if (currentAuthToken) {
    loginBtn.setAttribute("aria-pressed", "true");
    loginLabel.textContent = "Log out";
    if (signupBtn) signupBtn.hidden = true;
    updateUsernameTitle(currentUsername);
  } else {
    loginBtn.setAttribute("aria-pressed", "false");
    loginLabel.textContent = "Log in";
    if (signupBtn) signupBtn.hidden = false;
    resetUsernameTitle();
  }
}

if (signupBtn) {
  signupBtn.addEventListener("click", async () => {
    const username = prompt("Choose a username (3-30 chars):");
    if (!username) return;
    const email = prompt("Enter your email address:");
    if (!email) return;
    const password = prompt("Choose a password (min 8 chars):");
    if (!password) return;

    try {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, email, password })
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Registration failed");

      localStorage.setItem("library_auth_token", data.access_token);
      localStorage.setItem("library_username", data.user.username);
      currentAuthToken = data.access_token;
      currentUsername = data.user.username;
      
      alert(`Welcome to your digital library, ${currentUsername}! Account created successfully.`);
      syncAuthState();
    } catch (err) {
      alert(`Registration Error: ${err.message}`);
    }
  });
}

loginBtn.addEventListener("click", async () => {
  if (currentAuthToken) {
    localStorage.removeItem("library_auth_token");
    localStorage.removeItem("library_username");
    currentAuthToken = null;
    currentUsername = "guest";
    syncAuthState();
    if (resultsSection) resultsSection.hidden = true;
  } else {
    const usernameOrEmail = prompt("Enter your username or email:");
    if (!usernameOrEmail) return;
    const password = prompt("Enter your password:");
    if (!password) return;

    loginLabel.textContent = "Connecting...";
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: usernameOrEmail, password: password })
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Login failed");

      localStorage.setItem("library_auth_token", data.access_token);
      localStorage.setItem("library_username", data.user.username);
      currentAuthToken = data.access_token;
      currentUsername = data.user.username;
      
      syncAuthState();
    } catch (err) {
      alert(`Login Failed: ${err.message}`);
      syncAuthState();
    }
  }
});

// --- Home icon --------------------------------------------------------
homeBtn.addEventListener("click", () => {
  closeMenu();
  welcomeBanner.scrollIntoView({ behavior: "smooth", block: "center" });
});

// --- Add ("+") icon: open the add-book/add-game modal ------------------
const addModalStatus = document.getElementById("addModalStatus");
const addBookForm = document.getElementById("addBookForm");
const addGameForm = document.getElementById("addGameForm");
const modalTabs = document.querySelectorAll(".modal__tab");

if (modalTabs && modalTabs.length > 0) { 
  modalTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      modalTabs.forEach((t) => t.setAttribute("aria-pressed", "false"));
      tab.setAttribute("aria-pressed", "true");
      
      const showBook = tab.dataset.kind === "book";
      if (addBookForm) addBookForm.hidden = !showBook;
      if (addGameForm) addGameForm.hidden = showBook;
      if (addModalStatus) addModalStatus.textContent = "";
    });
  });
}

addBtn.addEventListener("click", () => {
  if (addModal) addModal.hidden = false;
  if (addModalStatus) addModalStatus.textContent = "";
});

addModalClose.addEventListener("click", () => {
  if (addModal) addModal.hidden = true;
});

// --- API Context Request Helpers ---
async function fetchJSON(path) {
  const headers = {};
  if (currentAuthToken) { 
    headers["Authorization"] = `Bearer ${currentAuthToken}`; 
  }

  const res = await fetch(`${API_BASE}${path}`, { headers: headers });
  if (!res.ok) {
    throw new Error(`${path} responded with ${res.status}`);
  }
  return res.json();
}

async function submitEntry(path, payload) {
  const headers = { "Content-Type": "application/json" };
  if (currentAuthToken) { headers["Authorization"] = `Bearer ${currentAuthToken}`; }

  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: headers,
    body: JSON.stringify(payload),
  });
  
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `Request failed with ${res.status}`);
  }
  return data;
}

addBookForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(addBookForm);
  const payload = {
    book_title: formData.get("book_title"),
    book_isbn: formData.get("book_isbn") || null,
    publish_date: formData.get("publish_date") || null,
  };
  addModalStatus.textContent = "Adding…";
  try {
    await submitEntry("/books", payload);
    addModalStatus.textContent = "Book added.";
    if (typeof routeHandlers["/books"] === "function") { await routeHandlers["/books"](); }
    addBookForm.reset();
    setTimeout(() => {
        if (addModal) addModal.hidden = true;
    }, 800);
  } catch (error) {
    addModalStatus.textContent = error.message;
  }
});

addGameForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(addGameForm);
  const payload = {
    game_title: formData.get("game_title"),
    publisher: formData.get("publisher") || null,
    release_date: formData.get("release_date") || null,
  };
  addModalStatus.textContent = "Adding…";
  try {
    await submitEntry("/games", payload);
    addModalStatus.textContent = "Game added.";
    if (typeof routeHandlers["/games"] === "function") { await routeHandlers["/games"](); }
    addGameForm.reset();
    setTimeout(() => {
        if (addModal) addModal.hidden = true;
    }, 800);
  } catch (error) {
    addModalStatus.textContent = error.message;
  }
});

// --- Hamburger menu -----------------------------------------------------
if (menuBtn) {
  menuBtn.addEventListener("click", () => {
    const isOpen = menuBtn.getAttribute("aria-expanded") === "true";
    isOpen ? closeMenu() : openMenu();
  });
}

function openMenu() {
  if (sideMenu) sideMenu.hidden = false;
  if (menuBtn) menuBtn.setAttribute("aria-expanded", "true");
}

function closeMenu() {
  if (sideMenu) sideMenu.hidden = true;
  if (menuBtn) menuBtn.setAttribute("aria-expanded", "false");
}

if (sideMenu) {
  sideMenu.querySelectorAll(".side-menu__item").forEach((item) => {
    item.addEventListener("click", async (event) => {
      event.preventDefault();
      const action = item.dataset.action;
      closeMenu();

      if (action === "search") {
        const query = prompt("Enter a single word to search for:");
        if (!query) return;
        try {
          const data = await fetchJSON(`/books/search?title=${encodeURIComponent(query)}`);
          renderResults(`Search results for "${query}"`, data.books.map(b => {
            const statusStr = b.read_status ? ` [${b.read_status}]` : "";
            const ratingStr = b.rating ? ` (${b.rating}★)` : "";
            return `${b.book_title}${statusStr}${ratingStr}`;
          }));
        } catch (err) { renderError(err.message); }
      } 
      else if (action === "edit") {
        const bookTitle = prompt("Enter the exact Book Title you want to update:");
        const newDesc = prompt("Enter the new description:");
        if (!bookTitle || !newDesc) return;
        try {
          const headers = { "Content-Type": "application/json" };
          if (currentAuthToken) headers["Authorization"] = `Bearer ${currentAuthToken}`;
          const res = await fetch(`${API_BASE}/books/description?book_title=${encodeURIComponent(bookTitle)}`, {
            method: "PUT",
            headers: headers,
            body: JSON.stringify({ book_description: newDesc })
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "Update failed");
          alert("Description updated successfully!");
          if (typeof routeHandlers["/books"] === "function") { await routeHandlers["/books"](); }
        } catch (err) { alert(`Error: ${err.message}`); }
      }
      else if (action === "remove") {
        const bookTitle = prompt("Enter the exact Book Title you want to permanently delete:");
        if (!bookTitle) return;
        if (!confirm(`Are you sure you want to delete "${bookTitle}"?`)) return;
        try {
          const headers = {};
          if (currentAuthToken) headers["Authorization"] = `Bearer ${currentAuthToken}`;
          const res = await fetch(`${API_BASE}/books?book_title=${encodeURIComponent(bookTitle)}`, { method: "DELETE", headers: headers });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "Deletion failed");
          alert("Entry deleted successfully!");
          if (typeof routeHandlers["/books"] === "function") { await routeHandlers["/books"](); }
        } catch (err) { alert(`Error: ${err.message}`); }
      }
      else if (action === "progress") {
        const bookTitle = prompt("Enter the exact Book Title you want to log progress for:");
        if (!bookTitle) return;
        const statusChoice = prompt("Enter reading status (type 'read' or 'want to read'):");
        if (!statusChoice) return;
        let ratingChoice = null;
        if (statusChoice.trim().toLowerCase() === "read") {
          const ratingInput = prompt("Rate this book from 1 to 5 stars (Optional, leave blank if unrated):");
          if (ratingInput) ratingChoice = parseInt(ratingInput, 10);
        }
        try {
          const headers = { "Content-Type": "application/json" };
          if (currentAuthToken) headers["Authorization"] = `Bearer ${currentAuthToken}`;
          const res = await fetch(`${API_BASE}/books/progress?book_title=${encodeURIComponent(bookTitle)}`, {
            method: "PUT",
            headers: headers,
            body: JSON.stringify({ read_status: statusChoice, rating: ratingChoice })
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "Progress update failed");
          alert(`Successfully logged "${bookTitle}" as "${statusChoice}" with a ${ratingChoice || 'no'} star rating!`);
          if (typeof routeHandlers["/books"] === "function") { await routeHandlers["/books"](); }
        } catch (err) { alert(`Error: ${err.message}`); }
      }
    });
  });
}


// --- Action UI Data Rendering ---
function renderResults(title, rows) {
  if (!resultsTitle || !resultsList || !resultsSection) return;
  resultsTitle.textContent = title;
  resultsList.innerHTML = "";
  if (rows.length === 0) {
    const li = document.createElement("li");
    li.textContent = "Nothing here yet.";
    resultsList.appendChild(li);
  } else {
    rows.forEach((row) => {
      const li = document.createElement("li");
      li.textContent = row;
      resultsList.appendChild(li);
    });
  }
  resultsSection.hidden = false;
  resultsSection.style.display = "block";
}

// Global visual tracking component update logs
function renderError(message) {
  if (!resultsTitle || !resultsList || !resultsSection) return;
  resultsTitle.textContent = "Couldn't load that";
  resultsList.innerHTML = "";
  const li = document.createElement("li");
  li.textContent = `${message} — is main.py running on ${API_BASE}?`;
  resultsList.appendChild(li);
  resultsSection.hidden = false;
}

const routeHandlers = {
  "/books": async () => {
    const data = await fetchJSON("/books"); 
    renderResults("Your books", data.books.map((b) => {
      const statusStr = b.read_status ? ` [${b.read_status}]` : "";
      const ratingStr = b.rating ? ` (${b.rating}★)` : "";
      return `${b.book_title}${statusStr}${ratingStr}`;
    }));
  },
  "/games": async () => {
    const data = await fetchJSON("/games");
    renderResults("Your games", data.games.map((g) => g.game_title));
  },
  "/all": async () => {
    const [books, games] = await Promise.all([
      fetchJSON("/books"), 
      fetchJSON("/games"),
    ]);
    const rows = [
      ...books.books.map((b) => {
        const statusStr = b.read_status ? ` [${b.read_status}]` : "";
        const ratingStr = b.rating ? ` (${b.rating}★)` : "";
        return `${b.book_title}${statusStr}${ratingStr} (book)`;
      }),
      ...games.games.map((g) => `${g.game_title} (game)`),
    ];
    renderResults("Everything in your library", rows);
  },
};

if(tiles){
    tiles.forEach((tile) => {
        tile.addEventListener("click", async() =>{
            const handler = routeHandlers[tile.dataset.route];
            if(!handler) return;
            try{
                await handler();
            } catch (error){
                console.error(error);
                renderError(error.message);
            }
        });
    });
}

window.addEventListener("DOMContentLoaded", () => {
    syncAuthState();
});