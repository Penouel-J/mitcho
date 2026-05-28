/* ============================================================
   MITCHÔ — Système d'authentification & abonnement
   Mode backend  : FastAPI /auth/register + /auth/login
   Mode fallback : localStorage (si le backend n'est pas démarré)
   ============================================================ */

const AUTH_BACKEND = 'http://localhost:8000';
let _afterAuthCallback = null;

/* ── Injection du modal dans le DOM ── */
(function injectAuthModal() {
  const html = `
<!-- ===== MODAL AUTH ===== -->
<div id="auth-overlay" class="fixed inset-0 bg-black/60 z-[300] hidden items-center justify-center p-4">
  <div class="bg-white rounded-3xl shadow-2xl w-full max-w-[440px] overflow-hidden animate-none" id="auth-card">

    <!-- Header -->
    <div class="bg-primary px-8 py-6 flex items-center justify-between">
      <div>
        <p class="font-display-lg text-[18px] font-bold text-on-primary">MITCHÔ</p>
        <p class="text-on-primary/70 text-[12px] mt-0.5" id="auth-header-sub">Créez votre compte gratuit</p>
      </div>
      <button onclick="closeAuthModal()" class="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors">
        <span class="material-symbols-outlined text-on-primary text-[18px]">close</span>
      </button>
    </div>

    <!-- Tabs -->
    <div class="flex border-b border-outline-variant/30">
      <button id="tab-register" onclick="switchTab('register')"
        class="flex-1 py-4 font-label-sm text-label-sm text-primary border-b-2 border-primary transition-all">
        Créer un compte
      </button>
      <button id="tab-login" onclick="switchTab('login')"
        class="flex-1 py-4 font-label-sm text-label-sm text-on-surface-variant border-b-2 border-transparent hover:text-primary transition-all">
        Se connecter
      </button>
    </div>

    <!-- Formulaire inscription -->
    <form id="form-register" onsubmit="handleRegister(event)" class="px-8 py-6 space-y-4">
      <div>
        <label class="font-label-sm text-label-sm text-on-surface-variant mb-1.5 block">Nom complet</label>
        <input id="reg-name" type="text" placeholder="Ex : Kouassi Adjovi" required
          class="w-full bg-surface-container-low border border-outline-variant/40 rounded-xl px-4 py-3 font-body-md text-body-md focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition"/>
      </div>
      <div>
        <label class="font-label-sm text-label-sm text-on-surface-variant mb-1.5 block">Email institutionnel</label>
        <input id="reg-email" type="email" placeholder="votre@institution.bj" required
          class="w-full bg-surface-container-low border border-outline-variant/40 rounded-xl px-4 py-3 font-body-md text-body-md focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition"/>
      </div>
      <div>
        <label class="font-label-sm text-label-sm text-on-surface-variant mb-1.5 block">Mot de passe</label>
        <input id="reg-password" type="password" placeholder="8 caractères minimum" required minlength="6"
          class="w-full bg-surface-container-low border border-outline-variant/40 rounded-xl px-4 py-3 font-body-md text-body-md focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition"/>
      </div>
      <!-- Abonnement email -->
      <label class="flex items-start gap-3 p-4 bg-primary/5 rounded-xl cursor-pointer hover:bg-primary/10 transition-colors border border-primary/20">
        <input id="reg-subscribe" type="checkbox" checked class="mt-0.5 w-4 h-4 accent-[#006b3f] flex-shrink-0"/>
        <div>
          <p class="font-label-sm text-label-sm text-on-surface font-semibold">Recevoir les prévisions mensuelles</p>
          <p class="font-caption text-caption text-on-surface-variant mt-0.5">Rapport PDF + synthèse stratégique envoyés le 1er de chaque mois dans votre boîte mail.</p>
        </div>
      </label>
      <p id="reg-error" class="hidden text-[12px] text-error font-medium"></p>
      <button type="submit"
        class="w-full bg-primary text-on-primary py-4 rounded-xl font-label-sm text-label-sm text-[14px] hover:opacity-90 active:scale-[0.98] transition-all shadow-lg shadow-primary/20 flex items-center justify-center gap-2">
        <span class="material-symbols-outlined text-[18px]" style="font-variation-settings:'FILL' 1;">person_add</span>
        Créer mon compte
      </button>
      <p class="text-center font-caption text-caption text-on-surface-variant">Gratuit · Aucune carte bancaire requise</p>
    </form>

    <!-- Formulaire connexion -->
    <form id="form-login" onsubmit="handleLogin(event)" class="hidden px-8 py-6 space-y-4">
      <div>
        <label class="font-label-sm text-label-sm text-on-surface-variant mb-1.5 block">Email</label>
        <input id="login-email" type="email" placeholder="votre@email.bj" required
          class="w-full bg-surface-container-low border border-outline-variant/40 rounded-xl px-4 py-3 font-body-md text-body-md focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition"/>
      </div>
      <div>
        <label class="font-label-sm text-label-sm text-on-surface-variant mb-1.5 block">Mot de passe</label>
        <input id="login-password" type="password" placeholder="••••••••" required
          class="w-full bg-surface-container-low border border-outline-variant/40 rounded-xl px-4 py-3 font-body-md text-body-md focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition"/>
      </div>
      <p id="login-error" class="hidden text-[12px] text-error font-medium"></p>
      <button type="submit"
        class="w-full bg-primary text-on-primary py-4 rounded-xl font-label-sm text-label-sm text-[14px] hover:opacity-90 active:scale-[0.98] transition-all shadow-lg shadow-primary/20 flex items-center justify-center gap-2">
        <span class="material-symbols-outlined text-[18px]" style="font-variation-settings:'FILL' 1;">login</span>
        Se connecter
      </button>
    </form>

  </div>
</div>

<!-- ===== TOAST DE CONFIRMATION ===== -->
<div id="auth-toast" class="fixed bottom-28 left-1/2 -translate-x-1/2 z-[400] hidden">
  <div class="bg-on-surface text-background px-6 py-4 rounded-2xl shadow-2xl flex items-center gap-3 max-w-sm">
    <span class="material-symbols-outlined text-inverse-primary text-[22px]" style="font-variation-settings:'FILL' 1;" id="toast-icon">check_circle</span>
    <p class="font-body-md text-body-md" id="toast-message"></p>
  </div>
</div>`;

  document.body.insertAdjacentHTML('beforeend', html);
})();

