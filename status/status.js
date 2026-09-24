const number = value => new Intl.NumberFormat('en-US').format(value || 0);
const date = value => new Intl.DateTimeFormat('en-US', { month: 'long', day: 'numeric', year: 'numeric' }).format(new Date(value));

function render(book, generatedAt, releases = []) {
  const planned = book.plannedEpisodes || book.episodes || [];
  const known = new Map((book.episodes || []).map(episode => [episode.number, episode]));
  const releaseByEpisode = new Map(releases.map(release => [release.number, release]));
  const released = [...known.values()].filter(episode => episode.published).length;
  const drafted = [...known.values()].filter(episode => episode.started && !episode.published).length;
  const percent = book.goalWords ? Math.min(100, book.wordCount / book.goalWords * 100) : 0;
  document.querySelector('#book-title').textContent = book.title;
  document.querySelector('#book-label').textContent = `${book.arc} · ${book.label}`;
  document.querySelector('#word-count').textContent = number(book.wordCount);
  document.querySelector('#percent').textContent = `${percent.toFixed(1)}%`;
  document.querySelector('#meter-fill').style.width = `${percent}%`;
  document.querySelector('#public-count').textContent = `${released} public installment${released === 1 ? '' : 's'} available`;
  document.querySelector('#updated').textContent = generatedAt ? `Production ledger last filed ${date(generatedAt)}` : 'Production ledger is being filed.';
  document.querySelector('#episode-grid').innerHTML = planned.map(plan => {
    const episode = known.get(plan.number);
    const release = releaseByEpisode.get(plan.number);
    const state = release?.status === 'advance' ? 'patreon' : episode?.published ? 'released' : episode?.started ? 'drafting' : '';
    const label = release?.status === 'advance' ? 'available early on Patreon' : episode?.published ? 'released' : episode?.started ? 'in production' : 'not yet started';
    const content = `${plan.number}${release?.status === 'advance' ? '<small>Patreon</small>' : ''}`;
    if (release?.status === 'public') return `<a class="episode ${state}" href="/read/garnet-shield/episode-${plan.number}/" aria-label="Episode ${plan.number}: released — read it" title="Episode ${plan.number}: read it on Bloodline">${content}</a>`;
    if (release?.status === 'advance' && release.patreon_url) return `<a class="episode ${state}" href="${release.patreon_url}" aria-label="Episode ${plan.number}: available early on Patreon" title="Episode ${plan.number}: read ahead on Patreon">${content}</a>`;
    return `<div class="episode ${state}" aria-label="Episode ${plan.number}: ${label}" title="Episode ${plan.number}: ${label}">${content}</div>`;
  }).join('');
  if (!planned.length) document.querySelector('#episode-grid').textContent = 'The episode ledger is still being prepared.';
}

function loadLedger() {
  Promise.all([
    fetch('/content/workshop.json', { cache: 'no-store' }).then(response => response.ok ? response.json() : Promise.reject(new Error('Workshop ledger unavailable'))),
    fetch('/content/publication.json', { cache: 'no-store' }).then(response => response.ok ? response.json() : { episodes: [] })
  ])
    .then(([data, publication]) => render(data.books?.[0] || {}, data.generatedAt, publication.episodes || []))
    .catch(() => { document.querySelector('#updated').textContent = 'The production ledger is temporarily unavailable. Please check back shortly.'; });
}

loadLedger();
setInterval(loadLedger, 60_000);
