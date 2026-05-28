/* ============================================================
   MITCHÔ — Assistant IA
   Mode backend  : POST /analysis/chat  (FastAPI + RAG)
   Mode fallback : Groq direct (si le backend n'est pas démarré)
   ============================================================ */

const BACKEND_URL = window.MITCHO_API || 'http://localhost:8000';
const GROQ_URL    = 'https://api.groq.com/openai/v1/chat/completions';
const GROQ_KEY    = window.MITCHO_GROQ_KEY || ''; // Définie via config.js (non committé)
const GROQ_MODEL  = 'llama-3.3-70b-versatile';

const SYSTEM_PROMPT = `Tu es l'assistant officiel de MITCHÔ, une plateforme d'intelligence publique orientée décision, conçue pour anticiper les crises alimentaires au Bénin.

MITCHÔ est un système d'intelligence stratégique destiné aux institutions publiques béninoises travaillant sur la sécurité alimentaire. Il transforme des signaux dispersés — marchés agricoles, médias, environnement — en analyses lisibles et en recommandations actionnables pour les décideurs de l'État.

Ce que fait MITCHÔ concrètement :
- Surveille les tendances des prix agricoles (maïs, riz, mil, sorgho, igname, haricot, tomate...)
- Analyse des signaux indirects via GDELT (médias, événements climatiques, tensions géopolitiques)
- Détecte des signaux faibles de tension ou de stabilité alimentaire
- Génère des résumés narratifs en langage naturel + recommandations stratégiques
- Produit des rapports PDF institutionnels mensuels et hebdomadaires
- Envoie des alertes email aux décideurs abonnés

Le problème qu'il résout :
1. Les données sur les marchés agricoles béninois sont fragmentées et tardives
2. Les signaux de crise (inflation, pénuries, tensions régionales) sont mal détectés à temps
3. Les décisions publiques sont réactives plutôt que préventives → crises anticipées trop tard

Pages du site (2 pages uniquement) :
- Accueil (index.html) : présente le contexte, le problème et la solution MITCHÔ
- Prévisions Mensuelles (tendances.html) : analyse du mois, prix agricoles, signaux GDELT, recommandations stratégiques, téléchargement du rapport PDF (nécessite un compte)

Pour télécharger le rapport PDF ou recevoir les prévisions par email, l'utilisateur doit créer un compte ou se connecter.

Ton rôle : Réponds toujours en français, avec un ton professionnel et institutionnel. Sois concis (3-4 phrases max). Si tu ne connais pas une donnée précise, dis-le et oriente vers les rapports disponibles. Tu es un assistant de démonstration — les données réelles sont traitées par le moteur analytique de MITCHÔ.`;

/*
  Historique au format OpenAI :
  [{ role: "system"|"user"|"assistant", content: "..." }]
*/
let conversationHistory = [
  { role: 'system', content: SYSTEM_PROMPT }
];
let isTyping = false;

/* ── Ouverture / fermeture ── */
function toggleChat() {
  const win  = document.getElementById('ai-chat-window');
  const icon = document.getElementById('fab-icon');
  if (!win) return;

  if (win.classList.contains('hidden')) {
    win.classList.remove('hidden');
    win.classList.add('flex');
    requestAnimationFrame(() => {
      win.classList.remove('scale-90', 'opacity-0');
      win.classList.add('scale-100', 'opacity-100');
    });
    icon.textContent = 'close';
    setTimeout(() => document.getElementById('chat-input')?.focus(), 320);
  } else {
    win.classList.remove('scale-100', 'opacity-100');
    win.classList.add('scale-90', 'opacity-0');
    setTimeout(() => {
      win.classList.add('hidden');
      win.classList.remove('flex');
    }, 280);
    icon.textContent = 'smart_toy';
  }
}

/* ── Question rapide ── */
function askQuestion(btn) {
  sendMessage(btn.textContent.trim());
}

/* ── Envoi principal ── */
async function sendMessage(override) {
  if (isTyping) return;

  const input = document.getElementById('chat-input');
  const text  = override || (input ? input.value.trim() : '');
  if (!text) return;
  if (input && !override) input.value = '';

  appendMessage(text, 'user');
  const tid = showTyping();
  isTyping  = true;

  try {
    const reply = await callBackendOrGroq(text);
    removeTyping(tid);
    appendMessage(reply, 'ai');
  } catch (err) {
    removeTyping(tid);
    console.error('[MITCHÔ Chat] Erreur :', err);
    appendMessage(getFallbackReply(text), 'ai');
  } finally {
    isTyping = false;
  }
}

