(function () {
  const path = location.pathname.replace(/\/index\.html$/, "/") || "/";
  document.querySelectorAll(".site-nav nav a[href]").forEach((a) => {
    const href = a.getAttribute("href");
    const normalized = href === "/" ? "/" : href.replace(/\.html$/, "");
    const current = path === "/" ? "/" : path.replace(/\.html$/, "");
    if (normalized === current) a.classList.add("active");
  });
})();

window.SE = {
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
  async getJson(url) {
    const res = await fetch(url);
    const payload = await res.json();
    if (!res.ok) throw new Error(payload.error || res.statusText);
    return payload;
  },
};
