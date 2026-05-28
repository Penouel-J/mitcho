/* ============================================================
   MITCHÔ — Authentification avec sélecteur de profil
   Profils : "agriculteur" | "decideur"
   Mode backend  : FastAPI /auth/register + /auth/login
   Mode fallback : localStorage (si le backend n'est pas démarré)
   ============================================================ */

const AUTH_BACKEND = 'http://localhost:8000';
let _afterAuthCallback = null;
let _forcedAuth = false;       // true = modal obligatoire (pas de fermeture)
let _selectedProfile = null;   // profil choisi à l'étape 1

/* ── Injection du modal dans le DOM ── */
(function injectAuthModal() {
  const html = `
<div id="auth-overlay" class="fixed inset-0 bg-black/70 z-[300] hidden items-center justify-center p-4" style="backdrop-filter:blur(4px)">
  <div class="bg-white rounded-3xl shadow-2xl w-full max-w-[480px] overflow-hidden" id="auth-card">

    <!-- Header -->
    <div class="bg-primary px-8 py-6 flex items-center justify-between">
      <div>
        <p class="font-display-lg text-[20px] font-bold text-on-primary tracking-tight">MITCHÔ</p>
        <p class="text-on-primary/70 text-[12px] mt-0.5" id="auth-header-sub">Intelligence alimentaire · Bénin</p>
      </div>
      <button id="auth-close-btn" onclick="closeAuthModal()"
        class="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors">
        <span class="material-symbols-outlined text-on-primary text-[18px]">close</span>
      </button>
    </div>

    <!-- ───── ÉTAPE 1 : Sélecteur de profil ───── -->
    <div id="step-profile" class="px-8 py-7">
      <p class="font-title-md text-[16px] font-semibold text-on-surface text-center mb-1">Vous êtes...</p>
      <p class="font-body-sm text-[13px] text-on-surface-variant text-center mb-6">
        Votre profil adapte les analyses et recommandations à vos besoins réels.
      </p>

      <div class="grid grid-cols-2 gap-4">
        <!-- Carte Agriculteur -->
        <button onclick="selectProfile('agriculteur')"
          id="card-agriculteur"
          class="group flex flex-col items-center gap-3 p-5 rounded-2xl border-2 border-outline-variant/30 hover:border-primary hover:bg-primary/5 transition-all text-left">
          <div class="w-14 h-14 rounded-2xl bg-[#e8f5e9] flex items-center justify-center group-hover:bg-primary/10 transition-colors">
            <span class="material-symbols-outlined text-[32px] text-[#2e7d32]" style="font-variation-settings:'FILL' 1;">agriculture</span>
          </div>
          <div class="text-center">
            <p class="font-label-sm text-[13px] font-semibold text-on-surface">Agriculteur</p>
            <p class="font-caption text-[11px] text-on-surface-variant mt-0.5">Producteur / Éleveur</p>
          </div>
          <div class="text-[10px] text-on-surface-variant text-center leading-relaxed">
            Conseils pratiques, meilleures périodes de vente, marchés favorables
          </div>
        </button>

        <!-- Carte Décideur -->
        <button onclick="selectProfile('decideur')"
          id="card-decideur"
          class="group flex flex-col items-center gap-3 p-5 rounded-2xl border-2 border-outline-variant/30 hover:border-primary hover:bg-primary/5 transition-all text-left">
          <div class="w-14 h-14 rounded-2xl bg-[#e8eaf6] flex items-center justify-center group-hover:bg-primary/10 transition-colors">
            <span class="material-symbols-outlined text-[32px] text-[#303f9f]" style="font-variation-settings:'FILL' 1;">account_balance</span>
          </div>
          <div class="text-center">
            <p class="font-label-sm text-[13px] font-semibold text-on-surface">Décideur public</p>
            <p class="font-caption text-[11px] text-on-surface-variant mt-0.5">Ministère / Institution</p>
          </div>
          <div class="text-[10px] text-on-surface-variant text-center leading-relaxed">
            Analyse stratégique, alertes précoces, recommandations de politique
          </div>
        </button>
      </div>
    </div>

    <!-- ───── ÉTAPE 2 : Formulaires connexion / inscription ───── -->
    <div id="step-auth" class="hidden">

      <!-- Profil sélectionné + retour -->
      <div id="profile-badge" class="flex items-center justify-between px-8 py-3 bg-surface-container-low border-b border-outline-variant/20">
        <div class="flex items-center gap-2">
          <span class="material-symbols-outlined text-[18px] text-primary" id="badge-icon" style="font-variation-settings:'FILL' 1;">agriculture</span>
          <span class="font-label-sm text-[12px] text-on-surface-variant">Profil : <strong class="text-on-surface" id="badge-label">Agriculteur</strong></span>
        </div>
        <button onclick="goBackToProfile()" class="text-[11px] text-primary hover:underline flex items-center gap-1">
          <span class="material-symbols-outlined text-[14px]">arrow_back</span>
          Modifier
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
          <label class="font-label-sm text-label-sm text-on-surface-variant mb-1.5 block">Email</label>
          <input id="reg-email" type="email" placeholder="votre@email.bj" required
            class="w-full bg-surface-container-low border border-outline-variant/40 rounded-xl px-4 py-3 font-body-md text-body-md focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition"/>
        </div>
        <div>
          <label class="font-label-sm text-label-sm text-on-surface-variant mb-1.5 block">Mot de passe</label>
          <input id="reg-password" type="password" placeholder="8 caractères minimum" required minlength="6"
            class="w-full bg-surface-container-low border border-outline-variant/40 rounded-xl px-4 py-3 font-body-md text-body-md focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition"/>
        </div>
        <label class="flex items-start gap-3 p-4 bg-primary/5 rounded-xl cursor-pointer hover:bg-primary/10 transition-colors border border-primary/20">
          <input id="reg-subscribe" type="checkbox" checked class="mt-0.5 w-4 h-4 accent-[#006b3f] flex-shrink-0"/>
          <div>
            <p class="font-label-sm text-label-sm text-on-surface font-semibold">Recevoir les prévisions mensuelles</p>
            <p class="font-caption text-caption text-on-surface-variant mt-0.5">Rapport PDF + synthèse envoyés chaque mois.</p>
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
</div>

<!-- ===== TOAST ===== -->
<div id="auth-toast" class="fixed bottom-28 left-1/2 -translate-x-1/2 z-[400] hidden">
  <div class="bg-on-surface text-background px-6 py-4 rounded-2xl shadow-2xl flex items-center gap-3 max-w-sm">
    <span class="material-symbols-outlined text-inverse-primary text-[22px]" style="font-variation-settings:'FILL' 1;" id="toast-icon">check_circle</span>
    <p class="font-body-md text-body-md" id="toast-message"></p>
  </div>
</div>`;

  document.body.insertAdjacentHTML('beforeend', html);
})();