/* ── Appel backend RAG (avec fallback Groq direct) ── */
async function callBackendOrGroq(userMessage) {
  const historyForApi = conversationHistory
    .filter(m => m.role !== 'system')
    .slice(-6);

  try {
    const res = await fetch(`${BACKEND_URL}/analysis/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: userMessage,
        history: historyForApi,
        profile: (typeof getUserProfile === 'function') ? getUserProfile() : 'decideur',
      }),
    });
    if (!res.ok) throw new Error(`Backend HTTP ${res.status}`);
    const data = await res.json();
    const reply = data.reply;
    conversationHistory.push({ role: 'user', content: userMessage });
    conversationHistory.push({ role: 'assistant', content: reply });
    return reply;
  } catch (backendErr) {
    console.info('[MITCHÔ Chat] Backend indisponible, fallback Groq direct.', backendErr.message);
    return await callGroqDirect(userMessage);
  }
}

/* ── Appel Groq direct (fallback si backend non démarré) ── */
async function callGroqDirect(userMessage) {
  conversationHistory.push({ role: 'user', content: userMessage });

  const res = await fetch(GROQ_URL, {
    method: 'POST',
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${GROQ_KEY}`,
    },
    body: JSON.stringify({
      model:       GROQ_MODEL,
      messages:    conversationHistory,
      temperature: 0.5,
      max_tokens:  450,
    }),
  });

  if (!res.ok) {
    conversationHistory.pop();
    let detail = `HTTP ${res.status}`;
    try { const e = await res.json(); detail = e?.error?.message || detail; } catch (_) {}
    if (res.status === 429) throw new Error('Quota atteint — réessayez dans quelques secondes.');
    throw new Error(detail);
  }

  const data   = await res.json();
  const aiText = data?.choices?.[0]?.message?.content;
  if (!aiText) { conversationHistory.pop(); throw new Error('Réponse vide.'); }

  conversationHistory.push({ role: 'assistant', content: aiText });
  return aiText;
}

/* ── Réponses de secours (si API indisponible) ── */
function getFallbackReply(question) {
  const q = question.toLowerCase();
  if (q.includes('maïs') || q.includes('riz') || q.includes('mil') || q.includes('prix') || q.includes('agricol')) {
    return "D'après nos dernières analyses, les prix du maïs et du riz montrent une légère tension saisonnière dans les marchés du nord du Bénin. Notre moteur d'analyse surveille ces tendances en continu. Consultez la page Tendances pour l'analyse complète.";
  }
  if (q.includes('fonctionne') || q.includes('comment') || q.includes('marche') || q.includes('mitchô') || q.includes('mitcho')) {
    return "MITCHÔ collecte des données de marchés agricoles, des signaux médiatiques via GDELT et des indicateurs économiques. Un moteur d'analyse IA les transforme en résumés lisibles et recommandations stratégiques pour les décideurs béninois.";
  }
  if (q.includes('alerte') || q.includes('abonnement') || q.includes('email')) {
    return "Nos alertes stratégiques sont envoyées par email chaque semaine ou chaque mois selon votre préférence. Rendez-vous sur la page Abonnement pour vous inscrire et choisir votre fréquence.";
  }
  if (q.includes('rapport') || q.includes('pdf') || q.includes('télécharg')) {
    return "MITCHÔ génère des rapports PDF institutionnels chaque mois. Ils incluent les tendances des prix agricoles, les signaux de tension détectés et des recommandations prêtes à être transmises aux décideurs.";
  }
  if (q.includes('crise') || q.includes('sécurité') || q.includes('alimentaire') || q.includes('bénin')) {
    return "La sécurité alimentaire au Bénin est exposée à des tensions saisonnières, des chocs climatiques et des volatilités de prix régionales. MITCHÔ identifie ces signaux en amont pour permettre une réponse préventive plutôt que réactive.";
  }
  if (q.includes('économie') || q.includes('économique') || q.includes('etat')) {
    return "L'économie agricole béninoise présente des signaux mixtes ce mois-ci : stabilité relative dans le sud, tensions logistiques au nord. Notre analyse intègre les données de marché et les sources médiatiques pour une vision complète.";
  }
  return "Merci pour votre question. MITCHÔ analyse en continu les signaux agricoles, économiques et médiatiques pour vous fournir des recommandations stratégiques. Pour une réponse détaillée, consultez nos rapports ou abonnez-vous à nos alertes hebdomadaires.";
}

/* ── Affichage message ── */
function appendMessage(text, type) {
  const container = document.getElementById('chat-messages');
  if (!container) return;
  const div = document.createElement('div');
  if (type === 'user') {
    div.className = 'ml-auto bg-primary text-on-primary p-3 rounded-2xl rounded-tr-none max-w-[82%] text-sm leading-relaxed';
  } else {
    div.className = 'bg-white p-4 rounded-2xl rounded-tl-none border border-outline-variant/20 shadow-sm max-w-[90%] text-sm text-on-surface-variant leading-relaxed';
  }
  div.textContent = text;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

/* ── Indicateur de frappe ── */
function showTyping() {
  const container = document.getElementById('chat-messages');
  if (!container) return null;
  const id  = 'typing-' + Date.now();
  const div = document.createElement('div');
  div.id        = id;
  div.className = 'bg-white p-4 rounded-2xl rounded-tl-none border border-outline-variant/20 shadow-sm max-w-[90%] flex items-center gap-1.5';
  div.innerHTML = `
    <span class="w-2 h-2 bg-primary/60 rounded-full animate-bounce" style="animation-delay:0ms"></span>
    <span class="w-2 h-2 bg-primary/60 rounded-full animate-bounce" style="animation-delay:150ms"></span>
    <span class="w-2 h-2 bg-primary/60 rounded-full animate-bounce" style="animation-delay:300ms"></span>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return id;
}

function removeTyping(id) {
  if (id) document.getElementById(id)?.remove();
}
