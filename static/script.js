(() => {
  "use strict";

  const toast = document.getElementById("toast");
  let toastTimer;

  function notify(message) {
    if (!toast) {
      console.info(message);
      return;
    }

    toast.textContent = message;
    toast.classList.add("show");
    clearTimeout(toastTimer);

    toastTimer = setTimeout(() => {
      toast.classList.remove("show");
    }, 2400);
  }

  const heroForm = document.getElementById("heroSearch");
  const navForm = document.getElementById("navSearch");
  const heroInput = document.getElementById("heroSearchInput");
  const navInput = document.getElementById("navSearchInput");
  const grid = document.getElementById("recommendationGrid");
  const emptyState = document.getElementById("emptyState");
  const resultsSection = document.getElementById("recommendations");
  const menuToggle = document.getElementById("menuToggle");
  const navLinks = document.getElementById("navLinks");

  async function fetchJSON(url) {
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`Request failed: ${response.status}`);
    }

    return response.json();
  }

  function scrollToResults() {
    resultsSection?.scrollIntoView({
      behavior: "smooth",
      block: "start"
    });
  }

  function createBookCard(book) {
    const card = document.createElement("article");
    card.className = "book-card";

    const heart = document.createElement("button");
    heart.className = "heart";
    heart.type = "button";
    heart.textContent = "♡";
    heart.setAttribute("aria-label", "Add to favorites");
    heart.setAttribute("aria-pressed", "false");

    const image = document.createElement("img");
    image.loading = "lazy";
    image.alt = `${book.title || "Book"} cover`;

    if (book.cover) {
      image.src = book.cover;
    } else {
      image.classList.add("cover-missing");
    }

    image.addEventListener("error", () => {
      image.removeAttribute("src");
      image.alt = "Book cover unavailable";
      image.classList.add("cover-missing");
    });

    const info = document.createElement("div");
    info.className = "book-info";

    const title = document.createElement("strong");
    title.textContent = book.title || "Untitled";

    const author = document.createElement("small");
    author.textContent = book.author || "Unknown author";

    const meta = document.createElement("div");
    meta.className = "book-meta";

    const rating = document.createElement("span");
    rating.className = "rating";

    const score = Number(book.rating);
    rating.textContent =
      `★ ${Number.isFinite(score) ? score.toFixed(1) : "—"}`;

    const view = document.createElement("button");
    view.className = "view-button";
    view.type = "button";
    view.textContent = "Similar books";
    view.dataset.title = book.title || "";

    meta.append(rating, view);
    info.append(title, author, meta);
    card.append(heart, image, info);

    return card;
  }

  function renderBooks(data, heading) {
    if (!grid || !emptyState) {
      notify("Could not find the results section in index.html.");
      return;
    }

    const books = Array.isArray(data)
      ? data
      : (Array.isArray(data?.results) ? data.results : []);

    grid.replaceChildren();

    const headingElement = document.querySelector(
      "#recommendations .section-heading h2"
    );

    if (headingElement && heading) {
      headingElement.textContent = heading;
    }

    emptyState.hidden = books.length > 0;

    if (books.length === 0) {
      emptyState.textContent =
        "No books found. Try another search.";
      return;
    }

    const fragment = document.createDocumentFragment();

    books.forEach(book => {
      fragment.appendChild(createBookCard(book));
    });

    grid.appendChild(fragment);
    notify(`${books.length} book(s) found.`);
  }

  async function submitSearch(query) {
    const q = (query || "").trim();

    if (!q) {
      notify("Enter a book title or author.");
      return;
    }

    scrollToResults();

    try {
      const results = await fetchJSON(
        `/api/search?q=${encodeURIComponent(q)}`
      );

      renderBooks(results, `Search results for "${q}"`);
    } catch (error) {
      console.error("Search error:", error);
      notify("Search failed. Check that Flask is running.");
    }
  }

  async function loadRecommendations(title) {
    const bookTitle = (title || "").trim();

    if (!bookTitle) {
      notify("Select a book first.");
      return;
    }

    scrollToResults();

    try {
      const response = await fetchJSON(
        `/api/recommend?title=${encodeURIComponent(bookTitle)}`
      );

      const books = Array.isArray(response)
        ? response
        : (response.results || []);

      renderBooks(
        books,
        `Books similar to "${bookTitle}"`
      );

      if (books.length === 0) {
        notify(
          response.message ||
          "No recommendations found for this book."
        );
      }
    } catch (error) {
      console.error("Recommendation error:", error);
      notify("Could not load recommendations.");
    }
  }

  heroForm?.addEventListener("submit", event => {
    event.preventDefault();

    if (navInput) {
      navInput.value = heroInput?.value || "";
    }

    submitSearch(heroInput?.value);
  });

  navForm?.addEventListener("submit", event => {
    event.preventDefault();

    if (heroInput) {
      heroInput.value = navInput?.value || "";
    }

    submitSearch(navInput?.value);
  });

  // Genre buttons: search the catalogue text.
  document.querySelectorAll("[data-genre]").forEach(button => {
    button.addEventListener("click", () => {
      const genre = button.dataset.genre || "";

      if (heroInput) heroInput.value = genre;
      if (navInput) navInput.value = genre;

      submitSearch(genre);
    });
  });

  // Works for both original and dynamically generated cards.
  document.addEventListener("click", event => {
    const heart = event.target.closest(".heart");

    if (heart) {
      heart.classList.toggle("saved");

      const saved = heart.classList.contains("saved");
      heart.textContent = saved ? "♥" : "♡";
      heart.setAttribute("aria-pressed", String(saved));

      notify(
        saved
          ? "Added to favorites for this session."
          : "Removed from favorites."
      );

      return;
    }

    const viewButton = event.target.closest(".view-button");

    if (viewButton) {
      const title =
        viewButton.dataset.title ||
        viewButton.closest(".book-card")
          ?.querySelector(".book-info strong")
          ?.textContent?.trim();

      loadRecommendations(title);
    }
  });

  menuToggle?.addEventListener("click", () => {
    const isOpen = navLinks?.classList.toggle("open") || false;

    menuToggle.setAttribute(
      "aria-expanded",
      String(isOpen)
    );
  });

  // Set up the existing server-rendered cards.
  document.querySelectorAll(
    "#recommendationGrid .book-card"
  ).forEach(card => {
    const button = card.querySelector(".view-button");

    if (button) {
      button.dataset.title ||= card.querySelector(
        ".book-info strong"
      )?.textContent?.trim() || "";
    }

    card.querySelector(".heart")
      ?.setAttribute("aria-pressed", "false");
  });
})();

/* FIX: Navigation links and section buttons */

document.addEventListener("DOMContentLoaded", () => {
  const sectionLinks = document.querySelectorAll(
    'a[href^="#"]'
  );

  sectionLinks.forEach(link => {
    link.addEventListener("click", event => {
      const href = link.getAttribute("href");

      if (!href || href === "#") return;

      const target = document.querySelector(href);

      if (!target) {
        console.warn("Navigation target not found:", href);
        return;
      }

      event.preventDefault();

      target.scrollIntoView({
        behavior: "smooth",
        block: "start"
      });

      // Update the URL fragment.
      history.replaceState(null, "", href);

      // Close the mobile navigation after selecting a link.
      const navLinks = document.getElementById("navLinks");
      const menuToggle = document.getElementById("menuToggle");

      if (navLinks && navLinks.classList.contains("open")) {
        navLinks.classList.remove("open");
        menuToggle?.setAttribute("aria-expanded", "false");
      }
    });
  });

  // Make sure every expected destination exists.
  [
    "home",
    "explore",
    "genres",
    "recommendations",
    "about"
  ].forEach(id => {
    if (!document.getElementById(id)) {
      console.error("Missing section ID:", id);
    }
  });
});
