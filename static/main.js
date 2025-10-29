// ------------------ shared tiny helpers ------------------
function humanMB(n) { return `${Math.round(n / (1024*1024))}MB`; }
function humanGB(n) { return `${Math.round(n / (1024*1024*1024))}GB`; }
function clamp01(v) { return Math.max(0, Math.min(1, v)); }
const hasNum = (v) => typeof v === "number" && Number.isFinite(v);
const hasObj = (v) => v && typeof v === "object";

// ------------------ click-to-confirm + Esc closes modals ------------------
document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-confirm]");
  if (!t) return;
  const msg = t.getAttribute("data-confirm") || "Are you sure?";
  if (!confirm(msg)) e.preventDefault();
});

document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  document.querySelectorAll(".modal.open").forEach((modal) => {
    const closer = modal.querySelector("[data-close]") || modal.querySelector(".modal-backdrop");
    if (closer) closer.click();
  });
});

// ------------------ System monitor (poll-only; no sockets) ------------------
(function systemCardMount() {
  const card = document.querySelector("[data-sys-card]");
  if (!card || card.dataset.mounted === "1") return;
  card.dataset.mounted = "1";

  // Build skeleton once
  card.innerHTML = `
    <h3 class="sysmon-title">System</h3>
    <div class="meters">
      <div class="meter" data-meter="cpu">
        <div class="meter-label">CPU</div>
        <div class="progress"><div class="fill" style="width:0%"></div></div>
        <div class="meter-text" data-cpu>—</div>
      </div>
      <div class="meter" data-meter="ram">
        <div class="meter-label">RAM</div>
        <div class="progress"><div class="fill" style="width:0%"></div></div>
        <div class="meter-text" data-ram>—</div>
      </div>
      <div class="meter" data-meter="disk">
        <div class="meter-label">Disk</div>
        <div class="progress"><div class="fill" style="width:0%"></div></div>
        <div class="meter-text" data-disk>—</div>
      </div>
    </div>
  `;

  const el = {
    cpuText:  card.querySelector("[data-cpu]"),
    ramText:  card.querySelector("[data-ram]"),
    diskText: card.querySelector("[data-disk]"),
    cpuFill:  card.querySelector('[data-meter="cpu"] .fill'),
    ramFill:  card.querySelector('[data-meter="ram"] .fill'),
    diskFill: card.querySelector('[data-meter="disk"] .fill'),
    ramRow:   card.querySelector('[data-meter="ram"]'),
    diskRow:  card.querySelector('[data-meter="disk"]'),
  };

  function render(mon) {
    const hasAny = (mon && (
      hasNum(mon.cpu) ||
      (hasObj(mon.ram)  && hasNum(mon.ram.total)) ||
      (hasObj(mon.disk) && hasNum(mon.disk.total))
    ));
    card.style.display = hasAny ? "" : "none";
    if (!hasAny) return;

    // CPU
    if (hasNum(mon.cpu)) {
      const p = clamp01(mon.cpu / 100);
      el.cpuFill.style.width = `${Math.round(p * 100)}%`;
      el.cpuText.textContent = `${Math.round(mon.cpu)}%`;
    } else {
      el.cpuFill.style.width = "0%";
      el.cpuText.textContent = "—";
    }

    // RAM
    if (hasObj(mon.ram) && hasNum(mon.ram.total) && hasNum(mon.ram.used)) {
      const p = clamp01(mon.ram.used / mon.ram.total);
      el.ramFill.style.width = `${Math.round(p * 100)}%`;
      el.ramText.textContent = `${humanMB(mon.ram.used)}/${humanMB(mon.ram.total)}`;
      el.ramRow.style.display = "";
    } else {
      el.ramRow.style.display = "none";
    }

    // Disk
    if (hasObj(mon.disk) && hasNum(mon.disk.total) && hasNum(mon.disk.used)) {
      const p = clamp01(mon.disk.used / mon.disk.total);
      el.diskFill.style.width = `${Math.round(p * 100)}%`;
      el.diskText.textContent = `${humanGB(mon.disk.used)}/${humanGB(mon.disk.total)}`;
      el.diskRow.style.display = "";
    } else {
      el.diskRow.style.display = "none";
    }
  }

  async function pollOnce() {
    try {
      const r = await fetch("/api/sys", { cache: "no-store" });
      if (!r.ok) { card.style.display = "none"; return; }
      render(await r.json());
    } catch {
      card.style.display = "none";
    }
  }

  pollOnce();
  const t = setInterval(pollOnce, 5000);
  window.addEventListener("beforeunload", () => clearInterval(t));
})();
