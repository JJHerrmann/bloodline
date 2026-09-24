function renderEpisodeLedger(sourceEpisodes, totalWords) {
  const episodes = [...sourceEpisodes].sort((a, b) => a.number - b.number);
  const written = episodes.filter(episode => episode.started !== false).length;
  const lane = words => words < 1500 ? '#d19a2e' : words <= 3750 ? '#3fa66b' : '#c05a5a';
  const label = words => words < 1500 ? 'under length' : words <= 3750 ? 'in lane' : 'over length';
  document.querySelector('#episode-progress').textContent = `${written} written · gold = released · gray = not started`;
  document.querySelector('#total-progress').textContent = `${totalWords.toLocaleString()} words in manuscript`;
  document.querySelector('#episode-grid').innerHTML = episodes.map(episode => episode.started === false ? `<span class="episode-pill not-started" style="--lane:#657781" title="Episode ${episode.number}: not started">${episode.number}</span>` : `<span class="episode-pill ${episode.published || episode.released ? 'published' : ''}" style="--lane:${lane(episode.words)}" title="Episode ${episode.number}: ${episode.words.toLocaleString()} words · ${label(episode.words)}${episode.published || episode.released ? ' · released' : ''}">${episode.number}</span>`).join('');
}

fetch('/content/workshop.json', {cache: 'no-store'})
  .then(response => response.ok ? response.json() : Promise.reject())
  .then(data => {
    const book = data.books?.[0];
    if (!book) return;
    if (!document.documentElement.dataset.liveLedger) {
      renderEpisodeLedger(book.plannedEpisodes || book.episodes || [], book.wordCount);
    }
  })
  .catch(() => {});

const stationMessages = [
  {kicker: 'Citizen signal', title: 'FILE A DISPATCH', detail: 'Vote on the next broadcast', path: '/dispatch/', domain: 'bloodline.rook.works', route: '/dispatch', label: 'File a dispatch'},
  {kicker: 'Public transmission', title: 'READ THE STORY', detail: 'Start The Garnet Shield free', path: '/read/', domain: 'bloodline.rook.works', route: '/read', label: 'Read the public story'},
  {kicker: 'From the files of', title: 'SHELTON OBSERVATORY', detail: 'Unearth an Appalachian case file', path: '/read/shelton-observatory/voices-at-lovers-leap/', domain: 'bloodline.rook.works', route: '/shelton', label: 'Read Shelton Observatory'},
  {kicker: 'Keep the signal lit', title: 'JOIN THE HALLOWED', detail: 'Paid members read ahead', path: 'https://www.patreon.com/masonrok', domain: 'patreon.com', route: '/masonrok', label: 'Join paid membership'},
  {kicker: 'Station objective', title: 'SUBSCRIBE TO WDSR', detail: 'Help fund the next broadcast', path: 'https://www.twitch.tv/subs/masonrok_author', domain: 'twitch.tv', route: '/subs/masonrok_author', label: 'Subscribe to WDSR'}
];

const stationCta = document.querySelector('#station-cta');
const ctaMessage = document.querySelector('#cta-message');
const ctaRoute = document.querySelector('#cta-route');
let stationMessageIndex = 0;
function showStationMessage(index, immediate = false) {
  const message = stationMessages[index];
  const update = () => {
    document.querySelector('#cta-kicker').textContent = message.kicker;
    document.querySelector('#cta-title').textContent = message.title;
    document.querySelector('#cta-detail').textContent = message.detail;
    document.querySelector('#cta-domain').textContent = message.domain;
    document.querySelector('#cta-path').textContent = message.route;
    stationCta.href = message.path;
    stationCta.setAttribute('aria-label', message.label);
    ctaMessage.classList.remove('is-changing');
    ctaRoute.classList.remove('is-changing');
  };
  if (immediate) return update();
  ctaMessage.classList.add('is-changing');
  ctaRoute.classList.add('is-changing');
  setTimeout(update, 230);
}
showStationMessage(stationMessageIndex, true);
setInterval(() => {
  stationMessageIndex = (stationMessageIndex + 1) % stationMessages.length;
  showStationMessage(stationMessageIndex);
}, 8000);

const stoneHues = [344, 18, 47, 103, 174, 215, 276];
let stoneIndex = 0;
function shiftStoneField() {
  document.documentElement.style.setProperty('--stone-hue', stoneHues[stoneIndex]);
  stoneIndex = (stoneIndex + 1) % stoneHues.length;
}
shiftStoneField();
setInterval(shiftStoneField, 16000);

const clock = document.querySelector('#sprint-clock');
const streamState = document.querySelector('#sprint-state');
const streamDelta = document.querySelector('#sprint-delta');
const dispatchBar = document.querySelector('#dispatch-bar');
async function fetchLiveStatus() {
  const endpoints = ['/api/status', 'http://127.0.0.1:4174/api/status'];
  for (const endpoint of endpoints) {
    try {
      const response = await fetch(endpoint, {cache: 'no-store'});
      if (response.ok) return response.json();
    } catch (_) {}
  }
  return Promise.reject();
}
async function updateLiveSession() {
  try {
    const live = await fetchLiveStatus();
    document.documentElement.dataset.liveLedger = 'true';
    renderEpisodeLedger(live.episodes, live.novelWords);
    dispatchBar.classList.toggle('is-writing', live.phase === 'writing');
    const seconds = live.sprint.secondsRemaining;
    clock.textContent = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
    streamState.innerHTML = `<i></i> ${live.phase === 'writing' ? 'Writing sprint' : live.phase}`;
    const signed = `${live.sprint.deltaWords >= 0 ? '+' : ''}${live.sprint.deltaWords.toLocaleString()}`;
    streamDelta.textContent = live.phase === 'writing' ? `${signed} words across ${live.sprint.episodeDeltas.length || 0} episode${live.sprint.episodeDeltas.length === 1 ? '' : 's'}` : `Episode ${live.activeEpisode ?? '—'} · ${live.episodeWords.toLocaleString()} words`;
  } catch (error) {
    streamDelta.textContent = 'Live folder feed unavailable';
    console.error('Bloodline live folder feed:', error);
  }
}
updateLiveSession(); setInterval(updateLiveSession, 1000);
