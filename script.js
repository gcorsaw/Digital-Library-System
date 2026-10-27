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

// Populated base URL context for backend communication
const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:5000';

// Configuration flags
const AUTH_PROVIDER = process.env.AUTH_PROVIDER || 'LOCAL';

// Initialize Cognito JWKS client with corrected endpoint URL interpolation
const cognitoClient = jwksClient({
  jwksUri: `https://cognito-idp.\${process.env.AWS_REGION}.amazonaws.com/\${process.env.COGNITO_USER_POOL_ID}/.well-known/jwks.json`
});

function getKey(header, callback) {
  cognitoClient.getSigningKey(header.kid, function(err, key) {
    if (err) return callback(err);
    const signingKey = key.getPublicKey();
    callback(null, signingKey);
  });
}

/**
 * Unified Authentication Middleware
 */
const authenticateToken = (req, res, next) => {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];

  if (!token) return res.status(401).json({ message: 'Authentication token missing' });

  if (AUTH_PROVIDER === 'COGNITO') {
    // 1. AWS Cognito Verification Strategy
    jwt.verify(token, getKey, { algorithms: ['RS256'] }, (err, decoded) => {
      if (err) return res.status(403).json({ message: 'Invalid Cognito Token', error: err.message });
      
      // Standardize the user object mapping from Cognito claims
      req.user = {
        id: decoded.sub,
        email: decoded.email,
        provider: 'COGNITO'
      };
      next();
    });
  } else {
    // 2. Standard Self-Hosted Verification Strategy
    jwt.verify(token, process.env.JWT_SECRET, { algorithms: ['HS256'] }, (err, decoded) => {
      if (err) return res.status(403).json({ message: 'Invalid Local Token' });
      
      // Standardize the user object mapping from Local DB schema
      req.user = {
        id: decoded.id,
        email: decoded.email,
        provider: 'LOCAL'
      };
      next();
    });
  }
};