/* ── Utilitaires localStorage ── */
function getUsers()   { return JSON.parse(localStorage.getItem('mitcho_users') || '[]'); }
function getSession() { return JSON.parse(sessionStorage.getItem('mitcho_session') || 'null'); }
function saveUsers(u) { localStorage.setItem('mitcho_users', JSON.stringify(u)); }
function setSession(user) {
  sessionStorage.setItem('mitcho_session', JSON.stringify({ ...user, loggedIn: true }));
}

/* ── Sélection du profil (étape 1) ── */
function selectProfile(profile) {
  _selectedProfile = profile;

  // Feedback visuel sur les cartes
  ['agriculteur', 'decideur'].forEach(p => {
    const card = document.getElementById(`card-${p}`);
    if (!card) return;
    if (p === profile) {
      card.classList.add('border-primary', 'bg-primary/5', 'shadow-md');
    } else {
      card.classList.remove('border-primary', 'bg-primary/5', 'shadow-md');
    }
  });

  // Badge profil
  const isAgri = profile === 'agriculteur';
  document.getElementById('badge-icon').textContent = isAgri ? 'agriculture' : 'account_balance';
  document.getElementById('badge-label').textContent = isAgri ? 'Agriculteur' : 'Décideur public';

  // Si déjà connecté mais sans profil → sauvegarder le choix directement et fermer
  const session = getSession();
  if (session?.loggedIn && !session.profile) {
    const updated = { ...session, profile };
    setSession(updated);
    _forcedAuth = false;
    closeAuthModal();
    refreshAuthNav();
    _dispatchAuthChanged();
    const msg = isAgri ? 'Profil Agriculteur activé !' : 'Profil Décideur activé !';
    showToast(msg, 'check_circle');
    return;
  }

  // Sinon → transition vers étape 2 (formulaire)
  setTimeout(() => {
    document.getElementById('step-profile').classList.add('hidden');
    document.getElementById('step-auth').classList.remove('hidden');
    document.getElementById('auth-header-sub').textContent = isAgri
      ? 'Espace agriculteur · Conseils pratiques'
      : 'Espace décideur · Analyses stratégiques';
    setTimeout(() => document.querySelector('#form-register input')?.focus(), 80);
  }, 200);
}

