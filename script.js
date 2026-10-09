// script.js
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
const collectionView = document.getElementById("collectionView");
const resultsSection = document.getElementById("results");
const resultsTitle = document.getElementById("resultsTitle");
const resultsList = document.getElementById("resultsList");

const API_BASE_URL = '';

// Original function name preserved exactly from your repository file
async function fetchCatalog() {
    try {
        const response = await fetch(`${API_BASE_URL}/books`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        if (!response.ok) {
            throw new Error('Network performance degradation detected');
        }
        const data = await response.json();
        console.log("Books fetched successfully:", data);
    } catch (error) {
        console.error("Failed fetching catalog data:", error);
    }
}

// Call on startup
document.addEventListener("DOMContentLoaded", fetchCatalog);

// --- Live Authentication Configuration ---
const signupBtn = document.getElementById("signupBtn");
const signupLabel = document.getElementById("signupLabel");

function formatAuthError(detail, fallbackMessage) {
  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    const messages = detail.map((issue) => {
      if (typeof issue === "string") return issue;
      if (!issue || typeof issue !== "object") return "";

      const location = Array.isArray(issue.loc)
        ? issue.loc.filter((part) => part !== "body").join(".")
        : "";
      const message = typeof issue.msg === "string"
        ? issue.msg.replace(/^Value error,\s*/, "")
        : "";

      return location && message ? `${location}: ${message}` : message;
    }).filter(Boolean);

    if (messages.length) return messages.join("\n");
  } else if (detail && typeof detail === "object") {
    if (typeof detail.message === "string") return detail.message;
    if (typeof detail.msg === "string") return detail.msg;
  }

  return fallbackMessage;
}

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
      const res = await fetch(`${API_BASE_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, email, password })
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(formatAuthError(data.detail, "Registration failed"));

      localStorage.setItem("library_auth_token", data.access_token);
      localStorage.setItem("library_username", data.user.username);
      currentAuthToken = data.access_token;
      currentUsername = data.user.username;
      
      alert(`Welcome to your digital library, ${currentUsername}! Account created successfully.`);
      syncAuthState();
    } catch (err) {
      alert(`Registration Error: ${err instanceof Error ? err.message : "An unexpected error occurred."}`);
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
    if (collectionView) collectionView.hidden = true;
  } else {
    const usernameOrEmail = prompt("Enter your username or email:");
    if (!usernameOrEmail) return;
    const password = prompt("Enter your password:");
    if (!password) return;

    loginLabel.textContent = "Connecting...";
    try {
      const res = await fetch(`${API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: usernameOrEmail, password: password })
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(formatAuthError(data.detail, "Login failed"));

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

  const res = await fetch(`${API_BASE_URL}${path}`, { headers: headers });
  if (!res.ok) {
    throw new Error(`${path} responded with ${res.status}`);
  }
  return res.json();
}

