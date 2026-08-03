const $ = id => document.getElementById(id);
function toast(msg, err){
  const t = $('toast');
  t.textContent = msg; t.className = err ? 'on err' : 'on';
  clearTimeout(t._h); t._h = setTimeout(()=>{ t.className=''; }, 3500);
}

function togglePeerKey(){
  const input = $('peer-supabase-key');
  const button = $('peer-key-toggle');
  if(!input || !button) return;
  const visible = input.type === 'password';
  input.type = visible ? 'text' : 'password';
  button.textContent = visible ? '\u{1F648}' : '\u{1F441}';
  button.setAttribute('aria-pressed', visible ? 'true' : 'false');
  button.setAttribute('aria-label', visible ? '公開キーを隠す' : '公開キーを表示');
}

async function copyPeerKey(){
  const input = $('peer-supabase-key');
  if(!input) return;
  if(!input.value){
    toast('公開キーを入力してからコピーしてください', true);
    return;
  }
  try{
    if(navigator.clipboard?.writeText){
      await navigator.clipboard.writeText(input.value);
    }else{
      input.focus();
      input.select();
      if(!document.execCommand('copy')) throw new Error('clipboard unavailable');
    }
    toast('公開キーをコピーしました');
  }catch(e){
    input.focus();
    input.select();
    toast('自動コピーできませんでした。選択された文字列を手動でコピーしてください', true);
  }
}

let BOOT = null;
const PERCENT_FIELDS = new Set(['reply_chance','friend_reply_chance','poke_chance','world_comment_chance','song_comment_chance']);
const CHECK_FIELDS = new Set(['think','kanji_mode','osc_proxy','greet_friends','diary','rule_polite','rule_trivia','rule_asks','rule_names',
  'persona_character_enabled','persona_talk_enabled','persona_preferences_enabled','persona_free_text_enabled','persona_examples_enabled',
  'advanced_growth_enabled','advanced_sense_enabled','advanced_listener_enabled','advanced_rules_enabled','advanced_aizuchi_enabled','advanced_safety_enabled']);
CHECK_FIELDS.add('core_prompt_enabled');
CHECK_FIELDS.add('vrcx_enabled');
CHECK_FIELDS.add('memory_conversation_enabled');
CHECK_FIELDS.add('memory_words_enabled');
CHECK_FIELDS.add('memory_diary_enabled');
CHECK_FIELDS.add('peer_enabled');
CHECK_FIELDS.add('peer_idle_enabled');
CHECK_FIELDS.add('peer_idle_initiator');
CHECK_FIELDS.add('social_context_enabled');
const DEFAULT_WEIGHT_OPTIONS = [{value:'low', label:'よわめ'}, {value:'mid', label:'ふつう'}, {value:'high', label:'つよめ'}];
function optHtml(items, selected){
  return items.map(o=>`<option value="${esc(o.value)}"${o.value===selected?' selected':''}>${esc(o.label)}</option>`).join('');
}
function renderWeightOptions(items, selected){
  return items.map(o=>`<option value="${esc(o.value)}"${o.value===selected?' selected':''}>${esc(o.label)}</option>`).join('');
}
function renderTraits(targetId, traits, cfg){
  const box = $(targetId);
  box.innerHTML = traits.map(t=>{
    const v = Number(cfg[t.key] ?? 50);
    return `<div class="field"><div class="lr"><span class="pole">${esc(t.left)}</span>`+
      `<output>${v}%</output><span class="pole">${esc(t.right)}</span></div>`+
      `<input type="range" name="${esc(t.key)}" min="0" max="100" step="5" value="${v}"></div>`;
  }).join('');
}
function renderRuleToggles(items, cfg){
  $('rule-toggles').innerHTML = items.map(r=>
    `<label class="check"><input type="checkbox" name="${esc(r.key)}"${cfg[r.key]?' checked':''}> ${esc(r.label)}</label>`
  ).join('');
}
function applyCategoryState(category){
  const toggle = category.querySelector('.category-toggle input');
  if(!toggle) return;
  const on = toggle.checked;
  category.classList.toggle('is-off', !on);
  category.setAttribute('aria-disabled', on ? 'false' : 'true');
  category.querySelectorAll('.category-body input,.category-body select,.category-body textarea').forEach(el=>{
    el.tabIndex = on ? 0 : -1;
  });
}
function initCategoryToggles(){
  document.querySelectorAll('.setting-category').forEach(category=>{
    const toggle = category.querySelector('.category-toggle input');
    if(!toggle || toggle.dataset.bound) return;
    toggle.dataset.bound = '1';
    toggle.addEventListener('change', ()=>{
      applyCategoryState(category);
      $('savebar').classList.add('on');
    });
    applyCategoryState(category);
  });
}
function initExternalToggles(){
  document.querySelectorAll('input[data-config-toggle][type="checkbox"]').forEach(toggle=>{
    if(toggle.dataset.bound) return;
    toggle.dataset.bound = '1';
    toggle.addEventListener('change', ()=>{
      $('savebar').classList.add('on');
    });
  });
}
function setField(form, name, value){
  const els = Array.from(document.querySelectorAll('[name]')).filter(el => el.name === name);
  els.forEach(el=>{
    if(el.type === 'checkbox') el.checked = !!value;
    else el.value = value ?? '';
    if(el.type === 'range'){
      const o = el.closest('.field')?.querySelector('output');
      if(o) o.textContent = el.value + '%';
    }
  });
}
function applyBootstrap(d){
  BOOT = d;
  PRESETS = d.presets || {};
  const cfg = d.cfg || {};
  const form = $('cfg');
  document.title = (d.pet_name_display || cfg.pet_name || 'むちこ') + 'のせってい';
  $('ttl').textContent = d.pet_name_display || cfg.pet_name || $('ttl').textContent;
  form.cfg_mtime.value = d.cfg_mtime || '';
  renderTraits('traits-character', (d.traits || []).filter(t=>t.group === 'character'), cfg);
  renderTraits('traits-talk', (d.traits || []).filter(t=>t.group === 'talk'), cfg);
  renderRuleToggles(d.rule_toggles || [], cfg);
  form.model.innerHTML = optHtml(d.model_options || [], cfg.model);
  form.model_en.innerHTML = optHtml(d.model_en_options || [], cfg.model_en);
  const weights = d.weight_options || DEFAULT_WEIGHT_OPTIONS;
  form.trait_weight.innerHTML = renderWeightOptions(weights, cfg.trait_weight || 'mid');
  form.persona_weight.innerHTML = renderWeightOptions(weights, cfg.persona_weight || 'mid');
  for(const [k,v0] of Object.entries(cfg)){
    const v = PERCENT_FIELDS.has(k) ? Math.round(Number(v0 || 0) * 100) : v0;
    setField(form, k, v);
  }
  CHECK_FIELDS.forEach(k=>setField(form, k, !!cfg[k]));
  initCategoryToggles();
  initExternalToggles();
  form.cfg_mtime.value = d.cfg_mtime || '';
  initPresets();
  updateSetupStatus();
}
async function loadBootstrap(){
  try{
    const d = await (await fetch('/bootstrap')).json();
    applyBootstrap(d);
    maybeStartTour();
  }catch(e){
    toast('設定の初期値を読み込めませんでした', true);
  }
}

