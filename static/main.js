document.addEventListener('click', (e) => {
  const t = e.target.closest('[data-confirm]');
  if (!t) return;
  const msg = t.getAttribute('data-confirm') || 'Are you sure?';
  if (!confirm(msg)) e.preventDefault();
});

document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape') return;
  document.querySelectorAll('.modal.open').forEach(modal => {
    const closer = modal.querySelector('[data-close]') || modal.querySelector('.modal-backdrop');
    if (closer) closer.click();
  });
});

/* ---------- System monitor (in sidebar device-info card) ---------- */
{
  const deviceCard = document.querySelector('.device-info.card');
  if (!deviceCard) {
    // This page doesn't have the device-info card; do nothing.
  } else if (deviceCard.querySelector('.sysmon')) {
    // Already mounted on this page; don't mount twice.
  } else {
    const sysRoot = document.createElement('div');
    sysRoot.className = 'sysmon';
    sysRoot.innerHTML = `
      <h4 class="sysmon-title">System</h4>
      <div class="meters">
        <div class="meter">
          <div class="meter-label">CPU</div>
          <div class="progress"><div class="fill" id="cpuFill" style="width:0%"></div></div>
          <div class="meter-text" id="cpuTxt">--%</div>
        </div>
        <div class="meter">
          <div class="meter-label">RAM</div>
          <div class="progress"><div class="fill" id="ramFill" style="width:0%"></div></div>
          <div class="meter-text" id="ramTxt">--/--</div>
        </div>
        <div class="meter">
          <div class="meter-label">Disk</div>
          <div class="progress"><div class="fill" id="diskFill" style="width:0%"></div></div>
          <div class="meter-text" id="diskTxt">--/--</div>
        </div>
        <div class="meter temp">
          <div class="meter-label">Temp</div>
          <div class="meter-text" id="tempTxt">-- °C</div>
        </div>
      </div>`;
    deviceCard.appendChild(sysRoot);

    // element refs (scoped to sysRoot so we don't leak globals)
    const cpuFill = sysRoot.querySelector('#cpuFill');
    const ramFill = sysRoot.querySelector('#ramFill');
    const diskFill = sysRoot.querySelector('#diskFill');
    const cpuTxt  = sysRoot.querySelector('#cpuTxt');
    const ramTxt  = sysRoot.querySelector('#ramTxt');
    const diskTxt = sysRoot.querySelector('#diskTxt');
    const tempTxt = sysRoot.querySelector('#tempTxt');

    const MB = 1024 * 1024;
    const fmtMB = n => `${Math.round(n / MB)}MB`;

    function renderSys(mon){
      const cpu = Math.max(0, Math.min(100, mon.cpu || 0));
      const rUsed = mon.ram?.used || 0, rTot = mon.ram?.total || 1;
      const dUsed = mon.disk?.used || 0, dTot = mon.disk?.total || 1;
      const rPct = Math.round((rUsed/rTot)*100);
      const dPct = Math.round((dUsed/dTot)*100);

      cpuFill.style.width = cpu + '%';
      cpuTxt.textContent = cpu.toFixed(0) + '%';

      ramFill.style.width = rPct + '%';
      ramTxt.textContent = `${fmtMB(rUsed)}/${fmtMB(rTot)}`;

      diskFill.style.width = dPct + '%';
      diskTxt.textContent = `${fmtMB(dUsed)}/${fmtMB(dTot)}`;

      tempTxt.textContent = (mon.temp_c != null) ? `${mon.temp_c.toFixed(1)} °C` : '-- °C';
    }

    // Dev-PC fallback (mock values)
    let mock = { cpu: 12, ram: {used: 220*MB, total: 512*MB}, disk: {used: 3.2*1024*MB, total: 8*1024*MB}, temp_c: 41.3 };
    const clamp = (v,min,max)=>Math.max(min,Math.min(max,v));
    function jiggleMock(){
      mock.cpu = clamp(mock.cpu + (Math.random()*10-5), 2, 95);
      mock.ram.used = clamp(mock.ram.used + (Math.random()*15-7)*MB, 150*MB, mock.ram.total*0.95);
      mock.disk.used = clamp(mock.disk.used + (Math.random()*30-15)*MB, 0.1*mock.disk.total, 0.95*mock.disk.total);
      mock.temp_c = clamp(mock.temp_c + (Math.random()*1.6-0.8), 35, 75);
      return {...mock, ram:{...mock.ram}, disk:{...mock.disk}};
    }

    async function pollSys(){
      try{
        const r = await fetch('/api/sys');
        if(!r.ok) throw new Error(String(r.status));
        const data = await r.json();
        renderSys(data);
      }catch{
        renderSys(jiggleMock()); // dev PC fallback
      }
    }
    pollSys();
    setInterval(pollSys, 3000);
  }
}
