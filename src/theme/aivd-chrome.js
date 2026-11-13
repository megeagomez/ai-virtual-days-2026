/* AI Virtual Days 2026 · inyecta el "chrome" fijo de la plantilla en cada .slide.
   Cargar ANTES de presentation.js. Atributos opcionales por diapositiva:
   data-chrome="none"                 → no inyectar nada (imágenes oficiales completas)
   data-panel="right|diag|diag-soft|none"   (por defecto right)
   data-dots="false"                  → sin rejilla de puntos arriba a la derecha
   data-accent-bars="true"            → barras de color verticales a la derecha (layouts de contenido)
   data-footer="brand|hub|none"       → "AI//VD · 26" + cuadraditos | "MICROSOFT SPEAKERS HUB…" + barra arcoíris
   data-badge="false"                 → sin insignia AI VD abajo a la derecha
   data-status="texto"                → sustituye la línea mode: copilot · latency…
   data-prompt="texto"                → sustituye msh://ai-virtual-days-2026:~$
   data-kicker="TEXTO" data-kicker-color="orange|yellow|green|blue|cyan" data-kicker-mono="true" */
(() => {
  'use strict';
  const DEFAULT_STATUS = 'mode: copilot  ·  latency: 0.8s  ·  tokens: 1.2k  ·  uptime: 99.9%';
  const DEFAULT_PROMPT = 'msh://ai-virtual-days-2026:~$';
  const el = (cls, html = '') => { const d = document.createElement('div'); d.className = cls; d.innerHTML = html; return d; };
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  document.querySelectorAll('.slide').forEach(slide => {
    const ds = slide.dataset;
    if (ds.chrome === 'none') return;
    const c = el('aivd-chrome'); c.setAttribute('aria-hidden', 'true');
    const panel = ds.panel || 'right';
    if (panel === 'right') c.append(el('panel-right'));
    if (panel === 'diag') c.append(el('panel-diag'));
    if (panel === 'diag-soft') c.append(el('panel-diag soft'));
    if (ds.dots !== 'false' && panel === 'right') c.append(el('dot-grid'));
    c.append(el('term-dots', '<i></i><i></i><i></i><i></i>'));
    c.append(el('term-prompt', esc(ds.prompt || DEFAULT_PROMPT)));
    const cursor = el('term-cursor');
    if (ds.prompt) cursor.style.left = `calc(10.52cqw + ${(ds.prompt.length + 2) * 0.745}cqw)`;
    c.append(cursor, el('rainbow'));
    c.append(el('line-nums', ['01', '02', '03', '04', '05', '06', '07', '08'].map(n => `<span>${n}</span>`).join('')));
    c.append(el('hub-logo'));
    if (ds.accentBars === 'true') c.append(el('accent-bars', '<i></i><i></i><i></i><i></i>'));
    if (ds.badge !== 'false') c.append(el('aivd-badge'));
    c.append(el('status-line', esc(ds.status || DEFAULT_STATUS)));
    const footer = ds.footer || 'brand';
    if (footer === 'brand') c.append(el('foot-brand', 'AI//VD · 26'), el('foot-squares', '<i></i><i></i><i></i><i></i>'));
    if (footer === 'hub') c.append(el('foot-hub', 'MICROSOFT SPEAKERS HUB EN ESPAÑOL'), el('foot-bar'));
    slide.prepend(c);
    if (ds.kicker) {
      const k = el(`kicker k-${ds.kickerColor || 'orange'}${ds.kickerMono === 'true' ? ' mono' : ''}`);
      k.textContent = ds.kicker; slide.append(k);
    }
  });
})();
