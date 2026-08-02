const $ = id => document.getElementById(id);
function toast(msg, err){
  const t = $('toast');
  t.textContent = msg; t.className = err ? 'on err' : 'on';
  clearTimeout(t._h); t._h = setTimeout(()=>{ t.className=''; }, 3500);
}

let BOOT = null;
const PERCENT_FIELDS = new Set(['reply_chance','friend_reply_chance','poke_chance','world_comment_chance','song_comment_chance']);
const CHECK_FIELDS = new Set(['think','kanji_mode','osc_proxy','greet_friends','diary','rule_polite','rule_trivia','rule_asks','rule_names',
  'weak_reply_guard','retry_bad_reply',
  'persona_character_enabled','persona_talk_enabled','persona_preferences_enabled','persona_free_text_enabled','persona_examples_enabled',
  'advanced_growth_enabled','advanced_sense_enabled','advanced_listener_enabled','advanced_rules_enabled','advanced_aizuchi_enabled','advanced_safety_enabled']);
CHECK_FIELDS.add('core_prompt_enabled');
CHECK_FIELDS.add('vrcx_enabled');
CHECK_FIELDS.add('memory_conversation_enabled');
CHECK_FIELDS.add('memory_words_enabled');
CHECK_FIELDS.add('memory_diary_enabled');
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
  renderSettingsTransfer(d.setting_categories || []);
  form.cfg_mtime.value = d.cfg_mtime || '';
  initPresets();
}

function renderSettingsTransfer(categories){
  const render = (targetId, prefix) => {
    const box = $(targetId);
    if(!box) return;
    box.innerHTML = categories.map(c =>
      `<label class="transfer-category"><input type="checkbox" data-transfer-category="${esc(c.id)}" data-transfer-group="${prefix}" checked> ${esc(c.label)}</label>`
    ).join('');
  };
  render('settings-export-categories', 'export');
  render('settings-import-categories', 'import');
  const selected = prefix => Array.from(document.querySelectorAll(`[data-transfer-group="${prefix}"]:checked`))
    .map(el=>el.dataset.transferCategory);
  const exportButton = $('settings-export');
  if(exportButton && !exportButton.dataset.bound){
    exportButton.dataset.bound = '1';
    exportButton.addEventListener('click', async ()=>{
      const cats = selected('export');
      if(!cats.length){ toast('書き出すカテゴリをひとつ選んでください', true); return; }
      try{
        const r = await fetch('/settings_export?categories='+encodeURIComponent(cats.join(',')));
        if(!r.ok) throw new Error('export');
        const blob = await r.blob();
        const url = URL.createObjectURL(blob), a = document.createElement('a');
        a.href = url; a.download = 'muchiko-settings.json'; a.click();
        setTimeout(()=>URL.revokeObjectURL(url), 1000);
        toast('選んだカテゴリを書き出しました');
      }catch(_){ toast('設定を書き出せませんでした', true); }
    });
  }
  const importButton = $('settings-import');
  if(importButton && !importButton.dataset.bound){
    importButton.dataset.bound = '1';
    importButton.addEventListener('click', async ()=>{
      const file = $('settings-import-file')?.files?.[0];
      const cats = selected('import');
      if(!file){ toast('読み込むJSONファイルを選んでください', true); return; }
      if(!cats.length){ toast('読み込むカテゴリをひとつ選んでください', true); return; }
      if(!confirm('選んだカテゴリを読み込みます。現在の設定はバックアップされます。よろしいですか？')) return;
      try{
        const documentData = JSON.parse(await file.text());
        const r = await fetch('/settings_import', {method:'POST', headers:{'Content-Type':'application/json'},
          body:JSON.stringify({document:documentData, categories:cats, cfg_mtime:$('cfg').cfg_mtime.value})});
        const d = await r.json();
        if(r.status === 409){ toast('べつの画面で設定が変わっています。ページを読み込み直してください', true); return; }
        if(!r.ok || !d.ok) throw new Error(d.err || 'import');
        await loadBootstrap();
        loadM();
        toast(`設定を読み込みました(${d.imported.length}項目)`);
      }catch(e){ toast('設定を読み込めませんでした: '+(e.message || ''), true); }
    });
  }
}
async function loadBootstrap(){
  try{
    const d = await (await fetch('/bootstrap')).json();
    applyBootstrap(d);
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
function setTab(t){
  document.body.className = 'tab-' + t;
  document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('on', b.dataset.tab===t));
  localStorage.setItem('muchio_tab', t);
}
document.querySelectorAll('.tab').forEach(b=>b.addEventListener('click', ()=>setTab(b.dataset.tab)));
const t0 = localStorage.getItem('muchio_tab');
setTab(t0 === 'a' || t0 === 'j' ? t0 : 's');

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
    loadM();
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
loadBootstrap();
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