/* ── Utilitaires localStorage ── */
function getUsers()    { return JSON.parse(localStorage.getItem('mitcho_users') || '[]'); }
function getSession()  { return JSON.parse(sessionStorage.getItem('mitcho_session') || 'null'); }

function saveUsers(users)  { localStorage.setItem('mitcho_users', JSON.stringify(users)); }
function setSession(user)  {
  sessionStorage.setItem('mitcho_session', JSON.stringify({ ...user, loggedIn: true }));
}

/* ── Ouvrir le modal ── */
function openAuthModal(tab = 'register', callback = null) {
  _afterAuthCallback = callback;
  const session = getSession();
  if (session?.loggedIn) {
    if (callback) callback();
    return;
  }
  switchTab(tab);
  const overlay = document.getElementById('auth-overlay');
  overlay.classList.remove('hidden');
  overlay.classList.add('flex');
  // Focus premier champ
  setTimeout(() => {
    const firstInput = document.querySelector('#auth-overlay input:not([type=checkbox])');
    firstInput?.focus();
  }, 100);
}

/* ── Fermer le modal ── */
function closeAuthModal() {
  const overlay = document.getElementById('auth-overlay');
  overlay.classList.add('hidden');
  overlay.classList.remove('flex');
}

/* ── Fermer si clic en dehors ── */
document.addEventListener('click', (e) => {
  const overlay = document.getElementById('auth-overlay');
  if (e.target === overlay) closeAuthModal();
});

/* ── Switcher les onglets ── */
function switchTab(tab) {
  const isRegister = tab === 'register';
  document.getElementById('form-register').classList.toggle('hidden', !isRegister);
  document.getElementById('form-login').classList.toggle('hidden', isRegister);
  document.getElementById('tab-register').className = `flex-1 py-4 font-label-sm text-label-sm transition-all border-b-2 ${isRegister ? 'text-primary border-primary' : 'text-on-surface-variant border-transparent hover:text-primary'}`;
  document.getElementById('tab-login').className    = `flex-1 py-4 font-label-sm text-label-sm transition-all border-b-2 ${!isRegister ? 'text-primary border-primary' : 'text-on-surface-variant border-transparent hover:text-primary'}`;
  document.getElementById('auth-header-sub').textContent = isRegister ? 'Créez votre compte gratuit' : 'Connectez-vous à votre espace';
}

