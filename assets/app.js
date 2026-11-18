/* Amélioration progressive : aucune donnée non publiée, aucun service tiers. */
'use strict';
(() => {
  const searchIndexUrl = new URL('../search-index.json', document.currentScript.src);
  const params = new URLSearchParams(location.search);
  const filter = document.querySelector('[data-filters]');
  if (filter) {
    const fields = [...filter.querySelectorAll('input,select')];
    fields.forEach(field => { if (params.has(field.name)) field.value = params.get(field.name); });
    const apply = (save = true) => {
      const selected = Object.fromEntries(fields.map(field => [field.name, field.value]));
      const year = selected.year === '' || selected.year === undefined ? null : Number(selected.year);
      let count = 0;
      document.querySelectorAll('[data-filter-item]').forEach(item => {
        const match = (!selected.category || item.dataset.category === selected.category)
          && (!selected.period || item.dataset.period === selected.period)
          && (year === null || (Number.isInteger(year) && year >= Number(item.dataset.start) && year <= Number(item.dataset.end)));
        item.hidden = !match;
        if (match) count += 1;
      });
      document.querySelector('[data-result-count]').textContent = `${count} fiche${count > 1 ? 's' : ''} pour ces critères.`;
      document.querySelector('[data-filter-empty]').hidden = count !== 0;
      if (save) {
        const next = new URLSearchParams();
        fields.forEach(field => { if (field.value !== '') next.set(field.name, field.value); });
        history.replaceState(null, '', location.pathname + (next.size ? '?' + next : ''));
      }
    };
    filter.addEventListener('submit', event => { event.preventDefault(); apply(); });
    filter.addEventListener('reset', () => {
      fields.forEach(field => { field.value = ''; });
      apply();
    });
    apply(false);
  }

  const search = document.querySelector('[data-search]');
  if (!search) return;
  const input = search.querySelector('input');
  const results = document.querySelector('[data-search-results]');
  const status = document.querySelector('[data-search-status]');
  const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('fr').replace(/œ/g, 'oe').replace(/æ/g, 'ae');
  let indexPromise;
  let request = 0;
  const run = async () => {
    const current = ++request;
    const query = input.value.trim();
    const next = new URLSearchParams();
    if (query) next.set('q', query);
    history.replaceState(null, '', location.pathname + (next.size ? '?' + next : ''));
    results.replaceChildren();
    if (!query) {
      status.textContent = 'Saisissez un mot pour explorer les fiches.';
      return;
    }
    status.textContent = 'Recherche en cours…';
    try {
      indexPromise ||= fetch(searchIndexUrl, {credentials: 'same-origin'}).then(response => {
        if (!response.ok) throw new Error('Index indisponible');
        return response.json();
      }).catch(error => { indexPromise = null; throw error; });
      const rows = await indexPromise;
      if (current !== request) return;
      const terms = normalize(query).split(/\s+/).filter(Boolean);
      const matches = rows.filter(row => terms.every(term => normalize(row.text).includes(term)));
      status.textContent = matches.length ? `${matches.length} résultat${matches.length > 1 ? 's' : ''} pour « ${query} ».` : `Aucun résultat pour « ${query} ». Essayez un autre mot ou consultez les répertoires.`;
      const fragment = document.createDocumentFragment();
      matches.forEach(row => {
        const card = document.createElement('article');
        card.className = 'card';
        const content = document.createElement('div');
        content.className = 'card-content';
        const label = document.createElement('span');
        label.className = 'eyebrow';
        label.textContent = row.type;
        const h2 = document.createElement('h2');
        const link = document.createElement('a');
        // Défense supplémentaire : l’index contient uniquement des URLs locales générées.
        link.href = row.url.startsWith('/') && !row.url.startsWith('//') ? row.url : location.pathname;
        link.textContent = row.title;
        h2.append(link);
        const summary = document.createElement('p');
        summary.textContent = row.summary;
        content.append(label, h2, summary);
        card.append(content);
        fragment.append(card);
      });
      results.append(fragment);
    } catch (_) {
      if (current === request) status.textContent = 'La recherche est momentanément indisponible. Vous pouvez parcourir les répertoires via la navigation.';
    }
  };
  search.addEventListener('submit', event => { event.preventDefault(); run(); });
  if (params.has('q')) { input.value = params.get('q'); run(); }
})();