async function upd(){
  try{
    $('stat').innerHTML = await (await fetch('/status')).text();
  }catch(e){}
  try{
    const r = await fetch('/log');
    const el = $('log');
    const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 30;
    el.innerHTML = await r.text();
    if(atBottom) el.scrollTop = el.scrollHeight;
  }catch(e){}
  try{
    const s = await (await fetch('/peer_status')).json();
    const el = $('peer-status');
    if(el){
      const labels = {disabled:'OFF',connecting:'接続中',connected:'接続済み',invalid:'設定エラー',
        missing_dependency:'追加ライブラリ不足',error:'接続エラー'};
      el.textContent = `Muchio間通信: ${labels[s.state] || s.state || '不明'} — ${s.detail || ''}`;
      el.className = 'status-note ' + (s.state === 'connected' ? 'good' :
        (['invalid','missing_dependency','error'].includes(s.state) ? 'err' : ''));
    }
  }catch(e){}
}
setInterval(upd, 3000); upd();

// ---- アップデート確認と適用(GitHubのmainを取り込み。反映は再起動後) ----
const updateState = $('update-state');
const runUpdate = $('run-update');
async function updateStatus(fetchRemote){
  updateState.className = 'update-state';
  updateState.textContent = fetchRemote ? 'GitHubを確認しています...' : '更新情報を確認中...';
  runUpdate.disabled = true;
  try{
    const d = await (await fetch('/update_status' + (fetchRemote ? '?fetch=1' : ''))).json();
    updateState.textContent = d.message || '更新情報を確認できませんでした';
    updateState.className = 'update-state ' + (d.ok ? (d.behind > 0 ? 'warn' : 'good') : 'err');
    runUpdate.disabled = !(d.ok && d.behind > 0 && d.ahead === 0);
  }catch(e){
    updateState.textContent = '更新情報を確認できませんでした';
    updateState.className = 'update-state err';
  }
}
$('check-update').addEventListener('click', ()=>updateStatus(true));
runUpdate.addEventListener('click', async ()=>{
  if(!confirm('アップデートしますか？ 完了したら run.bat を起動し直してください')) return;
  runUpdate.disabled = true;
  updateState.className = 'update-state';
  updateState.textContent = 'アップデート中...';
  try{
    const r = await fetch('/update', {method:'POST'});
    const d = await r.json();
    updateState.textContent = d.message || (r.ok ? 'アップデートしました。再起動してください' : 'アップデートできませんでした');
    updateState.className = 'update-state ' + (r.ok && d.ok ? 'good' : 'err');
  }catch(e){
    updateState.textContent = 'アップデートできませんでした';
    updateState.className = 'update-state err';
  }
});
updateStatus(false);

// ---- はじめてガイド(とじたのをおぼえる) ----
const gb = $('guidebox');
gb.open = localStorage.getItem('muchio_guide') !== 'closed';
gb.addEventListener('toggle', ()=>localStorage.setItem('muchio_guide', gb.open ? 'open' : 'closed'));

