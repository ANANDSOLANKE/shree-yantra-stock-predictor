(function(){
  const $ = id => document.getElementById(id);
  const input = $('ticker'), go = $('go');
  const box = $('suggestBox');
  const card = $('card');
  const setText = (id,val)=>{ $(id).textContent = val };

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
        <div class="right">${(it.shortname || '').slice(0,70)} ${it.exchange ? ' · ' + it.exchange : ''}</div>
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
    }catch(e){ clearSuggest(); }
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

  function setSignal(up, bindu){
    const chip = $('cSignal');
    chip.className = 'chip ' + (up ? 'up' : 'down');
    chip.textContent = (up ? '▲ Bullish' : '▼ Bearish') + ` • Bindu ${bindu}`;
    const note = $('predNote');
    note.textContent = 'Prediction For Next Day: ' + (up ? '▲ Price Up (1)' : '▼ Price Down (0)');
  }

  async function run(){
    const q = (input.value||'').trim();
    if(!q){ alert('Enter a company or ticker'); return; }

    card.classList.remove('hidden');
    setText('cTicker', 'Fetching… ' + q.toUpperCase());
    setText('cOpen','—'); setText('cHigh','—'); setText('cLow','—'); setText('cClose','—');
    $('cSignal').className = 'chip'; $('cSignal').textContent = 'Loading…';
    $('predNote').textContent = 'Prediction For Next Day: …';

    try{
      const r = await fetch('/stock?q=' + encodeURIComponent(q));
      const d = await r.json();
      if(!r.ok) throw new Error(d.error || 'Request failed');

      const {ticker, open, high, low, close} = d;
      setText('cTicker', ticker);
      setText('cOpen', open.toFixed(2));
      setText('cHigh', high.toFixed(2));
      setText('cLow', low.toFixed(2));
      setText('cClose', close.toFixed(2));

      const o=open%9, h=high%9, l=low%9, c=close%9;
      const layer1=(o+c)%9, layer2=(h-l+9)%9, bindu=(layer1*layer2)%9;
      const up = bindu >= 5;
      setSignal(up, bindu);
    }catch(e){
      setText('cTicker', 'Error');
      const chip = $('cSignal'); chip.className='chip down'; chip.textContent='Failed to fetch';
      $('predNote').textContent = 'Prediction For Next Day: —';
      console.error(e);
    }
  }

  async function loadTrending(){
    try{
      const r = await fetch('/trending?region=IN');
      const d = await r.json();
      const ul = $('trendList');
      ul.innerHTML = '';
      const list = (d.results||[]).slice(0,10);
      if(!list.length){ ul.innerHTML = '<li>No data</li>'; return; }
      list.forEach(item=>{
        const li = document.createElement('li');
        li.innerHTML = `<span>${item.symbol}</span><span class="right">${(item.shortname||'').slice(0,42)}</span>`;
        li.addEventListener('click', ()=>{ input.value = item.symbol; run(); });
        ul.appendChild(li);
      });
    }catch(e){
      const ul = $('trendList');
      ul.innerHTML = '<li>Failed to load</li>';
    }
  }

  input.addEventListener('input', onType);
  input.addEventListener('keydown', onKeyDown);
  input.addEventListener('blur', () => setTimeout(clearSuggest, 120));
  go.addEventListener('click', run);
  input.addEventListener('keydown', e => { if(e.key==='Enter' && box.classList.contains('hidden')) run(); });

  loadTrending();
})();