/* ── Inscription ── */
async function handleRegister(e) {
  e.preventDefault();
  const name       = document.getElementById('reg-name').value.trim();
  const email      = document.getElementById('reg-email').value.trim().toLowerCase();
  const password   = document.getElementById('reg-password').value;
  const subscribed = document.getElementById('reg-subscribe').checked;
  const errEl      = document.getElementById('reg-error');
  errEl.classList.add('hidden');

  try {
    const res = await fetch(`${AUTH_BACKEND}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, name, password, subscribe: subscribed }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Erreur inscription');

    setSession({ ...data.user, token: data.access_token, loggedIn: true });
    closeAuthModal();
    refreshAuthNav();
    const msg = subscribed
      ? `Compte créé ! Prévisions mensuelles activées → ${email}`
      : `Bienvenue, ${name.split(' ')[0]} !`;
    showToast(msg, 'check_circle');
    if (_afterAuthCallback) { _afterAuthCallback(); _afterAuthCallback = null; }
    return;
  } catch (backendErr) {
    if (!backendErr.message.includes('fetch')) {
      errEl.textContent = backendErr.message;
      errEl.classList.remove('hidden');
      return;
    }
  }

  // Fallback : localStorage
  const users = getUsers();
  if (users.find(u => u.email === email)) {
    errEl.textContent = 'Un compte existe déjà avec cet email. Connectez-vous.';
    errEl.classList.remove('hidden');
    return;
  }
  const user = { name, email, password, subscribed, createdAt: new Date().toISOString() };
  users.push(user);
  saveUsers(users);
  setSession({ ...user, loggedIn: true });
  closeAuthModal();
  refreshAuthNav();
  const msg = subscribed
    ? `Compte créé ! Prévisions mensuelles activées → ${email}`
    : `Bienvenue, ${name.split(' ')[0]} !`;
  showToast(msg, 'check_circle');
  if (_afterAuthCallback) { _afterAuthCallback(); _afterAuthCallback = null; }
}

/* ── Connexion ── */
async function handleLogin(e) {
  e.preventDefault();
  const email    = document.getElementById('login-email').value.trim().toLowerCase();
  const password = document.getElementById('login-password').value;
  const errEl    = document.getElementById('login-error');
  errEl.classList.add('hidden');

  try {
    const form = new URLSearchParams({ username: email, password });
    const res = await fetch(`${AUTH_BACKEND}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form.toString(),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Email ou mot de passe incorrect.');

    setSession({ ...data.user, token: data.access_token, loggedIn: true });
    closeAuthModal();
    refreshAuthNav();
    showToast(`Bon retour, ${data.user.name.split(' ')[0]} !`, 'check_circle');
    if (_afterAuthCallback) { _afterAuthCallback(); _afterAuthCallback = null; }
    return;
  } catch (backendErr) {
    if (!backendErr.message.includes('fetch')) {
      errEl.textContent = backendErr.message;
      errEl.classList.remove('hidden');
      return;
    }
  }

  // Fallback : localStorage
  const user = getUsers().find(u => u.email === email && u.password === password);
  if (!user) {
    errEl.textContent = 'Email ou mot de passe incorrect.';
    errEl.classList.remove('hidden');
    return;
  }
  setSession({ ...user, loggedIn: true });
  closeAuthModal();
  refreshAuthNav();
  showToast(`Bon retour, ${user.name.split(' ')[0]} !`, 'check_circle');
  if (_afterAuthCallback) { _afterAuthCallback(); _afterAuthCallback = null; }
}

/* ── Déconnexion ── */
function logout() {
  sessionStorage.removeItem('mitcho_session');
  refreshAuthNav();
  showToast('Vous êtes déconnecté.', 'logout');
}

/* ── Récupérer le token JWT (pour les appels API authentifiés) ── */
function getAuthToken() {
  return getSession()?.token || null;
}

/* ── Mise à jour barre de nav ── */
function refreshAuthNav() {
  const session = getSession();
  ['btn-login', 'btn-logout', 'nav-username'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    if (id === 'btn-login')    el.classList.toggle('hidden', !!session?.loggedIn);
    if (id === 'btn-logout')   el.classList.toggle('hidden', !session?.loggedIn);
    if (id === 'nav-username') {
      el.classList.toggle('hidden', !session?.loggedIn);
      if (session?.loggedIn) el.textContent = session.name.split(' ')[0];
    }
  });
}

/* ── Toast de notification ── */
function showToast(message, icon = 'check_circle') {
  const toast = document.getElementById('auth-toast');
  document.getElementById('toast-message').textContent = message;
  document.getElementById('toast-icon').textContent    = icon;
  toast.classList.remove('hidden');
  setTimeout(() => toast.classList.add('hidden'), 4000);
}

/* ── Init au chargement ── */
document.addEventListener('DOMContentLoaded', () => {
  refreshAuthNav();
});