// ---- シンプル/じんかく/アドバンスド タブ(選んだほうをおぼえる) ----
const SECTION_KEYS = ['start','basic','llm','audio','integrations','maintenance'];
const LEGACY_SECTION = {s:'start', j:'llm', a:'integrations'};
function normalizeWorkspaceLayout(){
  const main = document.querySelector('main.app-layout');
  const workspace = $('workspace');
  if(!main || !workspace) return;
  Array.from(main.children)
    .filter(el=>el.classList.contains('grid'))
    .forEach(grid=>workspace.appendChild(grid));
}
function normalizeSections(){
  const categorySections = {
    'advanced-rules':'llm','advanced-aizuchi':'llm','advanced-safety':'maintenance',
    'advanced-growth':'integrations','advanced-sense':'integrations','advanced-listener':'audio',
    'vrcx':'integrations','memory-words':'integrations'
  };
  Object.entries(categorySections).forEach(([key, section])=>{
    const el = document.querySelector(`[data-category="${key}"]`);
    if(el){ el.dataset.section = section; el.classList.add('section-page'); }
  });
  [['#voices','audio'],['#friends','integrations'],['#memory','integrations'],['#words','integrations'],['#log','maintenance']]
    .forEach(([selector, section])=>{
      const el = document.querySelector(selector)?.closest('section');
      if(el){ el.dataset.section = section; el.classList.add('section-page'); }
    });
}

