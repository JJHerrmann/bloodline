const number = value => new Intl.NumberFormat('en-US').format(value || 0);
const date = value => new Intl.DateTimeFormat('en-US', { month: 'long', day: 'numeric', year: 'numeric' }).format(new Date(value));

function episodeItems(planned, known, releaseByEpisode) {
  return planned.map(plan => {
    const episode = known.get(plan.number);
    const release = releaseByEpisode.get(plan.number);
    const state = release?.status === 'public' ? 'released' : release?.status === 'advance' ? 'patreon' : release?.status === 'scheduled' ? 'scheduled' : episode?.published ? 'released' : episode?.started ? 'drafting' : '';
    const label = release?.status === 'advance' ? 'available early on Patreon' : release?.status === 'scheduled' ? 'scheduled on Patreon' : episode?.published ? 'released' : episode?.started ? 'in production' : 'not yet started';
    const content = `${plan.number}${release?.status === 'advance' ? '<small>Patreon</small>' : release?.status === 'scheduled' ? '<small>Queued</small>' : ''}`;
    const releaseDate = release?.published || release?.patreon_published || null;
    let html;
    if (release?.status === 'public') html = `<a class="episode ${state}" href="${release.public_url || `/read/garnet-shield/episode-${plan.number}/`}" aria-label="Episode ${plan.number}: released — read it" title="Episode ${plan.number}: read it on Bloodline">${content}</a>`;
    else if (release?.status === 'advance' && release.patreon_url) html = `<a class="episode ${state}" href="${release.patreon_url}" aria-label="Episode ${plan.number}: available early on Patreon" title="Episode ${plan.number}: read ahead on Patreon">${content}</a>`;
    else html = `<div class="episode ${state}" aria-label="Episode ${plan.number}: ${label}" title="Episode ${plan.number}: ${label}">${content}</div>`;
    return { date: releaseDate, html };
  });
}

function observatoryItems(caseFiles) {
  return caseFiles
    .filter(caseFile => caseFile.published)
    .map(caseFile => {
      const label = `Shelton Observatory: ${caseFile.title}, filed ${date(caseFile.published)}`;
      const content = '<span class="observatory-mark" aria-hidden="true">&#9670;</span><small>Observatory</small>';
      const html = caseFile.url
        ? `<a class="episode observatory" href="${caseFile.url}" aria-label="${label}" title="${label}">${content}</a>`
        : `<div class="episode observatory" aria-label="${label}" title="${label}">${content}</div>`;
      return { date: caseFile.published, html };
    });
}

// Case files are filed by real-world date; episodes are filed by story order.
// A marker sits right after the last dated episode tile that precedes it, so
// the ledger reads as one timeline instead of two separate lists.
function interleaveByDate(items, markers) {
  const withInsertion = markers.map(marker => {
    let afterIndex = -1;
    items.forEach((item, index) => {
      if (item.date && item.date <= marker.date) afterIndex = index;
    });
    return { ...marker, afterIndex };
  });
  withInsertion.sort((a, b) => (b.afterIndex - a.afterIndex) || (a.date < b.date ? 1 : -1));
  const result = [...items];
  withInsertion.forEach(marker => result.splice(marker.afterIndex + 1, 0, marker));
  return result;
}

function render(book, generatedAt, releases = [], caseFiles = []) {
  const planned = book.plannedEpisodes || book.episodes || [];
  const known = new Map((book.episodes || []).map(episode => [episode.number, episode]));
  const releaseByEpisode = new Map(releases.map(release => [release.number, release]));
  const released = releases.length
    ? releases.filter(release => release.status === 'public').length
    : [...known.values()].filter(episode => episode.published).length;
  const percent = book.goalWords ? Math.min(100, book.wordCount / book.goalWords * 100) : 0;
  document.querySelector('#book-title').textContent = book.title;
  document.querySelector('#book-label').textContent = `${book.arc} · ${book.label}`;
  document.querySelector('#word-count').textContent = number(book.wordCount);
  document.querySelector('#percent').textContent = `${percent.toFixed(1)}%`;
  document.querySelector('#meter-fill').style.width = `${percent}%`;
  document.querySelector('#public-count').textContent = `${released} public installment${released === 1 ? '' : 's'} available`;
  document.querySelector('#updated').textContent = generatedAt ? `Production ledger last filed ${date(generatedAt)}` : 'Production ledger is being filed.';
  const grid = interleaveByDate(episodeItems(planned, known, releaseByEpisode), observatoryItems(caseFiles));
  document.querySelector('#episode-grid').innerHTML = grid.map(item => item.html).join('');
  if (!planned.length) document.querySelector('#episode-grid').textContent = 'The episode ledger is still being prepared.';
}

function loadLedger() {
  Promise.all([
    fetch('/content/workshop.json', { cache: 'no-store' }).then(response => response.ok ? response.json() : Promise.reject(new Error('Workshop ledger unavailable'))),
    fetch('/content/publication.json', { cache: 'no-store' }).then(response => response.ok ? response.json() : { episodes: [] }),
    fetch('/content/supplements.json', { cache: 'no-store' }).then(response => response.ok ? response.json() : { caseFiles: [] })
  ])
    .then(([data, publication, supplements]) => render(data.books?.[0] || {}, data.generatedAt, publication.episodes || [], supplements.caseFiles || []))
    .catch(() => { document.querySelector('#updated').textContent = 'The production ledger is temporarily unavailable. Please check back shortly.'; });
}

loadLedger();
setInterval(loadLedger, 60_000);
