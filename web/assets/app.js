'use strict';

/* ------------------------------------------------------------------ state */
const state = {
  status: null,
  versions: [],
  currentVersionId: null,
  modsData: null,
  modData: null,
  currentConfig: null,
  activeFile: null,
  changes: new Map(),
  fieldErrors: new Map(),
  fieldByPath: new Map(),
  rawMode: false,
  rawText: '',
  rawDirty: false,
  saving: false,
  modQuery: '',
  modFilter: 'all',
  fileQuery: '',
  fieldQuery: '',
  onlyDirty: false,
  fieldLimit: 400,
  editorHash: '',
  allowLeave: false,
  routeSeq: 0,
  booted: false,
};

const els = {
  sidebar: document.getElementById('sidebar'),
  view: document.getElementById('view'),
  modal: document.getElementById('modal-root'),
  toasts: document.getElementById('toast-stack'),
};

/* ---------------------------------------------------------------- helpers */
const icon = (name, cls = '') => `<svg class="icon ${cls}" aria-hidden="true"><use href="#i-${name}"></use></svg>`;

function escapeHtml(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
const escapeAttr = escapeHtml;

function truncate(value, max = 160) {
  const text = String(value == null ? '' : value).replace(/\s+/g, ' ').trim();
  return text.length > max ? text.slice(0, max - 1).trimEnd() + '…' : text;
}

function initial(value) {
  const text = String(value || '?').trim();
  return escapeHtml((text[0] || '?').toUpperCase());
}

function num(value) {
  if (value == null) return '0';
  return Number(value).toLocaleString('zh-CN');
}

function deepEqual(a, b) {
  if (a === b) return true;
  if (typeof a !== typeof b) return false;
  if (a && b && typeof a === 'object') {
    if (Array.isArray(a) !== Array.isArray(b)) return false;
    if (Array.isArray(a)) {
      if (a.length !== b.length) return false;
      return a.every((v, i) => deepEqual(v, b[i]));
    }
    const ak = Object.keys(a);
    const bk = Object.keys(b);
    if (ak.length !== bk.length) return false;
    return ak.every(k => deepEqual(a[k], b[k]));
  }
  return Number.isNaN(a) && Number.isNaN(b);
}

function debounce(fn, wait = 90) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

function loaderChip(loader) {
  const text = String(loader || '');
  let cls = 'mint';
  if (/Forge/i.test(text) && !/Neo/i.test(text)) cls = 'amber';
  else if (/NeoForge/i.test(text)) cls = 'violet';
  else if (/Fabric/i.test(text)) cls = 'mint';
  else if (/Quilt/i.test(text)) cls = 'violet';
  else if (/OptiFine/i.test(text)) cls = 'blue';
  else if (/原版/.test(text) || /Vanilla/i.test(text)) cls = '';
  else if (/未知/.test(text)) cls = 'amber';
  return `<span class="chip ${cls}">${escapeHtml(text || '未知')}</span>`;
}

function formatChip(fmt) {
  const text = String(fmt || '');
  const low = text.toLowerCase();
  let cls = '';
  if (low.includes('toml')) cls = 'mint';
  else if (low.includes('json')) cls = 'blue';
  else if (low.includes('yaml')) cls = 'violet';
  else if (low.includes('properties')) cls = 'amber';
  else if (low.includes('cfg')) cls = 'amber';
  return `<span class="chip ${cls}">${escapeHtml(text || '文件')}</span>`;
}

function iconUrl(versionId, key) {
  return `/api/icon?version=${encodeURIComponent(versionId)}&key=${encodeURIComponent(key)}`;
}
function versionIconUrl(versionId) {
  return `/api/version-icon?version=${encodeURIComponent(versionId)}`;
}

function modAvatar(mod, versionId, extraClass = '') {
  const v = versionId || state.currentVersionId || '';
  if (mod && mod.icon && v && mod.key && mod.key !== '__other__') {
    return `<div class="mod-icon ${extraClass}" data-icon-wrap><span class="fallback">${initial(mod.name)}</span><img src="${iconUrl(v, mod.key)}" alt="" loading="lazy" data-mod-img></div>`;
  }
  return `<div class="mod-icon noimg ${extraClass}"><span class="fallback">${initial(mod ? mod.name : '?')}</span></div>`;
}

function versionAvatar(version, extraClass = '') {
  if (!version) return `<div class="version-icon ${extraClass}">?</div>`;
  if (version.icon) {
    return `<div class="version-icon ${extraClass}" data-icon-wrap><span class="fallback" style="display:none">${initial(version.name)}</span><img src="${versionIconUrl(version.id)}" alt="" loading="lazy" data-version-img></div>`;
  }
  return `<div class="version-icon ${extraClass}">${initial(version.name)}</div>`;
}

function currentVersion() {
  return state.versions.find(v => v.id === state.currentVersionId) || (state.modsData && state.modsData.version) || null;
}

function currentMod() {
  return state.modData ? state.modData.mod : null;
}

async function api(path, options = {}) {
  const opts = Object.assign({ headers: {} }, options);
  if (opts.body && typeof opts.body !== 'string') {
    opts.body = JSON.stringify(opts.body);
    opts.headers['Content-Type'] = 'application/json';
  }
  let response;
  try {
    response = await fetch(path, opts);
  } catch (error) {
    const err = new Error('无法连接本地服务，请确认启动窗口仍在运行');
    err.status = 0;
    throw err;
  }
  let payload = null;
  try { payload = await response.json(); } catch (_) { payload = null; }
  if (!response.ok) {
    const err = new Error((payload && (payload.error || payload.message)) || `请求失败（${response.status}）`);
    err.status = response.status;
    err.payload = payload;
    throw err;
  }
  return payload || {};
}

/* ---------------------------------------------------------------- toasts */
function toast(message, type = 'success', sub = '') {
  const wrap = document.createElement('div');
  wrap.className = `toast ${type}`;
  const iconName = type === 'success' ? 'check' : type === 'error' ? 'alert' : type === 'warn' ? 'alert' : 'info';
  wrap.innerHTML = `<span class="ti">${icon(iconName)}</span><div class="tx">${escapeHtml(message)}${sub ? `<small>${escapeHtml(sub)}</small>` : ''}</div>`;
  els.toasts.appendChild(wrap);
  setTimeout(() => {
    wrap.classList.add('out');
    setTimeout(() => wrap.remove(), 240);
  }, type === 'error' ? 6200 : 4100);
}

/* ---------------------------------------------------------------- modal */
function showModal({ title, sub = '', iconName = 'info', danger = false, body = '', actions = [], input = null }) {
  return new Promise(resolve => {
    const actionsHtml = actions.map((action, index) => (
      `<button class="btn ${action.className || (index === actions.length - 1 ? 'btn-primary' : '')}" data-modal-action="${escapeAttr(action.value)}">${escapeHtml(action.label)}</button>`
    )).join('');
    els.modal.innerHTML = `
      <div class="modal-backdrop" data-modal-backdrop>
        <div class="modal" role="dialog" aria-modal="true">
          <div class="modal-head">
            <span class="mi ${danger ? 'danger' : ''}">${icon(iconName)}</span>
            <div><div class="modal-title">${escapeHtml(title)}</div>${sub ? `<div class="modal-sub">${escapeHtml(sub)}</div>` : ''}</div>
            <button class="modal-close" data-modal-action="__cancel" aria-label="关闭">${icon('close')}</button>
          </div>
          <div class="modal-body">${body}${input ? `<input class="modal-input" id="modal-input" value="${escapeAttr(input.value || '')}" placeholder="${escapeAttr(input.placeholder || '')}" autocomplete="off" spellcheck="false">${input.hint ? `<div class="modal-hint">${escapeHtml(input.hint)}</div>` : ''}` : ''}</div>
          <div class="modal-actions">
            ${actionsHtml || `<button class="btn" data-modal-action="__cancel">关闭</button>`}
          </div>
        </div>
      </div>`;
    const cleanup = value => {
      els.modal.innerHTML = '';
      document.removeEventListener('keydown', onKey);
      resolve(value);
    };
    const onKey = event => {
      if (event.key === 'Escape') cleanup(input ? null : '__cancel');
      if (event.key === 'Enter' && input) {
        const active = document.activeElement;
        if (active && active.id === 'modal-input') {
          const value = active.value.trim();
          if (value) cleanup(value);
        }
      }
    };
    document.addEventListener('keydown', onKey);
    const backdrop = els.modal.querySelector('[data-modal-backdrop]');
    if (backdrop) {
      backdrop.addEventListener('mousedown', event => {
        if (event.target === backdrop) cleanup(null);
      });
    }
    els.modal.querySelectorAll('[data-modal-action]').forEach(button => {
      button.addEventListener('click', () => {
        const value = button.dataset.modalAction;
        if (value === '__cancel') return cleanup(input ? null : '__cancel');
        if (input) {
          const field = document.getElementById('modal-input');
          const text = field ? field.value.trim() : '';
          if (!text) { field && field.classList.add('invalid'); field && field.focus(); return; }
          return cleanup(text);
        }
        cleanup(value);
      });
    });
    if (input) {
      const field = document.getElementById('modal-input');
      if (field) {
        field.focus();
        field.select();
      }
    }
  });
}

async function confirmDialog({ title, message, confirmText = '继续', danger = false, iconName = 'alert' }) {
  const result = await showModal({
    title,
    body: `<p>${message}</p>`,
    iconName,
    danger,
    actions: [
      { label: '取消', value: '__cancel' },
      { label: confirmText, value: 'ok', className: danger ? 'btn-danger' : 'btn-primary' },
    ],
  });
  return result === 'ok';
}

/* ---------------------------------------------------------------- sidebar */
function renderSidebar(active = 'home') {
  const version = currentVersion();
  const launcher = (state.status && state.status.launcher) || '';
  const detected = !!(state.status && state.status.detected);
  els.sidebar.innerHTML = `
    <a class="brand" href="#/" data-action="go-home">
      <span class="brand-mark">${icon('cube')}</span>
      <span class="brand-text">
        <div class="brand-name">Craft<span>Tune</span></div>
        <div class="brand-sub">mod config studio</div>
      </span>
    </a>
    <div class="side-label">工作台</div>
    <nav class="side-nav">
      <button class="nav-item ${active === 'home' || active === 'mods' || active === 'editor' ? 'active' : ''}" data-action="go-home">
        ${icon('grid')}<span>版本库</span><span class="nav-kbd">01</span>
      </button>
      <button class="nav-item" data-action="help">
        ${icon('info')}<span>使用说明</span><span class="nav-kbd">?</span>
      </button>
      <button class="nav-item" data-action="backups">
        ${icon('save')}<span>安全备份</span>
      </button>
    </nav>
    <div class="header-mini">
      <button class="nav-item" data-action="go-home" title="版本库">${icon('grid')}</button>
      <button class="nav-item" data-action="backups" title="安全备份">${icon('save')}</button>
      <button class="nav-item" data-action="help" title="使用说明">${icon('info')}</button>
    </div>
    ${version ? `
      <div class="side-version">
        <div class="sv-top">
          <div class="sv-icon">${version.icon ? `<img src="${versionIconUrl(version.id)}" alt="" data-version-img>` : initial(version.name)}</div>
          <div style="min-width:0"><div class="sv-name" title="${escapeAttr(version.name)}">${escapeHtml(version.name)}</div><div class="sv-meta">${escapeHtml(version.game_version)} · ${escapeHtml(version.loader)}</div></div>
        </div>
        <div class="sv-stats"><span><b>${num(version.mod_count)}</b> 模组</span><span><b>${num(version.config_count)}</b> 配置</span></div>
        <button data-action="switch-version">${icon('refresh')} 切换游戏版本</button>
      </div>
    ` : ''}
    <div class="side-spacer"></div>
    <div class="side-tip">
      <strong>安全第一</strong><br>
      每次保存都会自动备份原文件，参数修改可随时撤销。
    </div>
    <div class="side-footer">
      <span class="dot-live"></span>${detected ? '已检测到启动器目录' : '等待选择启动器目录'}
      <div class="path" title="${escapeAttr(launcher)}">${escapeHtml(launcher || '未选择 .minecraft 目录')}</div>
    </div>`;
}

/* ------------------------------------------------------------------ home */
function renderHome() {
  renderSidebar('home');
  const versions = state.versions || [];
  const launcher = (state.status && state.status.launcher) || '';
  els.view.innerHTML = `
    <section class="home fade-up">
      <div class="home-hero">
        <div class="eyebrow">Minecraft Java · Mod Config Studio</div>
        <h1>让每一个参数，<br><span class="grad">都听你的。</span></h1>
        <p class="home-lead">
          从整合包的模组列表中找到配置文件，把晦涩的键值变成清晰的开关、数字和选项。
          <b>自动关联模组、保留注释格式、保存前备份</b>，安心调出最顺手的整合包。
        </p>
        <div class="launcher-card">
          <div class="launcher-icon">${icon(launcher ? 'folder' : 'alert')}</div>
          <div class="launcher-body">
            <div class="launcher-label">${launcher ? '当前 Minecraft 目录' : '尚未找到 Minecraft 目录'}</div>
            <div class="launcher-path" title="${escapeAttr(launcher)}">${escapeHtml(launcher || '请选择包含 versions 文件夹的 .minecraft 目录')}</div>
          </div>
          <div class="launcher-actions">
            <button class="btn btn-sm" data-action="manual-launcher">${icon('folder')} 指定目录</button>
            <button class="btn btn-sm btn-primary" data-action="choose-folder">${icon('search')} 浏览</button>
          </div>
        </div>
      </div>

      <div class="section-head">
        <div>
          <div class="section-title">选择游戏版本</div>
          <div class="section-sub">不同版本拥有独立的 mods 与 config 目录 · 共 ${versions.length} 个实例</div>
        </div>
        <div class="section-actions">
          <button class="btn btn-sm btn-ghost" data-action="refresh-all">${icon('refresh')} 重新扫描</button>
        </div>
      </div>

      ${versions.length ? `<div class="version-grid">${versions.map(renderVersionCard).join('')}</div>` : renderHomeEmpty(launcher)}
      ${renderSteps()}
    </section>`;
}

function renderHomeEmpty(launcher) {
  return `
    <div class="empty-panel">
      <div class="empty-icon">${icon('package')}</div>
      <div class="empty-title">${launcher ? '这个目录里还没有游戏版本' : '先告诉我你的整合包在哪里'}</div>
      <div class="empty-text">${launcher
        ? '没有在 versions 目录中找到可用的版本实例。请确认整合包已经安装，或换一个 .minecraft 目录。'
        : '选择 .minecraft 文件夹后，CraftTune 会自动读取 versions、mods 和 config，不需要移动任何文件。'}</div>
      <div class="empty-actions">
        <button class="btn btn-primary" data-action="choose-folder">${icon('folder')} 选择 .minecraft 文件夹</button>
        <button class="btn" data-action="manual-launcher">手动输入路径</button>
      </div>
    </div>`;
}

function renderVersionCard(version) {
  return `
    <button class="version-card" data-action="enter-version" data-version="${escapeAttr(version.id)}">
      <div class="version-card-top">
        <div class="version-identity">
          ${versionAvatar(version)}
          <div style="min-width:0">
            <div class="version-name" title="${escapeAttr(version.name)}">${escapeHtml(version.name)}</div>
            <div class="version-sub">
              <span class="chip blue">${escapeHtml(version.game_version)}</span>
              ${loaderChip(version.loader)}
              ${version.disabled_mod_count ? `<span class="chip amber">${version.disabled_mod_count} 个已禁用</span>` : ''}
            </div>
          </div>
        </div>
        <span class="version-arrow">${icon('chevron')}</span>
      </div>
      <div class="version-stats">
        <div class="vstat"><div class="num">${num(version.mod_count)}</div><div class="lbl">模组</div></div>
        <div class="vstat"><div class="num">${num(version.config_count)}</div><div class="lbl">配置文件</div></div>
        <div class="vstat"><div class="num">${version.has_json ? '✓' : '—'}<small>${version.has_json ? '已识别' : '无清单'}</small></div><div class="lbl">版本清单</div></div>
      </div>
      <div class="version-foot">
        <span class="local">versions/${escapeHtml(version.name)}</span>
        <span>${version.isolated ? '版本隔离' : '共享目录'}</span>
      </div>
    </button>`;
}

function renderSteps() {
  return `
    <div class="step-strip">
      <div class="step"><span class="idx">01</span><div><div class="t">选择游戏版本</div><div class="d">读取每个版本的模组清单与配置文件。</div></div></div>
      <div class="step"><span class="idx">02</span><div><div class="t">找到目标模组</div><div class="d">按名称搜索，配置文件已自动归类到模组。</div></div></div>
      <div class="step"><span class="idx">03</span><div><div class="t">调整并保存</div><div class="d">开关、数字、文本与数组均可视化编辑。</div></div></div>
    </div>`;
}

/* ------------------------------------------------------------------ mods */
async function loadModsPage(versionId) {
  const seq = ++state.routeSeq;
  renderSidebar('mods');
  showPageLoading('正在读取模组与配置…');
  try {
    if (!state.versions.length) await loadVersions();
    const data = await api(`/api/mods?version=${encodeURIComponent(versionId)}`);
    if (seq !== state.routeSeq) return;
    state.currentVersionId = versionId;
    state.modsData = data;
    state.modData = null;
    state.currentConfig = null;
    state.modQuery = '';
    state.modFilter = 'all';
    renderSidebar('mods');
    renderModsPage();
  } catch (error) {
    if (seq !== state.routeSeq) return;
    renderErrorPage(error, () => loadModsPage(versionId));
  }
}

function renderModsPage() {
  const data = state.modsData;
  if (!data) return;
  const version = data.version;
  const stats = data.stats || {};
  els.view.innerHTML = `
    <div class="fade-up">
      <div class="crumb">
        <button data-action="go-home">版本库</button>
        <span class="sep">/</span>
        <span class="current">${escapeHtml(version.name)}</span>
      </div>
      <section class="version-banner">
        ${versionAvatar(version)}
        <div class="vb-body">
          <h1>${escapeHtml(version.name)}</h1>
          <div class="meta">
            <span class="chip blue">${escapeHtml(version.game_version)}</span>
            ${loaderChip(version.loader)}
            <span class="chip">${escapeHtml(version.isolated ? '版本隔离' : '共享目录')}</span>
            ${stats.disabled_mods ? `<span class="chip amber">${stats.disabled_mods} 个模组已禁用</span>` : ''}
          </div>
        </div>
        <div class="stats">
          <div><div class="num">${num(stats.mods)}</div><div class="lbl">模组</div></div>
          <div><div class="num">${num(stats.configs)}</div><div class="lbl">配置</div></div>
          <div><div class="num">${num(stats.orphan_configs)}</div><div class="lbl">未归属</div></div>
        </div>
        <button class="btn btn-sm" data-action="refresh-mods" title="重新读取 mods 与 config">${icon('refresh')} 刷新</button>
      </section>

      <div class="toolbar">
        <div class="search-box">
          ${icon('search')}
          <input id="mod-search" type="search" placeholder="搜索模组名称、ID 或描述…" value="${escapeAttr(state.modQuery)}" autocomplete="off" spellcheck="false">
          ${state.modQuery ? `<button class="clear-input" data-action="clear-mod-search" aria-label="清空">${icon('close')}</button>` : ''}
        </div>
        <div class="filter-group">
          <button class="filter-chip ${state.modFilter === 'all' ? 'active' : ''}" data-action="set-mod-filter" data-filter="all">全部</button>
          <button class="filter-chip ${state.modFilter === 'configured' ? 'active' : ''}" data-action="set-mod-filter" data-filter="configured">有配置</button>
          <button class="filter-chip ${state.modFilter === 'empty' ? 'active' : ''}" data-action="set-mod-filter" data-filter="empty">无配置</button>
        </div>
        <div class="toolbar-note">配置文件按模组 ID / 文件名自动关联</div>
      </div>

      <div class="mod-grid" id="mod-grid"></div>
    </div>`;
  renderModGrid();
}

function renderModGrid() {
  const container = document.getElementById('mod-grid');
  if (!container || !state.modsData) return;
  const query = state.modQuery.trim().toLowerCase();
  let mods = state.modsData.mods.slice();
  if (query) {
    mods = mods.filter(mod => {
      const hay = [mod.name, mod.id, mod.description, mod.filename, ...(mod.ids || [])].join(' ').toLowerCase();
      return hay.includes(query);
    });
  }
  if (state.modFilter === 'configured') mods = mods.filter(mod => mod.config_count > 0);
  if (state.modFilter === 'empty') mods = mods.filter(mod => !mod.config_count);
  if (!query && state.modFilter === 'all') {
    mods.sort((a, b) => {
      const av = a.is_virtual || a.key === '__other__' ? 1 : 0;
      const bv = b.is_virtual || b.key === '__other__' ? 1 : 0;
      if (av !== bv) return av - bv;
      return String(a.name).localeCompare(String(b.name), 'zh-CN');
    });
  }
  if (!mods.length) {
    container.innerHTML = `<div class="mod-empty">没有符合条件的模组。试试清空搜索，或切换筛选条件。</div>`;
    return;
  }
  container.innerHTML = mods.map(mod => renderModCard(mod)).join('');
}

function renderModCard(mod) {
  const isVirtual = mod.is_virtual || mod.key === '__other__';
  const disabled = mod.enabled === false;
  const format = mod.format && mod.format !== 'unknown' && !isVirtual
    ? ({ fabric: 'Fabric', forge: 'Forge', neoforge: 'NeoForge', quilt: 'Quilt', legacy: 'Legacy' }[String(mod.format).toLowerCase()] || mod.format)
    : '';
  return `
    <button class="mod-card ${isVirtual ? 'is-virtual' : ''} ${disabled ? 'is-disabled' : ''}" data-action="open-mod" data-key="${escapeAttr(mod.key)}">
      ${modAvatar(mod, state.currentVersionId)}
      <div class="mc-body">
        <div class="mc-name" title="${escapeAttr(mod.name)}">${escapeHtml(mod.name)}</div>
        <div class="mc-id" title="${escapeAttr(mod.id)}">${escapeHtml(isVirtual ? '未匹配到具体模组' : (mod.id || 'unknown'))}</div>
        <div class="mc-foot">
          <span class="cfgs ${mod.config_count ? '' : 'zero'}">${mod.config_count ? `${num(mod.config_count)} 个配置` : '无配置'}</span>
          ${format ? `<span>${escapeHtml(format)}</span>` : ''}
          ${disabled ? '<span style="color:var(--amber)">已禁用</span>' : ''}
          ${isVirtual ? '<span>仍可安全编辑</span>' : ''}
        </div>
      </div>
      <span class="go">${icon('chevron')}</span>
    </button>`;
}

/* ---------------------------------------------------------------- editor */
async function loadModPage(versionId, modKey) {
  const seq = ++state.routeSeq;
  renderSidebar('editor');
  showPageLoading('正在读取模组配置文件…');
  try {
    if (!state.versions.length) await loadVersions();
    const data = await api(`/api/mod?version=${encodeURIComponent(versionId)}&key=${encodeURIComponent(modKey)}`);
    if (seq !== state.routeSeq) return;
    state.currentVersionId = versionId;
    state.modsData = null;
    state.modData = data;
    state.activeFile = null;
    state.currentConfig = null;
    state.changes = new Map();
    state.fieldErrors = new Map();
    state.rawMode = false;
    state.rawText = '';
    state.rawDirty = false;
    state.fileQuery = '';
    state.fieldQuery = '';
    state.onlyDirty = false;
    state.editorHash = location.hash;
    const configs = data.configs || [];
    if (configs.length) {
      const preferred = configs.find(item => item.field_count > 0) || configs[0];
      await loadConfigFile(preferred.path, { skipGuard: true, seq });
    } else {
      renderSidebar('editor');
      renderEditorPage();
    }
  } catch (error) {
    if (seq !== state.routeSeq) return;
    renderErrorPage(error, () => loadModPage(versionId, modKey));
  }
}

async function loadConfigFile(filePath, options = {}) {
  if (!state.modData) return;
  if (!options.skipGuard && isDirty()) {
    const ok = await confirmDialog({
      title: '放弃未保存的修改？',
      message: '切换配置文件会丢弃当前尚未保存的参数修改。已保存的内容不受影响。',
      confirmText: '放弃并切换',
      danger: true,
    });
    if (!ok) return;
    clearDirty();
  }
  const seq = options.seq || ++state.routeSeq;
  state.activeFile = filePath;
  state.currentConfig = null;
  state.changes = new Map();
  state.fieldErrors = new Map();
  state.rawMode = false;
  state.rawDirty = false;
  renderSidebar('editor');
  renderEditorPage({ loadingConfig: true });
  try {
    const data = await api(`/api/config?version=${encodeURIComponent(state.currentVersionId)}&key=${encodeURIComponent(state.modData.mod.key)}&file=${encodeURIComponent(filePath)}`);
    if (seq !== state.routeSeq) return;
    state.currentConfig = data;
    state.rawText = data.raw;
    state.rawDirty = false;
    state.fieldByPath = new Map((data.fields || []).map(field => [field.path, field]));
    state.changes.clear();
    state.fieldErrors.clear();
    state.fieldQuery = '';
    state.onlyDirty = false;
    state.fieldLimit = 400;
    state.rawMode = data.raw_only || ((data.fields || []).length === 0 && (data.format === 'text' || data.format === 'snbt' || data.format === 'xml'));
    const activeMeta = (state.modData.configs || []).find(item => item.path === data.file.path);
    if (activeMeta) {
      activeMeta.field_count = (data.fields || []).length;
      activeMeta.warnings = (data.warnings || []).slice(0, 2);
      activeMeta.detected_format = data.format_label;
    }
    renderSidebar('editor');
    renderEditorPage();
  } catch (error) {
    if (seq !== state.routeSeq) return;
    state.currentConfig = null;
    renderEditorPage({ error });
  }
}

function renderEditorPage(options = {}) {
  const data = state.modData;
  if (!data) return;
  const mod = data.mod;
  const configs = data.configs || [];
  const active = configs.find(item => item.path === state.activeFile) || null;
  els.view.innerHTML = `
    <div class="editor-page fade-up">
      <div class="editor-top">
        <div class="crumb">
          <button data-action="go-home">版本库</button>
          <span class="sep">/</span>
          <button data-action="back-mods">${escapeHtml(data.version.name)}</button>
          <span class="sep">/</span>
          <span class="current">${escapeHtml(mod.name)}</span>
        </div>
        <button class="btn btn-sm btn-ghost" data-action="back-mods">${icon('arrow-left')} 返回模组列表</button>
      </div>

      <section class="mod-hero">
        ${modAvatar(mod, state.currentVersionId)}
        <div class="mh-body">
          <h1 title="${escapeAttr(mod.name)}">${escapeHtml(mod.name)}</h1>
          <div class="mh-meta">
            ${data.is_virtual ? '' : `<span class="chip">${escapeHtml(mod.id || 'unknown')}</span>`}
            ${mod.version ? `<span class="chip">v${escapeHtml(mod.version)}</span>` : ''}
            ${!data.is_virtual && mod.format && mod.format !== 'unknown' ? formatChip(mod.format) : ''}
            <span>${configs.length} 个配置文件</span>
            ${mod.enabled === false ? '<span class="chip amber">已禁用</span>' : ''}
            ${data.is_virtual ? '<span class="chip amber">未归属配置</span>' : ''}
            ${data.total_fields ? `<span>约 ${num(data.total_fields)} 个参数</span>` : ''}
          </div>
        </div>
        <div class="mh-actions">
          <button class="btn btn-sm" data-action="reveal-mod-config">${icon('folder')} 配置目录</button>
          <button class="btn btn-sm" data-action="refresh-mods">${icon('refresh')} 刷新</button>
        </div>
      </section>

      <div class="editor-grid">
        <aside class="file-panel">
          <div class="panel-head">
            <div class="ph-top"><span class="panel-title">配置文件</span><span class="panel-count">${configs.length}</span></div>
            <div class="file-filter">${icon('search')}<input id="file-filter" type="search" placeholder="筛选文件…" value="${escapeAttr(state.fileQuery)}" autocomplete="off" spellcheck="false"></div>
          </div>
          <div class="file-list" id="file-list"></div>
        </aside>
        <section class="config-panel" id="config-panel"></section>
      </div>
    </div>`;
  renderFileList();
  if (options.error) renderConfigError(options.error);
  else if (options.loadingConfig) renderConfigLoading();
  else renderConfigPanel();
}

function renderFileList() {
  const container = document.getElementById('file-list');
  if (!container || !state.modData) return;
  const query = state.fileQuery.trim().toLowerCase();
  const configs = (state.modData.configs || []).filter(item => {
    if (!query) return true;
    return `${item.path} ${item.name} ${item.format_label || ''}`.toLowerCase().includes(query);
  });
  if (!configs.length) {
    container.innerHTML = `<div class="file-empty">没有匹配的配置文件</div>`;
    return;
  }
  container.innerHTML = configs.map(item => {
    const warn = item.warnings && item.warnings.length;
    return `
      <button class="file-item ${item.path === state.activeFile ? 'active' : ''}" data-action="open-file" data-file="${escapeAttr(item.path)}">
        <div class="fi-name">${icon('file')}<span title="${escapeAttr(item.path)}">${escapeHtml(item.name)}</span></div>
        <div class="fi-sub">
          <span>${escapeHtml(item.format_label || item.format || '')}</span>
          <span>·</span>
          <span>${item.field_count == null ? '— 参数' : `${num(item.field_count || 0)} 参数`}</span>
          ${warn ? `<span class="fi-warn" title="${escapeAttr((item.warnings || []).join(' / '))}">● 提示</span>` : ''}
        </div>
      </button>`;
  }).join('');
}

function renderConfigLoading() {
  const container = document.getElementById('config-panel');
  if (!container) return;
  container.innerHTML = `<div class="loading-block"><div class="spinner"></div>正在解析配置参数…</div>`;
}

function renderConfigError(error) {
  const container = document.getElementById('config-panel');
  if (!container) return;
  container.innerHTML = `
    <div class="config-empty">
      <div class="empty-icon">${icon('alert')}</div>
      <div class="empty-title">无法读取这个配置文件</div>
      <div class="empty-text">${escapeHtml(error.message || String(error))}</div>
      <div class="empty-actions"><button class="btn" data-action="reload-config">${icon('refresh')} 重试</button></div>
    </div>`;
}

function renderConfigPanel() {
  const container = document.getElementById('config-panel');
  if (!container) return;
  const config = state.currentConfig;
  if (!config) {
    container.innerHTML = `<div class="config-empty">
      <div class="empty-icon">${icon('sliders')}</div>
      <div class="empty-title">选择一个配置文件</div>
      <div class="empty-text">从左侧选择配置文件后，参数会以开关、输入框和下拉选项展示。</div>
    </div>`;
    return;
  }
  const warnings = config.warnings || [];
  const activeMeta = (state.modData.configs || []).find(item => item.path === state.activeFile);
  const warningHtml = warnings.length ? `
    <div class="warn-banner">${icon('alert')}
      <div><div>解析时发现 ${warnings.length} 条提示，修改前建议先备份。</div>
      <ul>${warnings.slice(0, 3).map(w => `<li>${escapeHtml(truncate(w, 220))}</li>`).join('')}</ul></div>
    </div>` : '';
  const rawButton = `<button class="btn btn-sm ${state.rawMode ? 'btn-primary' : ''}" data-action="toggle-raw">${icon('code')} ${state.rawMode ? '参数视图' : '源码模式'}</button>`;

  if (state.rawMode) {
    container.innerHTML = `
      <div class="config-toolbar">
        <div class="ct-file">
          <div class="name">${icon('file')}<span>${escapeHtml(config.file.name)}</span>${formatChip(config.format_label)}</div>
          <div class="path">${escapeHtml(config.file.path)} · ${escapeHtml(config.encoding)} · ${escapeHtml(config.size_label)}</div>
          <div class="ct-meta">
            <span class="chip">源码编辑</span>
            ${activeMeta && activeMeta.field_count ? `<span class="chip mint">${num(activeMeta.field_count)} 个可识别参数</span>` : ''}
            ${config.has_bom ? '<span class="chip amber">UTF-8 BOM</span>' : ''}
          </div>
        </div>
        <div class="ct-actions">
          ${rawButton}
          <button class="btn btn-sm" data-action="reveal-config">${icon('external')} 打开位置</button>
          <button class="btn btn-sm" data-action="reload-config">${icon('refresh')} 重新载入</button>
        </div>
      </div>
      ${warningHtml}
      <div class="raw-wrap">
        <div class="raw-head"><span class="raw-dot"></span>直接编辑原始文件 · 自动保留编码与换行 · 保存前自动备份</div>
        <textarea class="raw-editor" id="raw-editor" spellcheck="false" autocomplete="off">${escapeHtml(state.rawText)}</textarea>
      </div>
      ${renderSaveDock()}`;
    return;
  }

  const fields = config.fields || [];
  container.innerHTML = `
    <div class="config-toolbar">
      <div class="ct-file">
        <div class="name">${icon('file')}<span>${escapeHtml(config.file.name)}</span>${formatChip(config.format_label)}</div>
        <div class="path">${escapeHtml(config.file.path)} · ${escapeHtml(config.encoding)} · ${escapeHtml(config.size_label)} · ${config.line_count} 行</div>
        <div class="ct-meta">
          <span class="chip mint">${num(fields.length)} 个参数</span>
          ${config.has_bom ? '<span class="chip amber">UTF-8 BOM</span>' : ''}
          ${activeMeta && activeMeta.warnings && activeMeta.warnings.length ? '<span class="chip amber">读取提示</span>' : ''}
        </div>
      </div>
      <div class="ct-actions">
        ${rawButton}
        <button class="btn btn-sm" data-action="reveal-config">${icon('external')} 打开位置</button>
        <button class="btn btn-sm" data-action="reload-config">${icon('refresh')} 重新载入</button>
      </div>
    </div>
    ${warningHtml}
    <div class="param-toolbar">
      <div class="search-box">${icon('search')}<input id="param-search" type="search" placeholder="筛选参数、说明…" value="${escapeAttr(state.fieldQuery)}" autocomplete="off" spellcheck="false"></div>
      <label class="toggle-label"><input type="checkbox" id="only-dirty" ${state.onlyDirty ? 'checked' : ''}> 只看已修改</label>
      <span class="param-count" id="param-count"></span>
    </div>
    <div id="field-groups"></div>
    ${fields.length === 0 ? `<div class="config-empty"><div class="empty-icon">${icon('code')}</div><div class="empty-title">没有识别到结构化参数</div><div class="empty-text">这个文件可能是特殊格式。切换到源码模式，仍然可以安全地编辑原始内容。</div><div class="empty-actions"><button class="btn btn-primary" data-action="toggle-raw">${icon('code')} 源码模式</button></div></div>` : ''}
    ${renderSaveDock()}`;
  renderFields();
  updateDirtyUI();
}

function renderSaveDock() {
  const count = dirtyCount();
  return `
    <div class="save-dock" id="save-dock" ${count ? '' : 'hidden'}>
      <div>
        <div class="sd-count"><b id="dirty-count">${count}</b> 项未保存的修改</div>
        <div class="sd-sub" id="save-hint">保存时会自动备份原文件</div>
      </div>
      <div class="spacer"></div>
      <div class="sd-btns">
        <button class="btn btn-sm" data-action="discard-changes">${icon('undo')} 撤销全部</button>
        <button class="btn btn-sm btn-primary" data-action="save-config" id="save-button">${icon('save')} 保存到文件</button>
      </div>
    </div>`;
}

/* ---------------------------------------------------------------- fields */
const typeLabel = {
  boolean: '布尔',
  integer: '整数',
  float: '小数',
  string: '文本',
  array: '数组',
  object: '对象',
  null: '空值',
};

function groupFields(fields) {
  const groups = new Map();
  for (const field of fields) {
    const name = field.section || '基础参数';
    if (!groups.has(name)) groups.set(name, []);
    groups.get(name).push(field);
  }
  return groups;
}

function renderFields() {
  const container = document.getElementById('field-groups');
  if (!container || !state.currentConfig) return;
  const query = state.fieldQuery.trim().toLowerCase();
  const filtered = (state.currentConfig.fields || []).filter(field => {
    if (state.onlyDirty && !state.changes.has(field.path)) return false;
    if (!query) return true;
    const hay = [field.key, field.label, field.section, field.description, field.value].join(' ').toLowerCase();
    return hay.includes(query);
  });
  const fields = filtered.slice(0, state.fieldLimit);
  const groups = groupFields(fields);
  if (!fields.length) {
    container.innerHTML = `<div class="config-empty" style="padding:34px 20px"><div class="empty-title">没有匹配的参数</div><div class="empty-text">${state.onlyDirty ? '当前没有未保存的修改。' : '换个关键词试试，或清空筛选。'}</div></div>`;
    updateParamCount(0, 0);
    return;
  }
  const moreHtml = filtered.length > fields.length ? `
    <div class="show-more-wrap">
      <span>已显示 ${fields.length} / ${filtered.length} 个参数</span>
      <button class="btn btn-sm" data-action="show-more-fields">${icon('chevron')} 再显示 400 个</button>
    </div>` : '';
  container.innerHTML = [...groups.entries()].map(([name, items], index) => `
    <section class="group-card">
      <div class="group-head">
        <span class="g-icon">${icon(index === 0 ? 'sliders' : 'chevron')}</span>
        <span class="g-name">${escapeHtml(name)}</span>
        <span class="g-count">${items.length} 项</span>
      </div>
      <div>${items.map(field => renderFieldRow(field)).join('')}</div>
    </section>`).join('') + moreHtml;
  updateParamCount(filtered.length, groups.size);
  updateDirtyUI();
}

function updateParamCount(count, groups) {
  const el = document.getElementById('param-count');
  if (!el) return;
  const total = (state.currentConfig && state.currentConfig.fields || []).length;
  el.textContent = `${count} / ${total} 个参数${groups ? ` · ${groups} 组` : ''}`;
}

function renderFieldRow(field) {
  const changed = state.changes.has(field.path);
  const value = changed ? state.changes.get(field.path) : field.value;
  const error = state.fieldErrors.get(field.path) || '';
  const control = renderFieldControl(field, value);
  const meta = [];
  meta.push(`<span>${typeLabel[field.type] || field.type}</span>`);
  if (field.min != null || field.max != null) {
    meta.push(`<span class="range">${field.min != null ? field.min : '−∞'} ~ ${field.max != null ? field.max : '∞'}</span>`);
  }
  if (field.enum) meta.push(`<span>${field.enum.length} 个可选值</span>`);
  if (field.line) meta.push(`<span class="line">L${field.line}</span>`);
  return `
    <div class="field-row ${changed ? 'is-dirty' : ''}" data-path="${escapeAttr(field.path)}">
      <div class="field-info">
        <div class="field-title">
          <span class="field-label">${escapeHtml(field.label || field.key)}</span>
          <code class="field-key" title="${escapeAttr(field.key)}">${escapeHtml(field.key)}</code>
        </div>
        <div class="field-desc ${field.description ? '' : 'empty'}" title="${escapeAttr(field.description || '')}">${escapeHtml(field.description || '')}</div>
        <div class="field-meta">${meta.join('')}</div>
        <div class="field-error ${error ? 'show' : ''}" data-error="${escapeAttr(field.path)}">${escapeHtml(error)}</div>
      </div>
      <div class="field-control">${control}</div>
      <button class="row-reset" data-action="reset-field" data-path="${escapeAttr(field.path)}" title="撤销此项修改" ${changed ? '' : 'disabled'}>${icon('undo')}</button>
    </div>`;
}

function renderFieldControl(field, value) {
  if (!field.editable) {
    return `<div class="locked-value">${icon('lock')} ${escapeHtml(truncate(JSON.stringify(value), 80))}</div>`;
  }
  if (field.type === 'boolean') {
    return `<div class="switch-wrap">
      <button class="switch" role="switch" aria-checked="${value ? 'true' : 'false'}" data-action="toggle-bool" data-path="${escapeAttr(field.path)}" aria-label="${escapeAttr(field.label)}"></button>
      <span class="switch-state">${value ? '开启' : '关闭'}</span>
    </div>`;
  }
  if (field.enum && field.enum.length >= 2) {
    const optionValue = item => (field.type === 'string' ? String(item) : String(item));
    const options = field.enum.map(item => {
      const selected = deepEqual(item, value);
      return `<option value="${escapeAttr(optionValue(item))}" ${selected ? 'selected' : ''}>${escapeHtml(String(item))}</option>`;
    }).join('');
    const hasCurrent = field.enum.some(item => deepEqual(item, value));
    return `<select class="select-input field-input" data-path="${escapeAttr(field.path)}" data-kind="enum" data-type="${escapeAttr(field.type)}" ${hasCurrent ? '' : 'data-custom="1"'}>
      ${hasCurrent ? '' : `<option value="${escapeAttr(String(value))}" selected>${escapeHtml(String(value))}</option>`}
      ${options}
    </select>`;
  }
  if (field.type === 'integer' || field.type === 'float') {
    const step = field.type === 'integer' ? '1' : 'any';
    return `<input class="num-input field-input" type="number" step="${step}" value="${escapeAttr(value)}" data-path="${escapeAttr(field.path)}" data-kind="number" data-type="${escapeAttr(field.type)}" ${field.min != null ? `min="${escapeAttr(field.min)}"` : ''} ${field.max != null ? `max="${escapeAttr(field.max)}"` : ''} autocomplete="off">`;
  }
  if (field.type === 'array' || field.type === 'object') {
    return `<textarea class="json-input field-input" data-path="${escapeAttr(field.path)}" data-kind="json" data-type="${escapeAttr(field.type)}" spellcheck="false">${escapeHtml(JSON.stringify(value, null, 2))}</textarea>`;
  }
  if (field.multiline) {
    return `<textarea class="json-input field-input" data-path="${escapeAttr(field.path)}" data-kind="string" spellcheck="false">${escapeHtml(value)}</textarea>`;
  }
  return `<input class="text-input field-input" type="text" value="${escapeAttr(value)}" data-path="${escapeAttr(field.path)}" data-kind="string" autocomplete="off" spellcheck="false">`;
}

/* ------------------------------------------------------------- field edits */
function fieldFor(path) {
  return state.fieldByPath.get(path) || null;
}

function effectiveValue(field) {
  return state.changes.has(field.path) ? state.changes.get(field.path) : field.value;
}

function setFieldError(field, message) {
  if (message) {
    state.fieldErrors.set(field.path, message);
    state.changes.delete(field.path);
  } else {
    state.fieldErrors.delete(field.path);
  }
  const row = findRow(field.path);
  if (row) {
    const error = row.querySelector('.field-error');
    if (error) {
      error.textContent = message || '';
      error.classList.toggle('show', !!message);
    }
    const input = row.querySelector('.field-input');
    if (input) input.classList.toggle('invalid', !!message);
    row.classList.toggle('is-dirty', state.changes.has(field.path));
    const reset = row.querySelector('.row-reset');
    if (reset) reset.disabled = !state.changes.has(field.path);
  }
}

function findRow(path) {
  if (typeof CSS !== 'undefined' && CSS.escape) {
    return document.querySelector(`.field-row[data-path="${CSS.escape(path)}"]`);
  }
  return [...document.querySelectorAll('.field-row')].find(row => row.dataset.path === path) || null;
}

function commitField(field, value) {
  state.fieldErrors.delete(field.path);
  if (deepEqual(value, field.value)) state.changes.delete(field.path);
  else state.changes.set(field.path, value);
  const row = findRow(field.path);
  if (row) {
    row.classList.toggle('is-dirty', state.changes.has(field.path));
    const reset = row.querySelector('.row-reset');
    if (reset) reset.disabled = !state.changes.has(field.path);
    const input = row.querySelector('.field-input');
    if (input) input.classList.remove('invalid');
    const error = row.querySelector('.field-error');
    if (error) { error.textContent = ''; error.classList.remove('show'); }
  }
  updateDirtyUI();
}

function handleFieldInput(target) {
  const path = target.dataset.path;
  const field = fieldFor(path);
  if (!field) return;
  const kind = target.dataset.kind;
  try {
    let value;
    if (kind === 'number') {
      if (target.value.trim() === '') throw new Error('请输入一个数字');
      const number = Number(target.value);
      if (!Number.isFinite(number)) throw new Error('数字格式无效');
      if (field.type === 'integer' && !Number.isInteger(number)) throw new Error('这里需要整数');
      if (field.min != null && number < field.min) throw new Error(`不能小于 ${field.min}`);
      if (field.max != null && number > field.max) throw new Error(`不能大于 ${field.max}`);
      value = number;
    } else if (kind === 'json') {
      if (target.value.trim() === '') throw new Error('请输入合法的 JSON');
      value = JSON.parse(target.value);
      if (field.type === 'array' && !Array.isArray(value)) throw new Error('这里需要数组，例如 [1, 2, 3]');
      if (field.type === 'object' && (typeof value !== 'object' || Array.isArray(value) || value === null)) throw new Error('这里需要对象，例如 {"key": true}');
    } else if (kind === 'enum') {
      const raw = target.value;
      if (target.dataset.type === 'integer') value = parseInt(raw, 10);
      else if (target.dataset.type === 'float') value = Number(raw);
      else value = raw;
    } else {
      value = target.value;
    }
    commitField(field, value);
  } catch (error) {
    setFieldError(field, error.message === 'Unexpected end of JSON input' ? 'JSON 尚未写完，请补全后再保存' : error.message);
    updateDirtyUI();
  }
}

function toggleBool(button) {
  const field = fieldFor(button.dataset.path);
  if (!field) return;
  const value = !effectiveValue(field);
  commitField(field, value);
  button.setAttribute('aria-checked', value ? 'true' : 'false');
  const stateLabel = button.parentElement.querySelector('.switch-state');
  if (stateLabel) stateLabel.textContent = value ? '开启' : '关闭';
}

function resetField(path) {
  const field = fieldFor(path);
  if (!field) return;
  state.changes.delete(path);
  state.fieldErrors.delete(path);
  const row = findRow(path);
  if (!row) return;
  row.classList.remove('is-dirty');
  const reset = row.querySelector('.row-reset');
  if (reset) reset.disabled = true;
  const input = row.querySelector('.field-input');
  if (input) {
    if (field.type === 'array' || field.type === 'object') input.value = JSON.stringify(field.value, null, 2);
    else if (field.type === 'boolean') {
      const button = row.querySelector('.switch');
      if (button) button.setAttribute('aria-checked', field.value ? 'true' : 'false');
      const stateLabel = row.querySelector('.switch-state');
      if (stateLabel) stateLabel.textContent = field.value ? '开启' : '关闭';
    } else input.value = field.value;
    input.classList.remove('invalid');
  }
  const error = row.querySelector('.field-error');
  if (error) { error.textContent = ''; error.classList.remove('show'); }
  updateDirtyUI();
}

function discardChanges() {
  state.changes.clear();
  state.fieldErrors.clear();
  state.rawDirty = false;
  state.rawText = state.currentConfig ? state.currentConfig.raw : '';
  renderConfigPanel();
  toast('已撤销所有未保存的修改', 'info');
}

function dirtyCount() {
  return state.rawMode ? (state.rawDirty ? 1 : 0) : state.changes.size;
}

function isDirty() {
  return dirtyCount() > 0;
}

function clearDirty() {
  state.changes.clear();
  state.fieldErrors.clear();
  state.rawDirty = false;
}

function updateDirtyUI() {
  const dock = document.getElementById('save-dock');
  if (!dock) return;
  const count = dirtyCount();
  dock.hidden = count === 0;
  dock.classList.toggle('has-error', state.fieldErrors.size > 0);
  const countEl = document.getElementById('dirty-count');
  if (countEl) countEl.textContent = String(count);
  const saveButton = document.getElementById('save-button');
  if (saveButton) saveButton.disabled = state.saving || state.fieldErrors.size > 0;
  const hint = document.getElementById('save-hint');
  if (hint) {
    hint.textContent = state.fieldErrors.size
      ? `有 ${state.fieldErrors.size} 个输入无效，修正后才能保存`
      : '保存时会自动备份原文件';
  }
}

/* ---------------------------------------------------------------- saving */
async function saveConfig() {
  if (state.saving || !state.currentConfig || !state.modData) return;
  if (state.fieldErrors.size) {
    toast('请先修正无效的输入', 'error');
    return;
  }
  const count = dirtyCount();
  if (!count) {
    toast('没有需要保存的修改', 'info');
    return;
  }
  const payload = {
    version: state.currentVersionId,
    key: state.modData.mod.key,
    file: state.currentConfig.file.path,
    hash: state.currentConfig.hash,
  };
  if (state.rawMode) payload.raw = state.rawText;
  else payload.changes = [...state.changes.entries()].map(([path, value]) => ({ path, value }));
  state.saving = true;
  const button = document.getElementById('save-button');
  if (button) {
    button.disabled = true;
    button.innerHTML = `<span class="spinner" style="width:13px;height:13px;margin:0;border-width:2px"></span> 保存中…`;
  }
  try {
    const result = await api('/api/config/save', { method: 'POST', body: payload });
    if (result.unchanged) {
      toast('内容没有变化', 'info');
      state.saving = false;
      renderConfigPanel();
      return;
    }
    state.currentConfig.hash = result.hash;
    state.currentConfig.raw = result.raw != null ? result.raw : state.rawText;
    state.currentConfig.fields = result.fields || state.currentConfig.fields;
    state.currentConfig.warnings = result.warnings || [];
    state.currentConfig.size = result.size;
    state.currentConfig.size_label = result.size_label;
    state.currentConfig.line_count = result.line_count;
    state.currentConfig.format = result.format || state.currentConfig.format;
    state.currentConfig.format_label = result.format_label || state.currentConfig.format_label;
    state.fieldByPath = new Map((state.currentConfig.fields || []).map(field => [field.path, field]));
    state.rawText = state.currentConfig.raw;
    state.rawDirty = false;
    state.changes.clear();
    state.fieldErrors.clear();
    const activeMeta = (state.modData.configs || []).find(item => item.path === state.currentConfig.file.path);
    if (activeMeta) {
      activeMeta.field_count = (state.currentConfig.fields || []).length;
      activeMeta.warnings = (state.currentConfig.warnings || []).slice(0, 2);
    }
    state.saving = false;
    renderConfigPanel();
    toast(`已保存 ${count} 项修改`, 'success', result.backup ? `原文件已备份 · ${result.backup.split('/')[0]}` : '原文件已自动备份');
  } catch (error) {
    state.saving = false;
    if (button) {
      button.disabled = false;
      button.innerHTML = `${icon('save')} 保存到文件`;
    }
    if (error.status === 409) {
      const reload = await confirmDialog({
        title: '文件已被外部修改',
        message: '在编辑期间，这个配置文件被其他程序修改了。为了避免覆盖新内容，CraftTune 已停止保存。重新载入后可以再次编辑。',
        confirmText: '重新载入',
        iconName: 'refresh',
        danger: true,
      });
      if (reload) await reloadConfig(true);
    } else {
      toast('保存失败', 'error', error.message);
    }
    updateDirtyUI();
  }
}

async function reloadConfig(skipGuard = false) {
  if (!state.currentConfig || !state.modData) return;
  if (!skipGuard && isDirty()) {
    const ok = await confirmDialog({
      title: '放弃修改并重新载入？',
      message: '重新载入会丢弃当前尚未保存的修改。',
      confirmText: '放弃并载入',
      danger: true,
    });
    if (!ok) return;
    clearDirty();
  }
  const filePath = state.currentConfig.file.path;
  await loadConfigFile(filePath, { skipGuard: true });
}

async function toggleRawMode() {
  if (!state.currentConfig) return;
  if (!state.rawMode) {
    if (isDirty()) {
      const ok = await confirmDialog({
        title: '切换到源码模式？',
        message: '切换视图会丢弃当前尚未保存的参数修改。',
        confirmText: '丢弃并切换',
        danger: true,
      });
      if (!ok) return;
      clearDirty();
    }
    state.rawMode = true;
    state.rawText = state.currentConfig.raw;
    state.rawDirty = false;
    renderConfigPanel();
  } else {
    if (state.rawDirty) {
      const ok = await confirmDialog({
        title: '切换回参数视图？',
        message: '源码修改尚未保存，切换视图会丢弃这些修改。',
        confirmText: '丢弃并切换',
        danger: true,
      });
      if (!ok) return;
      state.rawDirty = false;
      state.rawText = state.currentConfig.raw;
    }
    state.rawMode = false;
    state.changes.clear();
    state.fieldErrors.clear();
    renderConfigPanel();
  }
}

/* ------------------------------------------------------------------ nav */
function navigate(hash) {
  if (location.hash === hash) {
    route();
    return;
  }
  state.allowLeave = true;
  location.hash = hash;
}

async function guardedNavigate(hash) {
  if (isDirty()) {
    const ok = await confirmDialog({
      title: '离开当前编辑？',
      message: '当前配置文件还有未保存的修改，离开会丢失这些修改。',
      confirmText: '放弃并离开',
      danger: true,
    });
    if (!ok) return;
    clearDirty();
  }
  navigate(hash);
}

function openVersion(versionId) {
  navigate(`#/mods/${encodeURIComponent(versionId)}`);
}
function openMod(modKey) {
  navigate(`#/mod/${encodeURIComponent(state.currentVersionId)}/${encodeURIComponent(modKey)}`);
}

async function route() {
  const rawHash = location.hash.replace(/^#/, '') || '/';
  const parts = rawHash.split('/').filter(Boolean);
  state.editorHash = '';
  if (parts[0] === 'mods' && parts[1]) {
    const versionId = decodeURIComponent(parts[1]);
    if (state.modsData && state.currentVersionId === versionId && state.viewMode === 'mods') {
      renderSidebar('mods');
      renderModsPage();
      return;
    }
    state.viewMode = 'mods';
    await loadModsPage(versionId);
    return;
  }
  if (parts[0] === 'mod' && parts[1] && parts[2]) {
    const versionId = decodeURIComponent(parts[1]);
    const modKey = decodeURIComponent(parts[2]);
    state.viewMode = 'editor';
    state.editorHash = location.hash;
    await loadModPage(versionId, modKey);
    return;
  }
  state.viewMode = 'home';
  state.modsData = null;
  state.modData = null;
  state.currentConfig = null;
  state.currentVersionId = null;
  state.changes.clear();
  renderHome();
}

window.addEventListener('hashchange', () => {
  const allowLeave = state.allowLeave;
  state.allowLeave = false;
  if (!allowLeave && isDirty() && state.editorHash && location.hash !== state.editorHash) {
    const ok = window.confirm('当前配置还有未保存的修改，确定离开并丢弃吗？');
    if (!ok) {
      history.replaceState(null, '', state.editorHash);
      return;
    }
    clearDirty();
  }
  route();
});

/* ---------------------------------------------------------------- loading */
function showPageLoading(text) {
  els.view.innerHTML = `
    <div class="crumb"><button data-action="go-home">版本库</button><span class="sep">/</span><span class="current">读取中…</span></div>
    <div class="loading-block"><div class="spinner"></div>${escapeHtml(text || '正在读取…')}</div>`;
}

function renderErrorPage(error, retry) {
  const isConnection = !error.status;
  renderSidebar('home');
  els.view.innerHTML = `
    <div class="empty-panel fade-up" style="margin-top:40px">
      <div class="empty-icon">${icon('alert')}</div>
      <div class="empty-title">${isConnection ? '无法连接本地服务' : '读取失败'}</div>
      <div class="empty-text">${escapeHtml(error.message || String(error))}</div>
      <div class="empty-actions">
        <button class="btn btn-primary" data-action="retry-route">${icon('refresh')} 重试</button>
        <button class="btn" data-action="go-home">${icon('arrow-left')} 返回版本库</button>
        <button class="btn" data-action="manual-launcher">${icon('folder')} 检查目录</button>
      </div>
    </div>`;
  state.retryRoute = retry;
}

async function loadVersions() {
  const data = await api('/api/versions');
  state.versions = data.versions || [];
  if (state.status) {
    state.status.launcher = data.launcher || state.status.launcher;
    state.status.detected = data.detected || state.status.detected;
  }
}

/* ---------------------------------------------------------------- actions */
async function chooseFolder() {
  try {
    const result = await api('/api/pick-folder', { method: 'POST' });
    if (!result.path) return;
    await switchLauncher(result.path);
  } catch (error) {
    toast('无法打开文件夹选择框', 'error', error.message);
    await promptLauncher();
  }
}

async function promptLauncher() {
  const current = (state.status && state.status.launcher) || '';
  const value = await showModal({
    title: '指定 .minecraft 目录',
    sub: '选择包含 versions 文件夹的启动器目录',
    iconName: 'folder',
    body: '<p>通常位于 <code>%APPDATA%\\.minecraft</code>。如果你使用 PCL 等启动器，也可以直接填写它的 .minecraft 路径。</p>',
    input: { value: current, placeholder: 'C:\\Users\\你\\AppData\\Roaming\\.minecraft', hint: '支持带引号的路径；也可以填写包含 .minecraft 的父目录。' },
    actions: [
      { label: '取消', value: '__cancel' },
      { label: '使用此目录', value: 'ok', className: 'btn-primary' },
    ],
  });
  if (value && value !== '__cancel') await switchLauncher(value);
}

async function switchLauncher(path) {
  try {
    const data = await api('/api/launcher', { method: 'POST', body: { path } });
    state.status = Object.assign({}, state.status, { launcher: data.launcher, detected: data.launcher });
    state.versions = data.versions || [];
    state.modsData = null;
    state.modData = null;
    state.currentVersionId = null;
    navigate('#/');
    if (!state.versions.length) toast('已设置目录，但没有发现游戏版本', 'warn', '请确认 versions 文件夹存在');
    else toast('已切换 Minecraft 目录', 'success', `发现 ${state.versions.length} 个游戏版本`);
  } catch (error) {
    toast('目录无效', 'error', error.message);
  }
}

async function refreshAll(versionId = null) {
  if (isDirty()) {
    const ok = await confirmDialog({
      title: '重新扫描并刷新？',
      message: '刷新会重新读取配置文件，当前未保存的修改会丢失。',
      confirmText: '放弃并刷新',
      danger: true,
    });
    if (!ok) return;
    clearDirty();
  }
  try {
    const body = versionId ? { version: versionId } : {};
    await api('/api/refresh', { method: 'POST', body });
    await loadVersions();
    if (versionId) {
      state.modsData = null;
      if (state.viewMode === 'editor' && state.modData) {
        const modKey = state.modData.mod.key;
        await loadModPage(versionId, modKey);
      } else {
        await loadModsPage(versionId);
      }
    } else {
      state.modsData = null;
      state.modData = null;
      await route();
    }
    toast('已重新扫描', 'success');
  } catch (error) {
    toast('刷新失败', 'error', error.message);
  }
}

async function revealConfig() {
  if (!state.currentConfig) return;
  try {
    await api('/api/reveal', { method: 'POST', body: { version: state.currentVersionId, file: state.currentConfig.file.path } });
  } catch (error) {
    toast('无法打开文件夹', 'error', error.message);
  }
}

async function revealModConfig() {
  try {
    await api('/api/reveal', { method: 'POST', body: { version: state.currentVersionId } });
  } catch (error) {
    toast('无法打开文件夹', 'error', error.message);
  }
}

async function showHelp() {
  await showModal({
    title: 'CraftTune 使用说明',
    sub: '三步完成参数调整',
    iconName: 'spark',
    body: `
      <p><b>1. 选择游戏版本</b><br>在主页选择整合包版本。CraftTune 会读取该版本隔离目录中的 mods 与 config，不会移动或上传任何文件。</p>
      <p><b>2. 选择模组</b><br>配置文件通过模组 ID、JAR 文件名和目录名自动关联。没有匹配到的文件会集中到“未归属配置文件”，也可以直接编辑。</p>
      <p><b>3. 修改与保存</b><br>开关、数字、文本、数组会以不同控件展示。保存时只替换目标值，尽量保留原文件的注释与排版，并自动备份原文件。</p>
      <p style="color:var(--amber)"><b>提示：</b>修改配置前建议关闭游戏；部分模组只会在重启后读取配置。</p>`,
    actions: [{ label: '知道了', value: 'ok', className: 'btn-primary' }],
  });
}

async function showBackups() {
  const path = (state.status && state.status.backup_dir) || 'data/backups';
  const result = await showModal({
    title: '安全备份',
    sub: '每次保存前的原文件快照',
    iconName: 'save',
    body: `
      <p>保存任何配置文件之前，CraftTune 会把原文件复制到本地备份目录，默认保留最近 <b>120</b> 次保存记录。</p>
      <p style="font-family:var(--mono);font-size:11px;color:var(--text-soft);word-break:break-all;background:rgba(255,255,255,.03);border:1px solid var(--line);border-radius:8px;padding:10px 12px">${escapeHtml(path)}</p>
      <p>备份按保存时间分文件夹存放，路径结构与 config 目录一致。如果需要回滚，退出 CraftTune 后用备份文件覆盖原文件即可。</p>`,
    actions: [
      { label: '打开备份目录', value: 'open', className: 'btn' },
      { label: '关闭', value: 'ok', className: 'btn-primary' },
    ],
  });
  if (result === 'open') {
    try {
      await api('/api/open-backups', { method: 'POST' });
    } catch (error) {
      toast('无法打开备份目录', 'error', error.message);
    }
  }
}

function wireEvents() {
  document.addEventListener('click', async event => {
    const target = event.target.closest('[data-action]');
    if (!target) return;
    if (target.tagName === 'A') event.preventDefault();
    const action = target.dataset.action;
    try {
      switch (action) {
        case 'go-home': await guardedNavigate('#/'); break;
        case 'choose-folder': await chooseFolder(); break;
        case 'manual-launcher': await promptLauncher(); break;
        case 'refresh-all': await refreshAll(); break;
        case 'enter-version': openVersion(target.dataset.version); break;
        case 'switch-version': await guardedNavigate('#/'); break;
        case 'open-mod': openMod(target.dataset.key); break;
        case 'back-mods': await guardedNavigate(`#/mods/${encodeURIComponent(state.currentVersionId)}`); break;
        case 'refresh-mods':
          if (state.viewMode === 'editor') await refreshAll(state.currentVersionId);
          else await refreshAll(state.currentVersionId);
          break;
        case 'help': await showHelp(); break;
        case 'backups': await showBackups(); break;
        case 'retry-route': if (state.retryRoute) await state.retryRoute(); break;
        case 'clear-mod-search': state.modQuery = ''; renderModsPage(); break;
        case 'set-mod-filter': state.modFilter = target.dataset.filter; renderModsPage(); break;
        case 'open-file': await loadConfigFile(target.dataset.file); break;
        case 'toggle-bool': toggleBool(target); break;
        case 'show-more-fields': state.fieldLimit += 400; renderFields(); break;
        case 'reset-field': resetField(target.dataset.path); break;
        case 'discard-changes': discardChanges(); break;
        case 'save-config': await saveConfig(); break;
        case 'toggle-raw': await toggleRawMode(); break;
        case 'reload-config': await reloadConfig(); break;
        case 'reveal-config': await revealConfig(); break;
        case 'reveal-mod-config': await revealModConfig(); break;
        default: break;
      }
    } catch (error) {
      toast('操作失败', 'error', error.message || String(error));
    }
  });

  const onSearch = debounce(() => {
    renderFields();
  }, 100);

  document.addEventListener('input', event => {
    const target = event.target;
    if (!target) return;
    if (target.id === 'mod-search') {
      state.modQuery = target.value;
      renderModGrid();
      return;
    }
    if (target.id === 'file-filter') {
      state.fileQuery = target.value;
      renderFileList();
      return;
    }
    if (target.id === 'param-search') {
      state.fieldQuery = target.value;
      onSearch();
      return;
    }
    if (target.id === 'raw-editor') {
      state.rawText = target.value;
      state.rawDirty = state.rawText !== state.currentConfig.raw;
      updateDirtyUI();
      return;
    }
    if (target.classList.contains('field-input')) {
      handleFieldInput(target);
    }
  });

  document.addEventListener('change', event => {
    const target = event.target;
    if (target && target.id === 'only-dirty') {
      state.onlyDirty = target.checked;
      renderFields();
    }
  });

  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
      if (state.viewMode === 'editor' && state.currentConfig) {
        event.preventDefault();
        saveConfig();
      }
    }
    if (event.key === '/' && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) {
      const search = document.getElementById('param-search') || document.getElementById('mod-search');
      if (search) { event.preventDefault(); search.focus(); }
    }
  });

  document.addEventListener('error', event => {
    const img = event.target;
    if (img && img.tagName === 'IMG' && img.dataset.modImg !== undefined) {
      img.remove();
      if (img.parentElement) img.parentElement.classList.add('noimg');
    }
    if (img && img.tagName === 'IMG' && img.dataset.versionImg !== undefined) {
      img.remove();
      if (img.parentElement) {
        const fallback = img.parentElement.querySelector('.fallback');
        if (fallback) fallback.style.display = 'block';
      }
    }
  }, true);

  window.addEventListener('beforeunload', event => {
    if (isDirty()) {
      event.preventDefault();
      event.returnValue = '';
    }
  });
}

/* ------------------------------------------------------------------ boot */
async function boot() {
  if (!state.eventsWired) {
    wireEvents();
    state.eventsWired = true;
  }
  renderSidebar('home');
  try {
    state.status = await api('/api/status');
    await loadVersions();
  } catch (error) {
    renderErrorPage(error, boot);
    return;
  }
  state.booted = true;
  await route();
}

boot();