const ONBOARDING_KEY = 'muchio_onboarding_v1';
const TOUR_STEPS = [
  {section:'llm', target:'#hardware', title:'まずモデルを準備', body:'GPU・VRAM・RAMを確認して、このPCで無理なく動くモデルを選ぶ。大きすぎるモデルは返答の遅延につながるため、推薦表示を基準にする。'},
  {section:'basic', target:'#basic-identity input[name="pet_name"]', title:'名前を設定', body:'ペットの名前と飼い主名を入力する。呼びかけの判定と返答の宛先に使うため、VRChatで表示される名前に合わせる。'},
  {section:'audio', target:'#audio-listener .category-head', title:'音声と表示を確認', body:'音声認識、OSC、文字盤の設定を確認する。ここを飛ばすと、名前を呼んでも返答が届かない可能性がある。'},
  {section:'start', target:'#start-test', title:'VRChatで返答を確認', body:'保存してVRChatで名前を呼ぶ。文字盤に返答が出たことを確認できたら、このボタンで案内を完了する。'}
];
let tourIndex = 0;
let tourRestoreFocus = null;
let tourLayoutFrame = 0;
const TOUR_VIEW_MARGIN = 80;
function readOnboarding(){
  try{ return JSON.parse(localStorage.getItem(ONBOARDING_KEY) || '') || {status:'new', step:0}; }
  catch(_){ return {status:'new', step:0}; }
}
function writeOnboarding(status, step=tourIndex){
  localStorage.setItem(ONBOARDING_KEY, JSON.stringify({status, step}));
}
function updateSetupStatus(){
  const form = $('cfg');
  if(!form) return;
  const state = readOnboarding();
  const done = {
    model: Boolean(form.model?.value),
    identity: Boolean(form.pet_name?.value.trim() && form.owner_name?.value.trim()),
    audio: Boolean(form.advanced_listener_enabled?.checked && form.osc_proxy?.checked),
    test: state.status === 'complete'
  };
  document.querySelectorAll('.setup-step').forEach((step,index)=>{
    const isDone = done[step.dataset.setup];
    step.classList.toggle('is-done', isDone);
    step.setAttribute('aria-label', `${step.querySelector('b')?.textContent || ''}${isDone ? ' 完了' : ' 未完了'}`);
    const number = step.querySelector('span');
    if(number) number.textContent = isDone ? '✓' : String(index + 1);
  });
}
function positionTour(target){
  const focus = $('tour-focus'), card = $('tour-card');
  if(!focus || !card || $('tour-layer')?.hidden) return;
  card.style.visibility = 'hidden';
  const cardWidth = Math.max(240, Math.min(390, window.innerWidth - 32));
  card.style.width = `${cardWidth}px`;
  const cardRect = card.getBoundingClientRect();
  const hasTarget = target && target.getClientRects().length > 0;
  const r = hasTarget ? target.getBoundingClientRect() : {
    top:Math.max(16, (window.innerHeight - cardRect.height) / 2 - 70),
    left:16,width:window.innerWidth-32,height:1,bottom:Math.max(16, (window.innerHeight - cardRect.height) / 2 - 70),right:window.innerWidth-16
  };
  const pad = 8;
  Object.assign(focus.style, {top:`${Math.max(8,r.top-pad)}px`, left:`${Math.max(8,r.left-pad)}px`, width:`${Math.max(24,r.width+pad*2)}px`, height:`${Math.max(24,r.height+pad*2)}px`});
  const cardHeight = cardRect.height || 180;
  const below = hasTarget && r.bottom + 18 + cardHeight <= window.innerHeight - 16;
  const wantedTop = hasTarget && below ? r.bottom + 18 : hasTarget ? r.top - cardHeight - 18 : (window.innerHeight - cardHeight) / 2;
  const top = Math.min(Math.max(16, wantedTop), Math.max(16, window.innerHeight - cardHeight - 16));
  const left = Math.min(Math.max(16, hasTarget ? r.left : (window.innerWidth - cardWidth) / 2), Math.max(16, window.innerWidth - cardWidth - 16));
  Object.assign(card.style, {top:`${top}px`, left:`${left}px`, visibility:'visible'});
}
function scheduleTourLayout(){
  if(tourLayoutFrame || $('tour-layer')?.hidden) return;
  tourLayoutFrame = requestAnimationFrame(()=>{
    tourLayoutFrame = 0;
    const target = document.querySelector(TOUR_STEPS[tourIndex]?.target);
    const rect = target?.getBoundingClientRect?.();
    if(target && rect && (rect.top < TOUR_VIEW_MARGIN || rect.bottom > window.innerHeight - TOUR_VIEW_MARGIN)){
      target.scrollIntoView({block:'center', behavior:'auto'});
    }
    positionTour(target);
  });
}
function settleTourTarget(target, stepIndex){
  if(stepIndex !== tourIndex || $('tour-layer')?.hidden || !target) return;
  const rect = target.getBoundingClientRect();
  if(rect.top < TOUR_VIEW_MARGIN || rect.bottom > window.innerHeight - TOUR_VIEW_MARGIN){
    target.scrollIntoView({block:'center', behavior:'auto'});
  }
  requestAnimationFrame(()=>{ if(stepIndex === tourIndex) positionTour(target); });
}
function renderTourStep(){
  const step = TOUR_STEPS[tourIndex];
  if(!step) return;
  setSection(step.section);
  $('tour-progress').textContent = `${tourIndex + 1} / ${TOUR_STEPS.length}`;
  $('tour-title').textContent = step.title;
  $('tour-body').textContent = step.body;
  $('tour-prev').disabled = tourIndex === 0;
  $('tour-next').textContent = tourIndex === TOUR_STEPS.length - 1 ? '返答を確認した' : '次へ';
  requestAnimationFrame(()=>{
    const target = document.querySelector(step.target) || document.querySelector(`[data-section="${step.section}"]`);
    target?.scrollIntoView({block:'center', behavior:'auto'});
    requestAnimationFrame(()=>settleTourTarget(target, tourIndex));
  });
}
function startTour(step=0){
  tourIndex = Math.max(0, Math.min(TOUR_STEPS.length - 1, step));
  tourRestoreFocus = document.activeElement;
  writeOnboarding('active', tourIndex);
  $('tour-layer').hidden = false;
  document.body.classList.add('tour-active');
  $('workspace')?.setAttribute('inert','');
  renderTourStep();
  $('tour-card').focus();
}
function endTour(status){
  writeOnboarding(status, tourIndex);
  $('tour-layer').hidden = true;
  document.body.classList.remove('tour-active');
  $('workspace')?.removeAttribute('inert');
  updateSetupStatus();
  const restore = tourRestoreFocus;
  tourRestoreFocus = null;
  if(restore && document.contains(restore)) restore.focus();
}
function maybeStartTour(){
  const state = readOnboarding();
  if(!localStorage.getItem(ONBOARDING_KEY) || state.status === 'new') requestAnimationFrame(()=>startTour(state.step || 0));
}
function initTour(){
  $('start-tour')?.addEventListener('click', ()=>startTour(0));
  $('replay-tour')?.addEventListener('click', ()=>startTour(0));
  $('start-test')?.addEventListener('click', ()=>startTour(3));
  $('tour-skip')?.addEventListener('click', ()=>endTour('skipped'));
  $('tour-prev')?.addEventListener('click', ()=>{ if(tourIndex > 0){ tourIndex--; writeOnboarding('active'); renderTourStep(); } });
  $('tour-next')?.addEventListener('click', ()=>{ if(tourIndex >= TOUR_STEPS.length - 1) endTour('complete'); else { tourIndex++; writeOnboarding('active'); renderTourStep(); } });
  window.addEventListener('resize', scheduleTourLayout, {passive:true});
  window.visualViewport?.addEventListener('resize', scheduleTourLayout, {passive:true});
  document.addEventListener('keydown', e=>{
    if(!$('tour-layer') || $('tour-layer').hidden) return;
    if(e.key === 'Escape'){ e.preventDefault(); endTour('skipped'); return; }
    if(e.key === 'ArrowRight'){ e.preventDefault(); $('tour-next').click(); return; }
    if(e.key === 'ArrowLeft'){ e.preventDefault(); $('tour-prev').click(); return; }
    if(e.key === 'Tab'){
      const focusable = Array.from($('tour-card').querySelectorAll('button:not([disabled])'));
      const first = focusable[0], last = focusable[focusable.length-1];
      if(e.shiftKey && document.activeElement === first){ e.preventDefault(); last.focus(); }
      else if(!e.shiftKey && document.activeElement === last){ e.preventDefault(); first.focus(); }
    }
  });
}
initTour();
function setSection(section, {focus=false}={}){
  if(!SECTION_KEYS.includes(section)) section = 'start';
  document.body.dataset.section = section;
  localStorage.setItem('muchio_section', section);
  document.querySelectorAll('.side-link').forEach(b=>{
    const active = b.dataset.section === section;
    b.classList.toggle('on', active);
    if(active) b.setAttribute('aria-current','page'); else b.removeAttribute('aria-current');
  });
  if(focus) document.querySelector(`[data-section="${section}"].section-page`)?.focus?.();
  closeDrawer();
}
function setTheme(theme){
  theme = theme === 'light' ? 'light' : 'dark';
  document.body.dataset.theme = theme;
  localStorage.setItem('muchio_theme', theme);
  const b = $('theme-toggle');
  if(b){ b.textContent = theme === 'dark' ? '☼' : '☾'; b.title = theme === 'dark' ? '明るいテーマにする' : '暗いテーマにする'; }
}
function setDrawer(open){
  $('sidebar')?.classList.toggle('open', open);
  $('nav-backdrop')?.classList.toggle('open', open);
  $('sidebar-toggle')?.setAttribute('aria-expanded', String(open));
  document.body.classList.toggle('drawer-open', open);
}
function closeDrawer(){ setDrawer(false); }
document.querySelectorAll('.side-link').forEach(b=>b.addEventListener('click', ()=>setSection(b.dataset.section, {focus:true})));
document.querySelectorAll('[data-go-section]').forEach(b=>b.addEventListener('click', ()=>setSection(b.dataset.goSection, {focus:true})));
$('sidebar-toggle')?.addEventListener('click', ()=>setDrawer(!$('sidebar').classList.contains('open')));
$('nav-backdrop')?.addEventListener('click', closeDrawer);
$('theme-toggle')?.addEventListener('click', ()=>setTheme(document.body.dataset.theme === 'light' ? 'dark' : 'light'));
document.addEventListener('keydown', e=>{ if(e.key === 'Escape' && $('sidebar')?.classList.contains('open')) closeDrawer(); });
normalizeWorkspaceLayout();
normalizeSections();
setTheme(localStorage.getItem('muchio_theme') || 'dark');
const oldSection = localStorage.getItem('muchio_section') || LEGACY_SECTION[localStorage.getItem('muchio_tab')] || 'start';
setSection(oldSection);