/* ── Ouvrir uniquement le sélecteur de profil (déjà connecté, profil manquant) ── */
function _openProfilePicker() {
  _selectedProfile = null;
  _forcedAuth = true;
  document.getElementById('step-profile').classList.remove('hidden');
  document.getElementById('step-auth').classList.add('hidden');
  document.getElementById('auth-header-sub').textContent = 'Choisissez votre profil pour continuer';

  const closeBtn = document.getElementById('auth-close-btn');
  if (closeBtn) closeBtn.classList.add('hidden');

  const overlay = document.getElementById('auth-overlay');
  overlay.classList.remove('hidden');
  overlay.classList.add('flex');
}

/* ── Retour à la sélection du profil ── */
function goBackToProfile() {
  _selectedProfile = null;
  document.getElementById('step-auth').classList.add('hidden');
  document.getElementById('step-profile').classList.remove('hidden');
  document.getElementById('auth-header-sub').textContent = 'Intelligence alimentaire · Bénin';
  ['agriculteur', 'decideur'].forEach(p => {
    document.getElementById(`card-${p}`)?.classList.remove('border-primary', 'bg-primary/5', 'shadow-md');
  });
}

/* ── Ouvrir le modal ── */
function openAuthModal(tab = 'register', callback = null, forced = false) {
  _afterAuthCallback = callback;
  _forcedAuth = forced;

  const session = getSession();
  if (session?.loggedIn) {
    if (callback) callback();
    return;
  }

  // Réinitialiser à l'étape 1
  _selectedProfile = null;
  document.getElementById('step-profile').classList.remove('hidden');
  document.getElementById('step-auth').classList.add('hidden');
  document.getElementById('auth-header-sub').textContent = 'Intelligence alimentaire · Bénin';

  // Masquer bouton fermeture si auth forcée
  const closeBtn = document.getElementById('auth-close-btn');
  if (closeBtn) closeBtn.classList.toggle('hidden', forced);

  switchTab(tab);
  const overlay = document.getElementById('auth-overlay');
  overlay.classList.remove('hidden');
  overlay.classList.add('flex');
}

/* ── Fermer le modal ── */
function closeAuthModal() {
  if (_forcedAuth) return;
  const overlay = document.getElementById('auth-overlay');
  overlay.classList.add('hidden');
  overlay.classList.remove('flex');
}

/* ── Clic en dehors (non forcé seulement) ── */
document.addEventListener('click', (e) => {
  if (_forcedAuth) return;
  if (e.target === document.getElementById('auth-overlay')) closeAuthModal();
});

/* ── Switcher les onglets ── */
function switchTab(tab) {
  const isRegister = tab === 'register';
  document.getElementById('form-register').classList.toggle('hidden', !isRegister);
  document.getElementById('form-login').classList.toggle('hidden', isRegister);
  document.getElementById('tab-register').className = `flex-1 py-4 font-label-sm text-label-sm transition-all border-b-2 ${isRegister ? 'text-primary border-primary' : 'text-on-surface-variant border-transparent hover:text-primary'}`;
  document.getElementById('tab-login').className    = `flex-1 py-4 font-label-sm text-label-sm transition-all border-b-2 ${!isRegister ? 'text-primary border-primary' : 'text-on-surface-variant border-transparent hover:text-primary'}`;
}

