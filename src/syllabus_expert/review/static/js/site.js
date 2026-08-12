(function () {
  const file = (location.pathname.split("/").pop() || "index.html").replace(/\/$/, "") || "index.html";
  const current = file.replace(/\.html$/, "") || "index";
  document.querySelectorAll(".site-nav nav a[href]").forEach((a) => {
    const href = (a.getAttribute("href") || "").split("?")[0];
    const key = href.replace(/^.*\//, "").replace(/\.html$/, "") || "index";
    if (key === current || ((current === "index" || current === "") && key === "index")) {
      a.classList.add("active");
    }
  });
})();

window.SE = {
  me: null,
  root() {
    const parts = location.pathname.split("/").filter(Boolean);
    const last = parts[parts.length - 1] || "";
    const pages = new Set([
      "library", "library.html", "upload", "upload.html",
      "review", "review.html", "practice", "practice.html",
      "admin", "admin.html", "login", "login.html", "index.html",
    ]);
    if (pages.has(last) || last === "") parts.pop();
    return parts.length ? "/" + parts.join("/") : "";
  },
  url(path) {
    if (!path.startsWith("/")) path = "/" + path;
    return this.root() + path;
  },
  page(name, query) {
    const suffix = query ? (query.startsWith("?") ? query : "?" + query) : "";
    return name + suffix;
  },
  isLoginPage() {
    const file = (location.pathname.split("/").pop() || "").replace(/\.html$/, "");
    return file === "login" || location.pathname.endsWith("/login");
  },
  esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[ch]));
  },
  toast(msg) {
    let el = document.getElementById("toast");
    if (!el) {
      el = document.createElement("div");
      el.id = "toast";
      el.className = "toast";
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.style.display = "block";
    setTimeout(() => { el.style.display = "none"; }, 2400);
  },
  typesetMath(root) {
    if (!window.renderMathInElement || !root) return;
    window.renderMathInElement(root, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "$", right: "$", display: false },
        { left: "\\[", right: "\\]", display: true },
        { left: "\\(", right: "\\)", display: false },
      ],
      throwOnError: false,
      ignoredTags: ["script", "noscript", "style", "textarea", "pre", "code"],
    });
  },
  async getJson(path) {
    const res = await fetch(this.url(path), { credentials: "same-origin" });
    const payload = await res.json();
    if (!res.ok) throw new Error(payload.error || res.statusText);
    return payload;
  },
  async postJson(path, body) {
    const res = await fetch(this.url(path), {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    const payload = await res.json();
    if (!res.ok) throw new Error(payload.error || res.statusText);
    return payload;
  },
  decorateNav() {
    const header = document.querySelector(".site-nav");
    const nav = header && header.querySelector("nav");
    if (!header || !nav || !this.me) return;
    if ((this.me.role === "admin" || this.me.role === "teacher") && !nav.querySelector('[href="admin.html"]')) {
      nav.insertAdjacentHTML("beforeend", '<a href="admin.html">Admin</a>');
    }
    if (!header.querySelector(".account")) {
      header.insertAdjacentHTML(
        "beforeend",
        `<div class="account"><span id="whoami"></span><button class="ghost" type="button" id="logout-btn">Log out</button></div>`
      );
      header.querySelector("#logout-btn").onclick = async () => {
        await fetch(SE.url("/api/logout"), { method: "POST", credentials: "same-origin" });
        location.href = "login.html";
      };
    }
    const who = header.querySelector("#whoami");
    if (who) who.textContent = `${this.me.display_name || this.me.username} (${this.me.role})`;
  },
  async requireAuth() {
    if (this.isLoginPage()) return null;
    try {
      this.me = await this.getJson("/api/me");
      this.decorateNav();
      return this.me;
    } catch {
      location.href = "login.html";
      return null;
    }
  },
};

window.SE.requireAuth();