// ---- じんかくテンプレ: スライダー・こだわり・人格・れいぶんに一式を流し込む(保存は「ほぞん」で) ----
let PRESETS = {};
function initPresets(){
  const box = document.getElementById('presets'), f = document.getElementById('cfg');
  box.innerHTML = '';
  for(const k of Object.keys(PRESETS)){
    const item = document.createElement('div');
    item.className = 'preset-choice';
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'tab'; b.textContent = k;
    b.addEventListener('click', ()=>{
      const p = PRESETS[k];
      f.persona.value = p.persona; f.persona_en.value = p.persona_en;
      f.examples.value = p.examples; f.examples_en.value = p.examples_en;
      f.querySelectorAll('input[type=range][name^=trait_]').forEach(s=>{
        s.value = s.name in p.traits ? p.traits[s.name] : 50;   // ||50だと値0のプリセットが消える
        const o = s.closest('.field').querySelector('output');
        if(o) o.textContent = s.value + '%';
      });
      f.querySelectorAll('input[type=checkbox][name^=rule_]').forEach(c=>{ c.checked = !!p.checks[c.name]; });
      $('savebar').classList.add('on');
      toast('テンプレ「' + k + '」を入れました。「ほぞん」を押すと反映されます');
    });
    const d = document.createElement('small');
    d.textContent = PRESETS[k].description || '人格・話し方・例文をまとめて入れます。';
    item.append(b, d);
    box.appendChild(item);
  }
}

// ---- 設定の保存(fetch。リロードなしで連続保存できる) ----
const cfg = $('cfg');
cfg.addEventListener('input', e=>{
  if(e.target.type === 'range'){
    const o = e.target.closest('.field').querySelector('output');
    if(o) o.textContent = e.target.value + '%';
  }
  $('savebar').classList.add('on');
});
cfg.addEventListener('submit', async e=>{
  e.preventDefault();
  let r;
  const payload = new URLSearchParams(new FormData(cfg));
  document.querySelectorAll('input[data-config-toggle][type="checkbox"]').forEach(el=>{
    if(!cfg.contains(el)){
      payload.delete(el.name);
      if(el.checked) payload.append(el.name, 'on');
    }
  });
  try{ r = await fetch('/save', {method:'POST', body:payload}); }
  catch(_){ toast('サーバにつながりません', true); return; }
  let d = {}; try{ d = await r.json(); }catch(_){}
  if(r.ok && d.ok){
    cfg.cfg_mtime.value = d.mtime;
    $('ttl').textContent = cfg.pet_name.value.trim() || $('ttl').textContent;
    $('savebar').classList.remove('on');
    toast('ほぞんしました（数秒で反映されます）');
    updateSetupStatus();
    loadM();
    loadNgHits();
  }else if(r.status === 409){
    toast('べつの画面で設定が変わっています。ページを読み込み直してください', true);
  }else{
    toast('ほぞんできませんでした', true);
  }
});