/* ── Inscription ── */
async function handleRegister(e) {
  e.preventDefault();
  const name       = document.getElementById('reg-name').value.trim();
  const email      = document.getElementById('reg-email').value.trim().toLowerCase();
  const password   = document.getElementById('reg-password').value;
  const subscribed = document.getElementById('reg-subscribe').checked;
  const profile    = _selectedProfile || 'decideur';
  const errEl      = document.getElementById('reg-error');
  errEl.classList.add('hidden');

  try {
    const res = await fetch(`${AUTH_BACKEND}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, name, password, subscribe: subscribed, profile }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Erreur inscription');

    _forcedAuth = false;
    setSession({ ...data.user, token: data.access_token, loggedIn: true });
    closeAuthModal();
    refreshAuthNav();
    _dispatchAuthChanged();
    const isAgri = profile === 'agriculteur';
    const msg = subscribed
      ? `Bienvenue ${name.split(' ')[0]} ! Prévisions mensuelles activées.`
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

  // Fallback localStorage
  const users = getUsers();
  if (users.find(u => u.email === email)) {
    errEl.textContent = 'Un compte existe déjà avec cet email. Connectez-vous.';
    errEl.classList.remove('hidden');
    return;
  }
  const user = { name, email, password, profile, subscribed, createdAt: new Date().toISOString() };
  users.push(user);
  saveUsers(users);
  _forcedAuth = false;
  setSession({ ...user, loggedIn: true });
  closeAuthModal();
  refreshAuthNav();
  _dispatchAuthChanged();
  showToast(`Bienvenue, ${name.split(' ')[0]} !`, 'check_circle');
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

    _forcedAuth = false;
    setSession({ ...data.user, token: data.access_token, loggedIn: true });
    closeAuthModal();
    refreshAuthNav();
    _dispatchAuthChanged();
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

  // Fallback localStorage
  const user = getUsers().find(u => u.email === email && u.password === password);
  if (!user) {
    errEl.textContent = 'Email ou mot de passe incorrect.';
    errEl.classList.remove('hidden');
    return;
  }
  _forcedAuth = false;
  setSession({ ...user, loggedIn: true });
  closeAuthModal();
  refreshAuthNav();
  _dispatchAuthChanged();
  showToast(`Bon retour, ${user.name.split(' ')[0]} !`, 'check_circle');
  if (_afterAuthCallback) { _afterAuthCallback(); _afterAuthCallback = null; }
}

/* ── Déconnexion ── */
function logout() {
  sessionStorage.removeItem('mitcho_session');
  refreshAuthNav();
  showToast('Vous êtes déconnecté.', 'logout');
  // Ré-ouvrir le modal forcé après déconnexion
  setTimeout(() => openAuthModal('register', null, true), 600);
}

/* ── Token JWT ── */
function getAuthToken() {
  return getSession()?.token || null;
}

/* ── Profil utilisateur courant ── */
function getUserProfile() {
  return getSession()?.profile || 'decideur';
}

/* ── Mise à jour de la nav ── */
function _dispatchAuthChanged() {
  // Appel direct si la page expose la fonction (plus fiable que l'événement)
  if (typeof window.applyProfileContent === 'function') {
    window.applyProfileContent();
  }
  window.dispatchEvent(new Event('mitcho-auth-changed'));
}

function refreshAuthNav() {
  const session = getSession();
  const loggedIn = !!session?.loggedIn;

  ['btn-login', 'btn-logout', 'nav-username'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    if (id === 'btn-login')    el.classList.toggle('hidden', loggedIn);
    if (id === 'btn-logout')   el.classList.toggle('hidden', !loggedIn);
    if (id === 'nav-username') {
      el.classList.toggle('hidden', !loggedIn);
      if (loggedIn) {
        const profile = session.profile || 'decideur';
        const icon = profile === 'agriculteur' ? 'agriculture' : 'account_balance';
        el.innerHTML = `<span class="material-symbols-outlined text-[14px] align-middle" style="font-variation-settings:'FILL' 1;">${icon}</span> ${session.name.split(' ')[0]}`;
      }
    }
  });
}

/* ── Toast ── */
function showToast(message, icon = 'check_circle') {
  const toast = document.getElementById('auth-toast');
  document.getElementById('toast-message').textContent = message;
  document.getElementById('toast-icon').textContent    = icon;
  toast.classList.remove('hidden');
  setTimeout(() => toast.classList.add('hidden'), 4000);
}

/* ── Init : auth obligatoire au chargement si pas de session ── */
function _initAuth() {
  refreshAuthNav();
  const session = getSession();

  // Session sans profil → demander le choix de profil sans déconnecter
  if (session?.loggedIn && !session?.profile) {
    setTimeout(() => _openProfilePicker(), 400);
    return;
  }

  if (!session?.loggedIn) {
    setTimeout(() => openAuthModal('register', null, true), 400);
  }
}

// DOMContentLoaded peut déjà être passé quand ce script charge (fin de body)
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', _initAuth);
} else {
  _initAuth();
}
