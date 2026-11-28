(() => {
  const API = '/api/v1';
  const readSession = () => {
    try { return JSON.parse(sessionStorage.getItem('learnmate-session') || 'null'); }
    catch { return null; }
  };
  let session = readSession();
  let currentArticle = null;
  let currentRoom = null;
  let roomList = [];

  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const hasLogin = () => !!(session && session.token);
  const withAuth = headers => ({...(headers || {}), ...(hasLogin() ? {Authorization: `Bearer ${session.token}`} : {})});

  async function request(path, options = {}, retry = true) {
    const response = await fetch(API + path, {...options, headers: withAuth({'Content-Type':'application/json', ...(options.headers || {})})});
    const payload = await response.json().catch(() => ({}));
    if (response.status === 401 && retry && session?.refresh) {
      const rotated = await fetch(API + '/auth/refresh', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({refresh_token:session.refresh})}).then(r => r.json()).catch(() => ({}));
      if (rotated.data) {
        session = {user:rotated.data.user, token:rotated.data.tokens.access_token, refresh:rotated.data.tokens.refresh_token};
        sessionStorage.setItem('learnmate-session', JSON.stringify(session));
        return request(path, options, false);
      }
    }
    if (!response.ok) throw new Error(payload.error?.message || 'That didn’t work. Please try again.');
    return payload.data;
  }

  function loginNudge(target) {
    if (target) target.innerHTML = 'Sign in to save your questions and join the room. <a href="/workspace?mode=login">Sign in ↗</a>';
  }

  function renderArticles(items) {
    const host = document.getElementById('curiosityArticles');
    if (!host) return;
    if (!items.length) { host.innerHTML = '<p class="curiosity-loading">More field notes are on their way.</p>'; return; }
    host.innerHTML = items.map(article => {
      const saved = !!article.saved;
      const safeUrl = /^https:\/\//i.test(article.source_url) ? article.source_url : '#';
      return `<article class="research-entry" data-article="${esc(article.id)}"><div class="research-meta"><span class="research-topic">${esc(article.topic)}</span><span>·</span><span>${esc(article.reading_minutes || 4)} MIN</span></div><h4>${esc(article.title)}</h4><p class="research-hook">${esc(article.hook)}</p><p>${esc(article.summary)}</p><div class="research-actions"><button type="button" data-ask-article="${esc(article.id)}">Ask about this ↗</button><button type="button" class="${saved?'is-saved':''}" aria-pressed="${saved}" data-save-article="${esc(article.id)}">${saved?'♥ Saved':'♡ Save note'}</button><a target="_blank" rel="noopener noreferrer" href="${esc(safeUrl)}" data-read-article="${esc(article.id)}">Original study ↗</a></div><div class="research-meta" style="margin-top:8px">SOURCE / ${esc(article.source_name)}</div></article>`;
    }).join('');
    host.querySelectorAll('[data-ask-article]').forEach(button => button.addEventListener('click', () => {
      currentArticle = button.dataset.askArticle;
      const input = document.getElementById('curiosityQuestion');
      input.value = `Help me understand this research: ${button.closest('.research-entry').querySelector('h4').textContent}. `;
      input.focus();
      document.getElementById('curiosityQuestionForm').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth', block:'center'});
    }));
    host.querySelectorAll('[data-save-article]').forEach(button => button.addEventListener('click', async () => {
      if (!hasLogin()) { loginNudge(document.getElementById('curiosityAskStatus')); return; }
      const id = button.dataset.saveArticle;
      const event = button.getAttribute('aria-pressed') === 'true' ? 'unsave' : 'save';
      try { await request(`/curiosity/articles/${encodeURIComponent(id)}/events`, {method:'POST', body:JSON.stringify({event})}); await loadArticles(); }
      catch (error) { document.getElementById('curiosityAskStatus').textContent = error.message; }
    }));
    host.querySelectorAll('[data-read-article]').forEach(link => link.addEventListener('click', () => {
      if (hasLogin()) request(`/curiosity/articles/${encodeURIComponent(link.dataset.readArticle)}/events`, {method:'POST', body:JSON.stringify({event:'view'})}).catch(() => {});
    }));
  }

  async function loadArticles() {
    try {
      const result = await request('/curiosity/articles');
      renderArticles(result.articles || []);
      const toggle = document.getElementById('curiosityRecommendations');
      toggle.checked = !!result.recommendations_enabled;
      toggle.disabled = !hasLogin();
      if (result.recommended_topics?.length) {
        const shelf = document.querySelector('.curiosity-library .curiosity-intro');
        shelf.textContent = `Your reading has been circling ${result.recommended_topics.join(' and ')}. Here are more original studies to explore.`;
      }
    } catch { document.getElementById('curiosityArticles').innerHTML = '<p class="curiosity-loading">The field notes could not load just now. Refresh to try again.</p>'; }
  }

  async function loadPreference() {
    const toggle = document.getElementById('curiosityRecommendations');
    toggle.disabled = !hasLogin();
    if (!hasLogin()) return;
    try { const value = await request('/curiosity/preferences'); toggle.checked = value.recommendations_enabled; }
    catch { toggle.disabled = true; }
  }

  function showSolution(result) {
    const host = document.getElementById('curiositySolution');
    const status = result.verification?.status || result.solution_deck?.verification || 'unverified';
    host.innerHTML = `<div class="solution-content"><span class="solution-label">SOLUTION DECK / ${esc(status.toUpperCase())}</span><h4>${esc(result.question || 'Let’s open this idea up.')}</h4><p>${esc(result.solution_deck?.start_here || '')}</p><p>${esc(result.solution_deck?.explanation || result.answer || '')}</p><p><strong>Try next:</strong> ${esc(result.solution_deck?.try_next || '')}</p><div class="solution-actions"><small>${status === 'verified' ? 'Reviewed answer' : 'Draft answer · check against trusted sources'}</small><span>${result.id ? `<button type="button" data-feedback="true" data-question-id="${esc(result.id)}">Helpful</button><button type="button" data-feedback="false" data-question-id="${esc(result.id)}">Needs work</button>` : ''}</span></div></div>`;
    host.querySelectorAll('[data-feedback]').forEach(button => button.onclick = async () => {
      try { await request(`/curiosity/questions/${encodeURIComponent(button.dataset.questionId)}/feedback`, {method:'POST', body:JSON.stringify({helpful:button.dataset.feedback === 'true'})}); button.textContent = 'Feedback saved'; button.disabled = true; }
      catch (error) { button.textContent = error.message; }
    });
  }

  async function loadQuestionHistory() {
    if (!hasLogin()) return;
    const host = document.getElementById('curiosityHistory');
    try {
      const rows = await request('/curiosity/questions');
      host.innerHTML = rows.slice(0,4).map(row => `<div class="history-item"><strong>${esc(row.prompt)}</strong><br>${esc(row.answer.slice(0,150))}${row.answer.length>150?'…':''}</div>`).join('');
    } catch { host.textContent = ''; }
  }

  async function askQuestion(event) {
    event.preventDefault();
    const input = document.getElementById('curiosityQuestion');
    const status = document.getElementById('curiosityAskStatus');
    if (!hasLogin()) { loginNudge(status); return; }
    const question = input.value.trim();
    if (!question) return;
    status.textContent = 'Thinking it through…';
    const button = event.currentTarget.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      const result = await request('/curiosity/questions', {method:'POST', body:JSON.stringify({question, article_id:currentArticle})});
      showSolution(result); input.value = ''; currentArticle = null;
      status.textContent = 'Saved to your learner account. Check the source for important decisions.';
      await loadQuestionHistory();
    } catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  }

  async function loadRooms() {
    const select = document.getElementById('curiosityRoomSelect');
    try {
      roomList = await request('/communities/rooms');
      select.innerHTML = roomList.map(room => `<option value="${esc(room.id)}">${esc(room.name)} · ${esc(room.topic)}</option>`).join('');
      if (!roomList.length) { select.innerHTML = '<option value="">No circles available yet</option>'; return; }
      currentRoom = select.value = roomList[0].id;
      document.getElementById('curiosityRoomPrompt').textContent = roomList[0].prompt;
      await loadRoomMessages();
    } catch { select.innerHTML = '<option value="">Circles are unavailable</option>'; }
  }

  async function loadRoomMessages() {
    const host = document.getElementById('curiosityRoomMessages');
    const room = roomList.find(item => item.id === currentRoom);
    if (room) document.getElementById('curiosityRoomPrompt').textContent = room.prompt;
    if (!hasLogin()) {
      host.innerHTML = '<p class="curiosity-loading">Sign in to read and join this circle.</p>';
      document.getElementById('curiosityRoomStatus').textContent = 'Community posts are shared with signed-in learners.';
      return;
    }
    try {
      const messages = await request(`/communities/rooms/${encodeURIComponent(currentRoom)}/messages?limit=60`);
      host.innerHTML = messages.length ? messages.map(message => `<div class="room-message ${message.user_id===session.user?.id?'is-mine':''} ${message.status==='pending_review'?'pending':''}"><strong>${esc(message.display_name)}${message.user_id===session.user?.id?' · YOU':''}</strong>${esc(message.body)}${message.status==='pending_review'?'<small>Waiting for review</small>':message.user_id!==session.user?.id?`<button class="room-report" type="button" title="Report this post" aria-label="Report post by ${esc(message.display_name)}" data-report-message="${esc(message.id)}">⚑</button>`:''}</div>`).join('') : '<p class="curiosity-loading">Be the first to add a thought to this circle.</p>';
      host.scrollTop = host.scrollHeight;
      document.getElementById('curiosityRoomStatus').textContent = 'Keep it kind. Never post private contact details.';
      host.querySelectorAll('[data-report-message]').forEach(button => button.onclick = async () => {
        const reason = window.prompt('Why should this post be reviewed?');
        if (!reason?.trim()) return;
        try { await request(`/communities/messages/${encodeURIComponent(button.dataset.reportMessage)}/report`, {method:'POST', body:JSON.stringify({reason})}); await loadRoomMessages(); document.getElementById('curiosityRoomStatus').textContent = 'Thanks. The post is hidden while it is flagged for review.'; }
        catch (error) { document.getElementById('curiosityRoomStatus').textContent = error.message; }
      });
    } catch (error) {
      host.innerHTML = '<p class="curiosity-loading">Sign in to open this study circle.</p>';
      document.getElementById('curiosityRoomStatus').textContent = error.message;
    }
  }

  async function postToRoom(event) {
    event.preventDefault();
    const input = document.getElementById('curiosityRoomInput');
    const status = document.getElementById('curiosityRoomStatus');
    if (!hasLogin()) { loginNudge(status); return; }
    if (!currentRoom || !input.value.trim()) return;
    const button = event.currentTarget.querySelector('button');
    button.disabled = true;
    try {
      const message = await request(`/communities/rooms/${encodeURIComponent(currentRoom)}/messages`, {method:'POST', body:JSON.stringify({body:input.value.trim()})});
      input.value = '';
      await loadRoomMessages();
      status.textContent = message.status === 'pending_review' ? 'That post is held for review because it may contain contact information.' : 'Your thought is in the circle.';
    } catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  }

  document.getElementById('curiosityQuestionForm')?.addEventListener('submit', askQuestion);
  document.getElementById('curiosityRoomForm')?.addEventListener('submit', postToRoom);
  document.getElementById('curiosityRoomSelect')?.addEventListener('change', event => { currentRoom = event.target.value; loadRoomMessages(); });
  document.getElementById('curiosityRecommendations')?.addEventListener('change', async event => {
    if (!hasLogin()) { event.target.checked = false; loginNudge(document.getElementById('curiosityAskStatus')); return; }
    event.target.disabled = true;
    try { await request('/curiosity/preferences', {method:'PATCH', body:JSON.stringify({recommendations_enabled:event.target.checked})}); await loadArticles(); }
    catch (error) { event.target.checked = !event.target.checked; document.getElementById('curiosityAskStatus').textContent = error.message; }
    finally { event.target.disabled = false; }
  });
  loadArticles();
  loadPreference();
  loadQuestionHistory();
  loadRooms();
})();