// ---- 単語けし・会話リセット ----
$('purgeform').addEventListener('submit', async e=>{
  e.preventDefault();
  const w = e.target.word.value.trim();
  if(!w || !confirm('「'+w+'」を含む会話と日記をわすれる？（ファイルはバックアップされます）')) return;
  await fetch('/purge', {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:'word='+encodeURIComponent(w)});
  e.target.word.value = '';
  toast('「'+w+'」をわすれます（数秒で反映されます）');
});
$('resetform').addEventListener('submit', async e=>{
  e.preventDefault();
  if(!confirm('会話の記憶をリセットする？（ファイルはバックアップされます）')) return;
  await fetch('/reset', {method:'POST'});
  toast('会話の記憶をリセットします（数秒で反映されます）');
});

// ---- なかま一覧 ----
var F=[], LIM=20;
const esc=s=>s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ago=t=>!t?'-':(d=>d<1?'きょう':d+'日前')(Math.floor((Date.now()/1000-t)/86400));
let pullTimer = null;
function formatGb(n){ return n ? Number(n).toFixed(1) + ' GB' : '不明'; }
function formatBytesGb(n){ return n ? (Number(n) / 1e9).toFixed(1) + ' GB' : '不明'; }
function renderHardware(d){
  const gpu = d.gpu || {};
  const line = `${esc(gpu.name || 'GPU不明')} / VRAM ${formatGb(gpu.total_gb)} / RAM ${formatGb(d.ram_gb)} / `+
    `現在のプロンプト調整: ${esc(d.prompt_profile || 'full')}`;
  document.querySelector('#hardware .hardware-line').textContent = line;
  const installed = new Set(d.installed || []);
  const rec = d.recommended;
  $('model-recommend').innerHTML = (d.catalog || []).map(x=>{
    const isRec = x.name === rec, has = installed.has(x.name);
    return `<div class="model-row${isRec?' recommended':''}"><div><b>${esc(x.name)}</b>`+
      `${isRec?' <span class="model-badge">おすすめ</span>':''}`+
      `<small>${esc(x.label)} / ${formatBytesGb(x.size)} / ${esc(x.profile)}</small></div>`+
      (has ? `<button type="button" class="ghost use-model" data-model="${esc(x.name)}">これを使う</button>` :
        `<button type="button" class="ghost pull-model" data-model="${esc(x.name)}">ダウンロード</button>`)+
      `</div>`;
  }).join('') || '<small>推奨一覧を取得できません</small>';
  document.querySelectorAll('.pull-model').forEach(b=>b.addEventListener('click', ()=>pullModel(b.dataset.model)));
  document.querySelectorAll('.use-model').forEach(b=>b.addEventListener('click', ()=>useModel(b.dataset.model)));
}
function useModel(name){
  cfg.model.value = name;
  $('savebar').classList.add('on');
  toast(name + 'を選びました。「ほぞん」で切り替えます');
}
async function pullModel(name){
  const r = await fetch('/model_pull', {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:'model='+encodeURIComponent(name)});
  const d = await r.json().catch(()=>({}));
  if(!r.ok || !d.ok){ toast(d.error || 'モデルを取得できません', true); return; }
  toast(name + 'をダウンロードします。完了までこの画面を閉じなくていいです');
  clearInterval(pullTimer);
  pullTimer = setInterval(async()=>{
    const s = await (await fetch('/model_pull_status')).json().catch(()=>({}));
    const el = $('model-pull-status');
    el.textContent = s.status === 'done' ? `${s.model} の取得完了` :
      s.status === 'error' ? (s.error || '取得に失敗しました') : (s.line || '取得中...');
    if(s.status === 'done' || s.status === 'error'){
      clearInterval(pullTimer); pullTimer = null;
      loadHardware();
      if(s.status === 'done') useModel(s.model);
    }
  }, 1500);
}
async function loadHardware(){
  try{ renderHardware(await (await fetch('/hardware')).json()); }catch(_){
    document.querySelector('#hardware .hardware-line').textContent = 'スペックを取得できませんでした';
  }
  updateSetupStatus();
}
loadBootstrap();
loadHardware();
async function loadF(){
  try{ F = await (await fetch('/friends')).json(); drawF(); }catch(e){}
}
function drawF(){
  const q=document.getElementById('fq').value.trim().toLowerCase();
  const rows=F.filter(p=>!q||p.name.toLowerCase().includes(q)||p.nick.toLowerCase().includes(q));
  document.getElementById('friends').innerHTML = rows.slice(0,LIM).map(p=>
   `<div class="frow${p.here?' here':''}" data-uid="${esc(p.uid)}">
     <span class="fname">${esc(p.nick||p.name)}${p.nick?` <small>(${esc(p.name)})</small>`:''}`+
     `${p.here?'<span class="badge">いまいる</span>':''}${p.auto?'<span class="badge m">かおなじみ</span>':(p.manual?'<span class="badge m">てとつなぎ</span>':'')}`+
     `${p.board_ok?'':' <span title="この名前は文字盤に出せません。ひらがなのあだ名を付けると呼べます">⚠</span>'}</span>
     <span class="fmeta">${p.met}日 ・ ${ago(p.last)} ・ ${p.lang||'?'}</span>
     <input class="fnick" value="${esc(p.nick)}" placeholder="あだ名" onchange="saveF(this)">
     <label class="fgl"><input type="checkbox" class="fgreet" ${p.greet?'checked':''} onchange="saveF(this)">あいさつ</label>
     <label class="fgl"><input type="checkbox" class="fpoke" ${p.poke?'checked':''} onchange="saveF(this)">ちょっかい</label>
     <a href="#" title="この人の記録と声を忘れる${p.manual?'(登録も解除)':''}" onclick="delF('${esc(p.uid)}','${esc(p.nick||p.name)}');return false">🗑</a>
    </div>`).join('') || '<div class="frow">まだだれとも会っていません</div>';
}
async function saveF(el){
  const row = el.closest('.frow');
  const body = 'uid='+encodeURIComponent(row.dataset.uid)
    +'&nick='+encodeURIComponent(row.querySelector('.fnick').value)
    +'&greet='+(row.querySelector('.fgreet').checked?1:0)
    +'&poke='+(row.querySelector('.fpoke').checked?1:0);
  await fetch('/friend',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body});
  loadF();
}
async function delF(uid, name){
  if(!confirm(name+' の記録と声を忘れる？（手動登録なら解除。フレンドは次に会うとまた「はじめて」から）')) return;
  await fetch('/person_del',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:'uid='+encodeURIComponent(uid)});
  loadF(); loadV();
}
async function lookF(){
  const q=document.getElementById('fq').value.trim();
  const el=document.getElementById('look');
  if(q.length<2){ el.innerHTML='<div class="frow">検索欄に2文字以上入れてから押してね</div>'; return; }
  el.innerHTML='<div class="frow">さがしています...</div>';
  const rs = await (await fetch('/lookup?q='+encodeURIComponent(q))).json();
  el.innerHTML = rs.map(p=>
   `<div class="frow"><span class="fname">${esc(p.name)}</span>
     <span class="fmeta">${p.met}日 ・ ${ago(p.last)}</span>
     <button type="button" class="ghost" onclick="adoptF('${esc(p.uid)}',this)">登録</button>
    </div>`).join('') || '<div class="frow">みつからず（VRCXの記録にいる人だけ探せます）</div>';
}
async function adoptF(uid, btn){
  const name = btn.closest('.frow').querySelector('.fname').textContent;
  await fetch('/adopt',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:'uid='+encodeURIComponent(uid)+'&name='+encodeURIComponent(name)});
  document.getElementById('look').innerHTML='';
  loadF();
}
loadF();

