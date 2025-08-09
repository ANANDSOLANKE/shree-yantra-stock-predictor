(function(){
  const $ = id => document.getElementById(id);
  const input = $('ticker'), go = $('go'), out = $('out');
  const box = $('suggestBox');

  let items = [];
  let activeIdx = -1;
  let lastQ = "";
  let timer = null;

  function showSuggest(show){ box.classList.toggle('hidden', !show || items.length === 0); }
  function clearSuggest(){ items = []; box.innerHTML = ""; activeIdx = -1; showSuggest(false); }

  function renderSuggest() {
    box.innerHTML = "";
    items.forEach((it, idx) => {
      const row = document.createElement('div');
      row.className = 'suggest-item' + (idx === activeIdx ? ' active' : '');
      row.setAttribute('role','option');
      row.innerHTML = `
        <div class="left">${it.symbol}</div>
        <div class="right">${(it.shortname || '').slice(0,60)} ${it.exchange ? ' · ' + it.exchange : ''}</div>
      `;
      row.addEventListener('mousedown', (e) => { e.preventDefault(); choose(idx); });
      box.appendChild(row);
    });
    showSuggest(true);
  }

  async function fetchSuggest(q){
    try{
      const res = await fetch('/suggest?q=' + encodeURIComponent(q));
      const data = await res.json();
      items = (data.results || []).slice(0,10);
      renderSuggest();
    }catch(e){
      clearSuggest();
    }
  }

  function debounce(fn, ms){
    return function(...args){
      clearTimeout(timer);
      timer = setTimeout(()=>fn.apply(this,args), ms);
    };
  }

  const onType = debounce(() => {
    const q = (input.value || '').trim();
    if (!q || q === lastQ) { if(!q) clearSuggest(); return; }
    lastQ = q;
    fetchSuggest(q);
  }, 200);

  function choose(idx){
    if (idx < 0 || idx >= items.length) return;
    const sym = items[idx].symbol;
    input.value = sym;
    clearSuggest();
    run();
  }

  function onKeyDown(e){
    if (box.classList.contains('hidden')) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); activeIdx = Math.min(items.length-1, activeIdx+1); renderSuggest(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); activeIdx = Math.max(0, activeIdx-1); renderSuggest(); }
    else if (e.key === 'Enter') { if (activeIdx >= 0) { e.preventDefault(); choose(activeIdx); } }
    else if (e.key === 'Escape') { clearSuggest(); }
  }

  async function run(){
    const q = (input.value||'').trim();
    if(!q){ alert('Enter a company or ticker'); return; }
    out.textContent = 'Loading...';
    try{
      const r = await fetch('/stock?q=' + encodeURIComponent(q));
      const d = await r.json();
      if(!r.ok) throw new Error(d.error || 'Request failed');

      const {ticker, open, high, low, close} = d;
      const o = open%9, h = high%9, l = low%9, c = close%9;
      const layer1=(o+c)%9, layer2=(h-l+9)%9, bindu=(layer1*layer2)%9;
      const up = bindu >= 5;
      out.textContent =
        `${ticker}\nOpen: ${open}\nHigh: ${high}\nLow: ${low}\nClose: ${close}\n` +
        `Signal: ${up ? '▲ Up (1)' : '▼ Down (0)'} (Bindu ${bindu})`;
    }catch(e){
      out.textContent = 'Error: ' + e.message;
    }
  }

  input.addEventListener('input', onType);
  input.addEventListener('keydown', onKeyDown);
  input.addEventListener('blur', () => setTimeout(clearSuggest, 120));
  go.addEventListener('click', run);
  input.addEventListener('keydown', e => { if(e.key==='Enter' && box.classList.contains('hidden')) run(); });
})();
