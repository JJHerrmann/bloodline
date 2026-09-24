const schedule = document.querySelector('#release-schedule');

function formatDate(value) {
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(new Date(`${value}T12:00:00`));
}

fetch('/content/publication.json')
  .then(response => response.ok ? response.json() : Promise.reject(new Error('Ledger unavailable')))
  .then(({ episodes }) => {
    const visible = episodes.filter(episode => episode.status === 'public' || episode.status === 'advance').slice(-7);
    schedule.replaceChildren(...visible.map(episode => {
      const item = document.createElement('li');
      item.className = episode.status;
      const date = episode.published || episode.patreon_published;
      item.innerHTML = `<b>${episode.number === 0 ? 'Prologue' : `Episode ${episode.number}`}</b><span>${episode.status === 'advance' ? 'Patreon early' : formatDate(date)}</span>`;
      return item;
    }));
  })
  .catch(() => { schedule.innerHTML = '<li class="loading">Release ledger available at bloodline.rook.works/read</li>'; });
