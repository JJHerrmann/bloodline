(() => {
  const root = 'https://www.patreon.com';
  const roman = number => {
    if (number === 0) return '0';
    const numerals = [[1000, 'M'], [900, 'CM'], [500, 'D'], [400, 'CD'], [100, 'C'], [90, 'XC'], [50, 'L'], [40, 'XL'], [10, 'X'], [9, 'IX'], [5, 'V'], [4, 'IV'], [1, 'I']];
    let output = '', remaining = number;
    for (const [value, symbol] of numerals) while (remaining >= value) { output += symbol; remaining -= value; }
    return output;
  };
  const episodeLabel = episode => episode.number === 0 ? 'Prologue' : `Episode ${episode.number}`;
  const patreonUrl = value => !value ? 'https://www.patreon.com/masonrok' : value.startsWith('http') ? value : `${root}${value}`;
  const readerUrl = episode => episode.public_url && episode.public_url !== '/read/'
    ? episode.public_url
    : `/read/garnet-shield/episode-${episode.number}/`;
  const formatDate = value => value ? new Intl.DateTimeFormat('en-US', {month: 'short', day: 'numeric'}).format(new Date(`${value}T12:00:00`)).replace(' ', '. ') : '';

  const setText = (id, value) => { const node = document.getElementById(id); if (node) node.textContent = value; };

  function render({episodes = []}) {
    const publicEpisodes = episodes.filter(episode => episode.status === 'public' || episode.website_public === true)
      .sort((a, b) => a.number - b.number);
    const advance = episodes.filter(episode => episode.status === 'advance')
      .sort((a, b) => b.number - a.number)[0];
    const latestPublic = publicEpisodes.at(-1);
    const current = advance || latestPublic;

    if (publicEpisodes.length) setText('public-count-bulletin', `${publicEpisodes.length} installment${publicEpisodes.length === 1 ? '' : 's'} free`);
    if (advance) setText('advance-bulletin', `${episodeLabel(advance)} ahead on Patreon`);
    else setText('advance-bulletin', 'New installments file first on Patreon');

    if (latestPublic) {
      const link = document.getElementById('latest-public-link');
      link.href = readerUrl(latestPublic);
      link.textContent = `Read ${episodeLabel(latestPublic)} →`;
    }

    if (current) {
      setText('current-number', roman(current.number));
      setText('current-title', current.title || episodeLabel(current));
      const isAdvance = current.status === 'advance';
      setText('current-summary', isAdvance
        ? 'The newest completed installment is available early to The Hallowed and above before it enters the public archive.'
        : 'The most recent public installment is ready to read in the Bloodline archive.');
      const link = document.getElementById('current-link');
      link.href = isAdvance ? patreonUrl(current.patreon_url) : readerUrl(current);
      setText('current-link-label', isAdvance ? 'Read the advance installment →' : 'Read the current installment →');
      const note = document.getElementById('current-link-note');
      note.textContent = isAdvance ? 'Available now through Patreon' : 'Available free in the public archive';
    }

    const archive = document.getElementById('archive-list');
    if (archive && publicEpisodes.length) {
      archive.replaceChildren(...publicEpisodes.slice(-4).reverse().map(episode => {
        const item = document.createElement('li');
        const numeral = document.createElement('span'); numeral.textContent = roman(episode.number);
        const title = document.createElement('strong');
        const link = document.createElement('a'); link.href = readerUrl(episode); link.textContent = episode.title || episodeLabel(episode);
        title.append(link);
        const time = document.createElement('time'); time.textContent = formatDate(episode.published || episode.patreon_published);
        item.append(numeral, title, time);
        return item;
      }));
    }
  }

  fetch('/content/publication.json', {cache: 'no-store'}).then(response => {
    if (!response.ok) throw new Error('Release ledger unavailable');
    return response.json();
  }).then(render).catch(() => {});
})();
