// ============================================================
// Digital Library — home screen interactions (Fully Patched)
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

const API_BASE = "http://localhost:8000";
const MOCK_TOKEN = "Bearer local-test-admin-token";

// --- Login / logout -------------------------------------------------
let isLoggedIn = false;
let storedToken = localStorage.getItem("library_auth_token") || null;

function getUserFromToken(token){
    if (!token || token === "Bearer local-test-admin-token") {
        return { "username": "AlexLocalTest" };
    }
    try{
        const parts = token.split('.');
        const base64URL = parts.length === 3 ? parts[1] : token; // Extract index 1 string cleanly
        const base64 = base64URL.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c){
            return '%' + ('00' + c.charCodeAt(0).toString(16).slice(-2)); 
        }).join(''));
        return JSON.parse(jsonPayload);
    } catch(e){
        return { "username": "AlexLocalTest" };
    }
}

function updateUsernameTitle(newUsername) {
  document.title = `${newUsername}'s Digital Library`;
  userNameEl.textContent = newUsername;
}

function resetUsernameTitle() {
  document.title = "Digital Library — Home";
  userNameEl.textContent = "guest";
}

loginBtn.addEventListener("click", () => {
  isLoggedIn = !isLoggedIn;
  loginBtn.setAttribute("aria-pressed", String(isLoggedIn));

  if (isLoggedIn) {
    loginLabel.textContent = "Signing in\u2026";
    loginBtn.disabled = true;

    setTimeout(() => {
      updateUsernameTitle("Alex");
      loginLabel.textContent = "Log out";
      loginBtn.disabled = false;
    }, 1200);
  } else {
    resetUsernameTitle();
    loginLabel.textContent = "Log in";
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

// Connect UI Actions for showing and hiding the layout container
addBtn.addEventListener("click", () => {
  if (addModal) addModal.hidden = false;
  if (addModalStatus) addModalStatus.textContent = "";
});

addModalClose.addEventListener("click", () => {
  if (addModal) addModal.hidden = true;
});

async function submitEntry(path, payload) {
  const headers = { "Content-Type": "application/json" };
  if (isLoggedIn) { headers["Authorization"] = MOCK_TOKEN; }

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
  addModalStatus.textContent = "Adding\u2026";
  try {
    await submitEntry("/books", payload);
    addModalStatus.textContent = "Book added.";
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
  addModalStatus.textContent = "Adding\u2026";
  try {
    await submitEntry("/games", payload);
    addModalStatus.textContent = "Game added.";
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
          renderResults(`Search results for "${query}"`, data.books.map(b => b.book_title));
        } catch (err) { renderError(err.message); }
      } 
      else if (action === "edit") {
        const bookId = prompt("Enter the Book ID you want to update:");
        const newDesc = prompt("Enter the new description:");
        if (!bookId || !newDesc) return;
        try {
          const headers = { "Content-Type": "application/json" };
          if (isLoggedIn) headers["Authorization"] = MOCK_TOKEN;
          await fetch(`${API_BASE}/books/${bookId}/description`, {
            method: "PUT",
            headers: headers,
            body: JSON.stringify({ book_description: newDesc })
          });
          alert("Description updated successfully!");
        } catch (err) { alert(`Error: ${err.message}`); }
      }
      else if (action === "remove") {
        const bookId = prompt("Enter the Book ID you want to permanently delete:");
        if (!bookId) return;
        if (!confirm("Are you sure you want to delete this entry?")) return;
        try {
          const headers = {};
          if (isLoggedIn) headers["Authorization"] = MOCK_TOKEN;
          await fetch(`${API_BASE}/books/${bookId}`, { method: "DELETE", headers: headers });
          alert("Entry deleted successfully!");
        } catch (err) { alert(`Error: ${err.message}`); }
      }
    });
  });
}

// --- Action tiles: fetch real data from the FastAPI backend --------------
async function fetchJSON(path) {
  const headers = {};
  if (isLoggedIn) { 
    headers["Authorization"] = MOCK_TOKEN; 
  }

  const res = await fetch(`${API_BASE}${path}`, { headers: headers });
  if (!res.ok) {
    throw new Error(`${path} responded with ${res.status}`);
  }
  return res.json();
}

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
    renderResults("Your books", data.books.map((b) => b.book_title));
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
      ...books.books.map((b) => `${b.book_title} (book)`),
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
    isLoggedIn = true;
    const loginBtnEl = document.getElementById("loginBtn");
    const loginLabelEl = document.getElementById("loginLabel");
    if (loginBtnEl) loginBtnEl.setAttribute("aria-pressed", "true");
    if (loginLabelEl) loginLabelEl.textContent = "Log out";
    updateUsernameTitle("AlexLocalTest");
});