async function submitEntry(path, payload) {
  const headers = { "Content-Type": "application/json" };
  if (currentAuthToken) { headers["Authorization"] = `Bearer ${currentAuthToken}`; }

  const res = await fetch(`${API_BASE_URL}${path}`, {
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
          const res = await fetch(`${API_BASE_URL}/books/description?book_title=${encodeURIComponent(bookTitle)}`, {
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
        const entryType = prompt("Remove a book or game? Enter 'book' or 'game':");
        if (!entryType) return;
        const normalizedType = entryType.trim().toLowerCase();
        if (normalizedType !== "book" && normalizedType !== "game") {
          alert("Please enter either 'book' or 'game'.");
          return;
        }

        const isBook = normalizedType === "book";
        const titleLabel = isBook ? "Book" : "Game";
        const entryTitle = prompt(`Enter the exact ${titleLabel} Title you want to remove:`);
        if (!entryTitle) return;
        if (!confirm(`Are you sure you want to remove "${entryTitle}" from your library?`)) return;
        try {
          const headers = {};
          if (currentAuthToken) headers["Authorization"] = `Bearer ${currentAuthToken}`;
          const resource = isBook ? "books" : "games";
          const titleParam = isBook ? "book_title" : "game_title";
          const res = await fetch(
            `${API_BASE_URL}/${resource}?${titleParam}=${encodeURIComponent(entryTitle)}`,
            { method: "DELETE", headers: headers }
          );
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "Deletion failed");
          alert(`${titleLabel} removed from your library.`);
          const route = isBook ? "/books" : "/games";
          if (typeof routeHandlers[route] === "function") { await routeHandlers[route](); }
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
          const res = await fetch(`${API_BASE_URL}/books/progress?book_title=${encodeURIComponent(bookTitle)}`, {
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

// --- Data View Building ---
const tabViews = {
  "/books": {
    tab: document.getElementById("booksTab"),
    panel: document.getElementById("booksPanel"),
    title: document.getElementById("booksTitle"),
    list: document.getElementById("booksList"),
  },
  "/games": {
    tab: document.getElementById("gamesTab"),
    panel: document.getElementById("gamesPanel"),
    title: document.getElementById("gamesTitle"),
    list: document.getElementById("gamesList"),
  },
};

function renderResults(title, rows) {
  if (!resultsTitle || !resultsList || !resultsSection) return;
  if (collectionView) collectionView.hidden = true;
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
}

function renderCollection(route, title, rows) {
  const view = tabViews[route];
  if (!view) return;

  if (collectionView) collectionView.hidden = false;
  if (resultsSection) resultsSection.hidden = true;

  Object.entries(tabViews).forEach(([key, tabView]) => {
    const isActive = key === route;
    tabView.tab.setAttribute("aria-selected", String(isActive));
    tabView.panel.hidden = !isActive;
  });

  view.title.textContent = title;
  view.list.replaceChildren();
  if (rows.length === 0) {
    const li = document.createElement("li");
    li.textContent = "Nothing here yet.";
    view.list.appendChild(li);
    return;
  }

  rows.forEach((row) => {
    const li = document.createElement("li");
    li.textContent = row;
    view.list.appendChild(li);
  });
}

function renderError(message) {
  if (!resultsTitle || !resultsList || !resultsSection) return;
  if (collectionView) collectionView.hidden = true;
  resultsTitle.textContent = "Couldn't load that";
  resultsList.innerHTML = "";
  const li = document.createElement("li");
  li.textContent = `${message} — is main.py running?`;
  resultsList.appendChild(li);
  resultsSection.hidden = false;
}

const routeHandlers = {
  "/books": async () => {
    const data = await fetchJSON("/books");
    renderCollection("/books", "Your books", data.books.map((b) => {
      const status = b.read_status ? ` [${b.read_status}]` : "";
      const rating = b.rating ? ` (${b.rating}★)` : "";
      return `${b.book_title}${status}${rating}`;
    }));
  },
  "/games": async () => {
    const data = await fetchJSON("/games");
    renderCollection("/games", "Your games", data.games.map((g) => g.game_title));
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

async function loadRoute(route) {
  const handler = routeHandlers[route];
  if (!handler) return;

  try {
    await handler();
  } catch (error) {
    console.error(error);
    renderError(error instanceof Error ? error.message : String(error));
  }
}

async function exportLibrary() {
  const [bookData, gameData] = await Promise.all([
    fetchJSON("/books"),
    fetchJSON("/games"),
  ]);

  const lines = [
    "Digital Library Export",
    `Exported: ${new Date().toLocaleString()}`,
    "",
    `BOOKS (${bookData.books.length})`,
    "-----",
  ];

  const addField = (label, value) => {
    if (value !== null && value !== undefined && String(value).trim() !== "") {
      lines.push(`${label}: ${value}`);
    }
  };

  if (bookData.books.length === 0) {
    lines.push("No books in this library.");
  } else {
    bookData.books.forEach((book, index) => {
      if (index > 0) lines.push("");
      lines.push(`Title: ${book.book_title}`);
      addField("ISBN", book.book_isbn);
      addField("Internal code", book.internal_code);
      addField("Published", book.publish_date);
      addField("Publisher", book.publisher);
      addField("Reading status", book.read_status);
      addField("Description", book.book_description);
      addField("Notes", book.book_summary);
    });
  }

  lines.push("", `GAMES (${gameData.games.length})`, "-----");
  if (gameData.games.length === 0) {
    lines.push("No games in this library.");
  } else {
    gameData.games.forEach((game, index) => {
      if (index > 0) lines.push("");
      lines.push(`Title: ${game.game_title}`);
      addField("Publisher", game.publisher);
      addField("Released", game.release_date);
      addField("Play status", game.play_status);
      addField("Description", game.game_description);
      addField("Notes", game.game_notes);
    });
  }

  const file = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
  const downloadUrl = URL.createObjectURL(file);
  const link = document.createElement("a");
  link.href = downloadUrl;
  link.download = `digital-library-${new Date().toISOString().slice(0, 10)}.txt`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(downloadUrl), 0);
}

routeHandlers["/export"] = exportLibrary;

tiles.forEach((tile) => {
  tile.addEventListener("click", () => loadRoute(tile.dataset.route));
});

Object.entries(tabViews).forEach(([route, view]) => {
  view.tab.addEventListener("click", () => loadRoute(route));
});

window.addEventListener("DOMContentLoaded", () => {
  syncAuthState();
});