// ---- こえおぼえ ----
async function loadV(){
  try{
    const d = await (await fetch('/voices')).json();
    document.getElementById('vprof').innerHTML = d.profiles.length
      ? '<small>おぼえたこえ: ' + d.profiles.map(p=>
          `${esc(p.name)}×${p.n} <a href="#" onclick="resetV('${esc(p.uid)}');return false" title="この声を忘れる">✕</a>`
        ).join('、') + '</small>'
      : '<small>まだ声をおぼえていません。下の発話に名前を付けてください</small>';
    const opts = F.slice(0,40).map(p=>`<option value="${esc(p.uid)}">${esc(p.nick||p.name)}</option>`).join('');
    document.getElementById('voices').innerHTML = d.recent.map(r=>
     `<div class="frow" data-ts="${r.ts}">
       <span class="fmeta">${new Date(r.ts*1000).toLocaleTimeString()}</span>
       <span class="fname">${esc(r.text)}</span>
       <span class="fmeta">${r.who_name?('→'+esc(r.who_name)):'?'}</span>
       <select class="fnick vsel"><option value="">だれ?</option>${opts}</select>
       <button type="button" class="ghost" onclick="labelV(this)">おぼえる</button>
      </div>`).join('') || '<div class="frow">まだ発話がありません</div>';
  }catch(e){}
}
async function labelV(btn){
  const row = btn.closest('.frow');
  const uid = row.querySelector('.vsel').value;
  if(!uid) return;
  await fetch('/voice',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:'ts='+row.dataset.ts+'&uid='+encodeURIComponent(uid)});
  loadV();
}
async function resetV(uid){
  await fetch('/voice_reset',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:'uid='+encodeURIComponent(uid)});
  loadV();
}
setInterval(loadV, 5000); setTimeout(loadV, 300);

