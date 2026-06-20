/**
 * Unified top navigation — injected on every page for consistent UX
 */
(function () {
  const PAGE = window.GRIDLOCK_PAGE || "command";

  const TABS = [
    { id: "command", label: "Command", href: "/" },
    { id: "map", label: "Live Map", href: "/map" },
    { id: "scenarios", label: "Scenarios", href: "/scenarios" },
    { id: "hotspots", label: "Hotspots", href: "/hotspots" },
    { id: "analytics", label: "Analytics", href: "/analytics" },
    { id: "learning", label: "Learning Loop", href: "/learning" },
  ];

  document.body.classList.add("gl-shell");

  // Remove duplicate top headers from Stitch (keep our unified one)
  document.querySelectorAll("body > header, body > nav.fixed").forEach((el) => {
    if (el.id !== "gl-unified-nav") el.remove();
  });

  const navLinks = TABS.map(
    (t) =>
      `<a href="${t.href}" class="gl-nav-link font-label-md text-label-md text-sm whitespace-nowrap ${t.id === PAGE ? "gl-nav-active" : ""}">${t.label}</a>`
  ).join("");

  const nav = document.createElement("header");
  nav.id = "gl-unified-nav";
  nav.className =
    "fixed top-0 left-0 right-0 z-[200] h-16 flex items-center justify-between px-5 bg-[#10131a]/95 backdrop-blur-lg border-b border-white/10";
  nav.innerHTML = `
    <div class="flex items-center gap-8 min-w-0">
      <a href="/" class="font-bold text-lg text-[#adc6ff] shrink-0">Gridlock</a>
      <nav class="flex items-center gap-4 overflow-x-auto max-w-[70vw]">${navLinks}</nav>
    </div>
    <div class="flex items-center gap-3 shrink-0">
      <span class="hidden sm:inline text-xs text-[#8c909f]">Bengaluru Ops</span>
      <span class="w-2 h-2 rounded-full bg-[#00C851] animate-pulse" title="Live"></span>
    </div>
  `;

  document.body.prepend(nav);

  // Mobile nav row
  const mobileNav = document.createElement("nav");
  mobileNav.id = "gl-mobile-nav";
  mobileNav.className =
    "md:hidden fixed top-16 left-0 right-0 z-[199] flex gap-4 overflow-x-auto px-4 py-2 bg-[#10131a]/95 border-b border-white/10";
  mobileNav.innerHTML = navLinks;
  document.body.insertBefore(mobileNav, nav.nextSibling);
})();
