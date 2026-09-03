(() => {
  const root = document.documentElement;
  const sizeKey = "bloodline:reader-size";
  const themeKey = "bloodline:reader-theme";
  const savedSize = Number(localStorage.getItem(sizeKey) || 19);
  root.style.setProperty("--reader-size", `${Math.min(24, Math.max(16, savedSize))}px`);

  document.querySelector("[data-size-down]")?.addEventListener("click", () => adjustSize(-1));
  document.querySelector("[data-size-up]")?.addEventListener("click", () => adjustSize(1));
  document.querySelector("[data-theme]")?.addEventListener("click", () => {
    const light = document.body.classList.toggle("light-reader");
    localStorage.setItem(themeKey, light ? "light" : "dark");
    document.body.style.background = light ? "#eee4d2" : "#171312";
    document.body.style.color = light ? "#251d1a" : "#f3eadc";
  });
  if (localStorage.getItem(themeKey) === "light") document.querySelector("[data-theme]")?.click();

  function adjustSize(delta) {
    const current = parseInt(getComputedStyle(root).getPropertyValue("--reader-size"), 10);
    const next = Math.min(24, Math.max(16, current + delta));
    root.style.setProperty("--reader-size", `${next}px`);
    localStorage.setItem(sizeKey, String(next));
  }
})();