// Original function name preserved exactly from your repository file
async function fetchCatalog() {
    const token = localStorage.getItem("library_auth_token");
    if (!token) return; // Not signed in: /books would only answer 401.
    try {
        const response = await fetch(`\${API_BASE_URL}/books`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer \${token}`
            }
        });
        if (!response.ok) {
            throw new Error(`Catalog request failed with status \${response.status}`);
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

      return location && message ? `\${location}: \${message}` : message;
    }).filter(Boolean);

    if (messages.length) return messages.join("\n");
  } else if (detail && typeof detail === "object") {
    if (typeof detail.message === "string") return detail.message;
    if (typeof detail.msg === "string") return detail.msg;
  }

  return fallbackMessage;
}

const NETWORK_ERROR_MESSAGE =
  "Could not reach the server. Check that the app is running and try again.";
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Turn any thrown value into text a person can act on.
function describeError(err, fallback = "An unexpected error occurred.") {
  if (err instanceof TypeError) return NETWORK_ERROR_MESSAGE; // fetch() network failure
  return err instanceof Error && err.message ? err.message : fallback;
}

// Read a JSON body without throwing when the server returns HTML or nothing.
async function readJson(response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

// Build an Error from a failed response, keeping the HTTP status for callers.
function apiError(response, data, fallback) {
  const message =
    formatAuthError(data && data.detail, "") ||
    (response.status >= 500
      ? `\${fallback}: the server had a problem (error \${response.status}). Please try again.`
      : `\${fallback} (error \${response.status}).`);
  const error = new Error(message);
  error.status = response.status;
  return error;
}

// Alert for failed actions; signs the user out if their session is no longer valid.
function reportActionError(err) {
  if (err && err.status === 401) {
    clearAuthSession();
    alert("Your session has expired. Please log in again.");
    return;
  }
  alert(`Error: \${describeError(err)}`);
}

// Cognito pool policy: 8+ chars with upper, lower, number, symbol, no edge spaces.
function cognitoPasswordProblems(password) {
  const problems = [];
  if (password.length < 8) problems.push("at least 8 characters");
  if (!/[A-Z]/.test(password)) problems.push("an uppercase letter");
  if (!/[a-z]/.test(password)) problems.push("a lowercase letter");
  if (!/[0-9]/.test(password)) problems.push("a number");
  if (!/[^A-Za-z0-9\s]/.test(password)) problems.push("a symbol (such as ! # $ %)");
  if (/^\s|\s$/.test(password)) problems.push("no spaces at the start or end");
  return problems;
}

let currentAuthToken = localStorage.getItem("library_auth_token") || null;
let currentUsername = localStorage.getItem("library_username") || "guest";

function updateUsernameTitle(newUsername) {
  document.title = `\${newUsername}'s Digital Library`;
  userNameEl.textContent = newUsername;
}

function resetUsernameTitle() {
  document.title = "Digital Library — Home";
  userNameEl.textContent = "guest";
}

function clearAuthSession() {
  localStorage.removeItem("library_auth_token");
  localStorage.removeItem("library_username");
  currentAuthToken = null;
  currentUsername = "guest";
  syncAuthState();
}

function syncAuthState() {
  if (currentAuthToken) {
    loginBtn.setAttribute("aria-pressed", "true");
    loginLabel.textContent = "Log out";
    if (signupBtn) signupBtn.hidden = true;
    updateUsernameTitle(currentUsername);
    if (resultsTitle?.textContent === "Log in to view your library") {
      resultsSection.hidden = true;
    }
  } else {
    loginBtn.setAttribute("aria-pressed", "false");
    loginLabel.textContent = "Log in";
    if (signupBtn) signupBtn.hidden = false;
    resetUsernameTitle();
  }
}

async function postAuthRequest(path, payload, fallbackMessage) {
  const response = await fetch(`\${API_BASE_URL}\${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await readJson(response);
  if (!response.ok) {
    throw apiError(response, data, fallbackMessage);
  }
  return data;
}

// Ask for the emailed code, allowing a few attempts for typos.
async function confirmCognitoAccount(email, firstPrompt) {
  let message = firstPrompt;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    const code = (prompt(message) || "").trim();
    if (!code) return false;
    try {
      await postAuthRequest(
        "/auth/cognito/confirm",
        { email, confirmation_code: code },
        "Cognito email confirmation failed"
      );
      return true;
    } catch (err) {
      if (err.status !== 400 || attempt === 3) throw err;
      message = `\${err.message}\n\nTry again (attempt \${attempt + 1} of 3) or press Cancel to stop:`;
    }
  }
  return false;
}

function saveAuthSession(data, username) {
  if (!data.access_token) {
    throw new Error("The authentication service did not return an access token.");
  }
  localStorage.setItem("library_auth_token", data.access_token);
  localStorage.setItem("library_username", username);
  currentAuthToken = data.access_token;
  currentUsername = username;
  syncAuthState();
}

if (signupBtn) {
  signupBtn.addEventListener("click", async () => {
    let errorStage = "Registration";
    try {
      const provider = prompt("Create account with 1) Local account or 2) Amazon Cognito? Enter 1 or 2:");
      if (!provider) return;

      if (provider.trim() === "2") {
        const email = (prompt("Enter your email address for Cognito:") || "").trim();
        if (!email) return;
        if (!EMAIL_PATTERN.test(email)) {
          alert("Registration Error: Enter a valid email address, such as name@example.com.");
          return;
        }
        const password = prompt(
          "Choose a password:\n(8+ characters with an uppercase letter, a lowercase letter, a number, and a symbol)"
        );
        if (!password) return;
        const problems = cognitoPasswordProblems(password);
        if (problems.length) {
          alert(`Registration Error: Your password needs \${problems.join(", ")}.`);
          return;
        }

        let codePrompt;
        try {
          const registration = await postAuthRequest(
            "/auth/cognito/register",
            { email, password },
            "Cognito registration failed"
          );
          codePrompt = `\${registration.message}\nEnter the confirmation code from your email:`;
        } catch (err) {
          if (err.status !== 409) throw err;
          // The email is already registered, possibly never confirmed.
          codePrompt =
            "An account with this email already exists.\n" +
            "If you never confirmed it, enter the code from your email now.\n" +
            "Otherwise press Cancel and use Log in:";
        }

        errorStage = "Confirmation";
        const confirmed = await confirmCognitoAccount(email, codePrompt);
        if (!confirmed) {
          alert("Your account is not confirmed yet. Confirm the email code before signing in with Cognito.");
          return;
        }
        errorStage = "Sign-in";
        const tokenData = await postAuthRequest(
          "/auth/cognito/login",
          { email, password },
          "Cognito sign-in failed"
        );
        saveAuthSession(tokenData, email);
        alert(`Welcome to your digital library, \${email}! Your Cognito account is ready.`);
        return;
      }

      if (provider.trim() !== "1") {
        alert("Choose 1 for a local account or 2 for Amazon Cognito.");
        return;
      }

      const username = prompt("Choose a username (3-30 chars):");
      if (!username) return;
      const email = prompt("Enter your email address:");
      if (!email) return;
      const password = prompt("Choose a password (min 8 chars):");
      if (!password) return;

      const data = await postAuthRequest(
        "/auth/register",
        { username, email, password },
        "Registration failed"
      );
      saveAuthSession(data, data.user.username);
      alert(`Welcome to your digital library, \${currentUsername}! Account created successfully.`);
    } catch (err) {
      alert(`\${errorStage} Error: \${describeError(err)}`);
    }
  });
}

loginBtn.addEventListener("click", async () => {
  if (currentAuthToken) {
    clearAuthSession();
    if (resultsSection) resultsSection.hidden = true;
    if (collectionView) collectionView.hidden = true;
  } else {
    const provider = prompt("Sign in with 1) Local account or 2) Amazon Cognito? Enter 1 or 2:");
    if (!provider) return;
    if (provider.trim() !== "1" && provider.trim() !== "2") {
      alert("Choose 1 for a local account or 2 for Amazon Cognito.");
      return;
    }

    const isCognito = provider.trim() === "2";
    const usernameOrEmail = prompt(isCognito
      ? "Enter your Cognito email address:"
      : "Enter your username or email:");
    if (!usernameOrEmail) return;
    const password = prompt("Enter your password:");
    if (!password) return;

    loginLabel.textContent = "Connecting...";
    try {
      const data = isCognito
        ? await postAuthRequest(
          "/auth/cognito/login",
          { email: usernameOrEmail, password },
          "Cognito sign-in failed"
        )
        : await postAuthRequest(
          "/auth/login",
          { username: usernameOrEmail, password },
          "Login failed"
        );
      saveAuthSession(data, isCognito ? usernameOrEmail : data.user.username);
    } catch (err) {
      let message = describeError(err);
      if (isCognito && err && err.status === 401) {
        message += "\n\nIf you just registered, make sure you confirmed the emailed code first.";
      }
      alert(`Login Failed: \${message}`);
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
    headers["Authorization"] = `Bearer \${currentAuthToken}`; 
  }

  const res = await fetch(`\${API_BASE_URL}\${path}`, { headers: headers });
  if (!res.ok) {
    throw apiError(res, await readJson(res), "The library request failed");
  }
  return res.json();
}

async function submitEntry(path, payload) {
  const headers = { "Content-Type": "application/json" };
  if (currentAuthToken) { headers["Authorization"] = `Bearer \${currentAuthToken}`; }

  const res = await fetch(`\${API_BASE_URL}\${path}`, {
    method: "POST",
    headers: headers,
    body: JSON.stringify(payload),
  });
  
  const data = await readJson(res);
  if (!res.ok) {
    throw apiError(res, data, "Could not add the entry");
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
    addModalStatus.textContent = describeError(error);
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
    addModalStatus.textContent = describeError(error);
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
          const data = await fetchJSON(`/books/search?title=\${encodeURIComponent(query)}`);
          renderResults(`Search results for "\${query}"`, data.books.map(b => {
            const statusStr = b.read_status ? ` [\${b.read_status}]` : "";
            const ratingStr = b.rating ? ` (\${b.rating}★)` : "";
            return `\${b.book_title}\${statusStr}\${ratingStr}`;
          }));
        } catch (err) { handleRouteError(err); }
      } 
      else if (action === "edit") {
        const bookTitle = prompt("Enter the exact Book Title you want to update:");
        const newDesc = prompt("Enter the new description:");
        if (!bookTitle || !newDesc) return;
        try {
          const headers = { "Content-Type": "application/json" };
          if (currentAuthToken) headers["Authorization"] = `Bearer \${currentAuthToken}`;
          const res = await fetch(`\${API_BASE_URL}/books/description?book_title=\${encodeURIComponent(bookTitle)}`, {
            method: "PUT",
            headers: headers,
            body: JSON.stringify({ book_description: newDesc })
          });
          const data = await readJson(res);
          if (!res.ok) throw apiError(res, data, "Update failed");
          alert("Description updated successfully!");
          if (typeof routeHandlers["/books"] === "function") { await routeHandlers["/books"](); }
        } catch (err) { reportActionError(err); }
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
        const entryTitle = prompt(`Enter the exact \${titleLabel} Title you want to remove:`);
        if (!entryTitle) return;
        if (!confirm(`Are you sure you want to remove "\${entryTitle}" from your library?`)) return;
        try {
          const headers = {};
          if (currentAuthToken) headers["Authorization"] = `Bearer \${currentAuthToken}`;
          const resource = isBook ? "books" : "games";
          const titleParam = isBook ? "book_title" : "game_title";
          const res = await fetch(
            `\${API_BASE_URL}/lternate\${resource}?\${titleParam}=\${encodeURIComponent(entryTitle)}`,
            { method: "DELETE", headers: headers }
          );
          const data = await readJson(res);
          if (!res.ok) throw apiError(res, data, "Deletion failed");
          alert(`\${titleLabel} removed from your library.`);
          const route = isBook ? "/books" : "/games";
          if (typeof routeHandlers[route] === "function") { await routeHandlers[route](); }
        } catch (err) { reportActionError(err); }
      }
      else if (action === "progress") {
        const bookTitle = prompt("Enter the exact Book Title you want to log progress for:");
        if (!bookTitle) return;
        const statusChoice = prompt("Enter reading status (type 'read' or 'want to read'):");
        if (!statusChoice) return;
        let ratingChoice = null;
        if (statusChoice.trim().toLowerCase() === "read") {
          const ratingInput = prompt("Rate this book from 1 to 5 stars (Optional, leave blank if unrated):");
          if (ratingInput) {
            ratingChoice = parseInt(ratingInput, 10);
            if (!Number.isInteger(ratingChoice) || ratingChoice < 1 || ratingChoice > 5) {
              alert("Rating must be a whole number from 1 to 5.");
              return;
            }
          }
        }
        try {
          const headers = { "Content-Type": "application/json" };
          if (currentAuthToken) headers["Authorization"] = `Bearer \${currentAuthToken}`;
          const res = await fetch(`\${API_BASE_URL}/books/progress?book_title=\${encodeURIComponent(bookTitle)}`, {
            method: "PUT",
            headers: headers,
            body: JSON.stringify({ read_status: statusChoice, rating: ratingChoice })
          });
          const data = await readJson(res);
          if (!res.ok) throw apiError(res, data, "Progress update failed");
          alert(`Successfully logged "\${bookTitle}" as "\${statusChoice}" with a \${ratingChoice || 'no'} star rating!`);
          if (typeof routeHandlers["/books"] === "function") { await routeHandlers["/books"](); }
        } catch (err) { reportActionError(err); }
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

function renderLoginRequired() {
  if (!resultsTitle || !resultsList || !resultsSection) return;
  if (collectionView) collectionView.hidden = true;
  resultsTitle.textContent = "Log in to view your library";
  resultsList.replaceChildren();

  const message = document.createElement("li");
  message.textContent = "Your books and games are private to your account.";
  const loginItem = document.createElement("li");
  const button = document.createElement("button");
  button.type = "button";
  button.className = "login-btn";
  button.textContent = "Log in";
  button.addEventListener("click", () => loginBtn.click());
  loginItem.appendChild(button);
  resultsList.append(message, loginItem);
  resultsSection.hidden = false;
}

function renderError(message) {
  if (!resultsTitle || !resultsList || !resultsSection) return;
  if (collectionView) collectionView.hidden = true;
  resultsTitle.textContent = "Couldn't load that";
  resultsList.innerHTML = "";
  const li = document.createElement("li");
  li.textContent = message;
  resultsList.appendChild(li);
  resultsSection.hidden = false;
}

const routeHandlers = {
  "/books": async () => {
    const data = await fetchJSON("/books");
    renderCollection("/books", "Your books", data.books.map((b) => {
      const status = b.read_status ? ` [\${b.read_status}]` : "";
      const rating = b.rating ? ` (\${b.rating}★)` : "";
      return `\${b.book_title}\${status}\${rating}`;
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
        const statusStr = b.read_status ? ` [\${b.read_status}]` : "";
        const ratingStr = b.rating ? ` (\${b.rating}★)` : "";
        return `\${b.book_title}\${statusStr}\${ratingStr} (book)`;
      }),
      ...games.games.map((g) => `\${g.game_title} (game)`),
    ];
    renderResults("Everything in your library", rows);
  },
};

async function loadRoute(route) {
  const handler = routeHandlers[route];
  if (!handler) return;

  if (!currentAuthToken) {
    renderLoginRequired();
    return;
  }

  try {
    await handler();
  } catch (error) {
    console.error(error);
    handleRouteError(error);
  }
}

// Show a login prompt for expired sessions, otherwise a readable error.
function handleRouteError(error) {
  if (error instanceof Error && error.status === 401) {
    clearAuthSession();
    renderLoginRequired();
    return;
  }
  renderError(describeError(error, String(error)));
}

async function exportLibrary() {
  const [bookData, gameData] = await Promise.all([
    fetchJSON("/books"),
    fetchJSON("/games"),
  ]);

  const lines = [
    "Digital Library Export",
    `Exported: \${new Date().toLocaleString()}`,
    "",
    `BOOKS (\${bookData.books.length})`,
    "-----",
  ];

  const addField = (label, value) => {
    if (value !== null && value !== undefined && String(value).trim() !== "") {
      lines.push(`\${label}: \${value}`);
    }
  };

  if (bookData.books.length === 0) {
    lines.push("No books in this library.");
  } else {
    bookData.books.forEach((book, index) => {
      if (index > 0) lines.push("");
      lines.push(`Title: \${book.book_title}`);
      addField("ISBN", book.book_isbn);
      addField("Internal code", book.internal_code);
      addField("Published", book.publish_date);
      addField("Publisher", book.publisher);
      addField("Reading status", book.read_status);
      addField("Description", book.book_description);
      addField("Notes", book.book_summary);
    });
  }

  lines.push("", `GAMES (\${gameData.games.length})`, "-----");
  if (gameData.games.length === 0) {
    lines.push("No games in this library.");
  } else {
    gameData.games.forEach((game, index) => {
      if (index > 0) lines.push("");
      lines.push(`Title: \${game.game_title}`);
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
  link.download = `digital-library-\${new Date().toISOString().slice(0, 10)}.txt`;
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