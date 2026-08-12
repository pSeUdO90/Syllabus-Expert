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
  root() {
    const parts = location.pathname.split("/").filter(Boolean);
    const last = parts[parts.length - 1] || "";
    const pages = new Set([
      "library", "library.html", "upload", "upload.html",
      "review", "review.html", "practice", "practice.html", "index.html",
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
    const res = await fetch(this.url(path));
    const payload = await res.json();
    if (!res.ok) throw new Error(payload.error || res.statusText);
    return payload;
  },
};