// ---- 記憶ぜんぶ ----
let MT = 0;
const MEMORY_KIND_LABELS = {
  all: '全部',
  conversation: '会話',
  diary: '日記',
  notes: 'メモ/ナレッジ',
  video: '動画',
};
function memoryKind(){
  const kind = $('mk')?.value || 'all';
  localStorage.setItem('muchio_memory_kind', kind);
  return kind;
}
function memoryKindLabel(kind){
  return MEMORY_KIND_LABELS[kind] || MEMORY_KIND_LABELS.all;
}
async function loadM(){
  clearTimeout(MT);
  MT = setTimeout(async ()=>{
    const q = $('mq').value.trim();
    const kind = memoryKind();
    try{
      const d = await (await fetch('/memory?q='+encodeURIComponent(q)+'&kind='+encodeURIComponent(kind))).json();
      $('promptview').textContent = d.prompt || '';
      const note = q ? `検索「${esc(q)}」: ${d.total}件` : `最新の記憶 ${d.records.length}件`;
      $('memory').innerHTML = `<small>${note}</small>` + (d.records.length ? d.records.map(r=>{
        const when = r.date || (r.ts ? new Date(r.ts*1000).toLocaleString() : '');
        const tags = (r.tags||[]).map(t=>`<span class="mtag">${esc(t)}</span>`).join('');
        return `<div class="mrow" data-id="${esc(r.id)}">
          <div class="msrc">${esc(r.source)}<br>${esc(when)}<br>${esc(r.role||'')}</div>
          <div class="mtxt">${tags}${esc(r.text)}</div>
          <button type="button" class="ghost danger" onclick="delM(this)">消す</button>
        </div>`;
      }).join('') : '<div class="frow">記憶はありません</div>');
    }catch(e){}
  }, 180);
}
async function purgeCurrentMemory(){
  const q = $('mq').value.trim();
  const kind = memoryKind();
  if(!q){
    toast('先に検索語を入れてね', true);
    return;
  }
  if(!confirm(`「${q}」を${memoryKindLabel(kind)}から消す？（ファイルはバックアップされます）`)) return;
  await fetch('/purge',{
    method:'POST',
    headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:'word='+encodeURIComponent(q)+'&kind='+encodeURIComponent(kind),
  });
  loadM();
  loadW();
  toast(`「${q}」を${memoryKindLabel(kind)}から消しました`);
}
async function clearCurrentMemory(){
  const kind = memoryKind();
  if(!confirm(`${memoryKindLabel(kind)}の記憶を全部消す？（ファイルはバックアップされます）`)) return;
  const r = await fetch('/memory_clear',{
    method:'POST',
    headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:'kind='+encodeURIComponent(kind),
  });
  const d = await r.json().catch(()=>({}));
  loadM();
  loadW();
  toast(d.n ? `${memoryKindLabel(kind)}を${d.n}件消しました` : `${memoryKindLabel(kind)}を消しました`);
}
async function delM(btn){
  const row = btn.closest('.mrow');
  const text = row.querySelector('.mtxt').textContent.trim().slice(0, 60);
  if(!confirm('この記憶を消す？（バックアップされます）\n'+text)) return;
  await fetch('/memory_del',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:'id='+encodeURIComponent(row.dataset.id)});
  row.remove();
  loadW();
  toast('記憶を1件わすれました');
}
const mk = $('mk');
if(mk){
  mk.value = localStorage.getItem('muchio_memory_kind') || 'all';
}
loadM();

// ---- おぼえてることば ----
async function loadW(){
  try{ $('words').innerHTML = await (await fetch('/words')).text(); }catch(e){}
}
async function delW(el){
  // チップは1クリックでわすれる(確認なし。バックアップが毎回残るので取り消せる)
  const w = el.dataset.w;
  el.remove();
  await fetch('/purge', {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:'word='+encodeURIComponent(w)});
  toast('「'+w+'」をわすれます');
}
loadW();

async function loadNgHits(){
  const box = $('ng-hits');
  if(!box) return;
  try{
    const d = await (await fetch('/ng_hits')).json();
    const words = Array.isArray(d.words) ? d.words : [];
    if(!words.length){
      box.hidden = true;
      box.innerHTML = '';
      return;
    }
    box.hidden = false;
    box.innerHTML = '<div class="ng-hit-title">禁止ワードを含む保存データがあります</div>' +
      words.map(item=>`<div class="ng-hit-row">
        <div><b>${esc(item.word)}</b><small>会話 ${Number(item.conversation_count)||0}件 / 覚えた単語 ${Number(item.learned_count)||0}件</small></div>
        <button type="button" class="ghost danger" data-ng-delete="${esc(item.word)}">該当データを削除</button>
      </div>`).join('');
    box.querySelectorAll('[data-ng-delete]').forEach(btn=>{
      btn.addEventListener('click', ()=>deleteNgWord(btn));
    });
  }catch(e){
    box.hidden = true;
    box.innerHTML = '';
  }
}

async function deleteNgWord(btn){
  const word = btn.dataset.ngDelete || '';
  if(!word || !confirm(`「${word}」を含む会話・学習データを削除しますか？\\nバックアップは保存されます。`)) return;
  btn.disabled = true;
  try{
    const r = await fetch('/ng_word_delete', {
      method:'POST',
      headers:{'Content-Type':'application/x-www-form-urlencoded'},
      body:'word='+encodeURIComponent(word),
    });
    const d = await r.json().catch(()=>({}));
    if(!r.ok || !d.ok) throw new Error(d.error || 'delete failed');
    toast(`「${word}」を含む${d.deleted || 0}件を削除しました`);
    await Promise.all([loadNgHits(), loadM(), loadW()]);
  }catch(e){
    btn.disabled = false;
    toast('禁止ワードの削除に失敗しました', true);
  }
}

loadNgHits();
setInterval(loadNgHits, 5000);
