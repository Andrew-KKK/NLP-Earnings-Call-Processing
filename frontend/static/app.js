// Chat panel: posts to /chat/stream via EventSource and appends chunks to #chat-log.
// Bot bubbles render a small subset of markdown (paragraphs, lists, bold/italic, inline code).
(function () {
  const form = document.getElementById('chat-form');
  if (!form) return;
  const log = document.getElementById('chat-log');
  const input = document.getElementById('chat-input');
  const slug = form.dataset.case;
  const history = [];

  const escapeHtml = (s) => s.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));

  function renderMarkdown(text) {
    let s = escapeHtml(text);

    // Inline code first so backticks don't interfere with bold/italic.
    s = s.replace(/`([^`\n]+)`/g, '<code class="px-1 py-[1px] rounded bg-line text-ink text-[0.85em] font-mono">$1</code>');

    // Bold (**x**) before italic (*x*) so the * pair isn't mistaken for italic.
    s = s.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>');

    // Group consecutive list lines into a <ul>/<ol>.
    const lines = s.split('\n');
    const grouped = [];
    let listKind = null; // 'ul' | 'ol' | null
    const flush = () => {
      if (listKind) {
        grouped.push(`</${listKind}>`);
        listKind = null;
      }
    };
    for (const line of lines) {
      const ul = /^\s*[*\-·•]\s+(.*)$/.exec(line);
      const ol = /^\s*\d+\.\s+(.*)$/.exec(line);
      if (ul) {
        if (listKind !== 'ul') { flush(); grouped.push('<ul class="list-disc pl-5 my-1 space-y-0.5">'); listKind = 'ul'; }
        grouped.push(`<li>${ul[1]}</li>`);
      } else if (ol) {
        if (listKind !== 'ol') { flush(); grouped.push('<ol class="list-decimal pl-5 my-1 space-y-0.5">'); listKind = 'ol'; }
        grouped.push(`<li>${ol[1]}</li>`);
      } else {
        flush();
        grouped.push(line);
      }
    }
    flush();
    s = grouped.join('\n');

    // Paragraph breaks: blank-line splits → <p>; single newline → <br> (inside paragraphs only).
    return s
      .split(/\n{2,}/)
      .map((para) => {
        const trimmed = para.trim();
        if (!trimmed) return '';
        // Don't wrap blocks that already start with a list/heading tag.
        if (/^<(ul|ol|h\d|blockquote|pre)\b/.test(trimmed)) return trimmed;
        return `<p class="my-1 leading-relaxed">${trimmed.replace(/\n/g, '<br>')}</p>`;
      })
      .filter(Boolean)
      .join('');
  }

  function bubble(role, text) {
    const div = document.createElement('div');
    div.className = role === 'me'
      ? 'self-end inline-block px-3 py-2 rounded-xl bg-ink text-white max-w-[85%]'
      : 'self-start inline-block px-3 py-2 rounded-xl bg-accent-soft text-ink max-w-[92%]';
    if (role === 'me') {
      div.textContent = text;
    } else {
      div.innerHTML = renderMarkdown(text);
    }
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  form.addEventListener('submit', (ev) => {
    ev.preventDefault();
    const msg = (input.value || '').trim();
    if (!msg) return;
    bubble('me', msg);
    history.push({ role: 'user', parts: [msg] });
    input.value = '';

    const bot = bubble('bot', '');
    const url = `/chat/stream?case=${encodeURIComponent(slug)}&msg=${encodeURIComponent(msg)}&history=${encodeURIComponent(JSON.stringify(history))}`;
    const es = new EventSource(url);
    let acc = '';
    es.onmessage = (e) => {
      acc += e.data; // Server-side framing preserves all newlines; just concatenate.
      bot.innerHTML = renderMarkdown(acc);
      log.scrollTop = log.scrollHeight;
    };
    es.addEventListener('done', () => {
      es.close();
      history.push({ role: 'model', parts: [acc] });
    });
    es.onerror = () => { es.close(); };
  });
})();
