import { initializeApp } from 'firebase/app';
import { getAuth, setPersistence, browserLocalPersistence, connectAuthEmulator, onAuthStateChanged, createUserWithEmailAndPassword,
  signInWithEmailAndPassword, updateProfile, sendEmailVerification, sendPasswordResetEmail,
  signOut, reload } from 'firebase/auth';
import { getFirestore, connectFirestoreEmulator, collection, doc, query, orderBy, limit,
  getDocs, writeBatch, serverTimestamp, deleteDoc } from 'firebase/firestore';

const root = document.querySelector('[data-native-discussion]');
if (root) start().catch(() => { root.textContent = 'On-site comments are unavailable right now.'; });

function element(tag, text, parent = root) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  parent.append(node);
  return node;
}
function button(label, action, parent) {
  const node = element('button', label, parent);
  node.type = 'button';
  node.addEventListener('click', () => run(action, label));
  return node;
}
let busy = false;
let message;
function showMessage(text, kind = 'info') {
  message.textContent = text;
  message.dataset.kind = kind;
}
function reportError(error, action) {
  const code = error.code;
  // Log only the operation and code, never credentials or the SDK error object.
  console.warn(`Significance: ${action} failed (${code || 'unknown'}).`);
  message.textContent = code === 'permission-denied'
    ? 'Posting was refused. Confirm your email, then wait 30 seconds between comments.'
    : code === 'auth/weak-password' ? 'Choose a stronger password.'
    : code === 'auth/invalid-email' ? 'Enter a valid email address.'
    : code === 'auth/too-many-requests'
    ? 'Firebase temporarily blocked this request. Wait before trying again.'
    : code === 'resource-exhausted' || code === 'auth/quota-exceeded'
    ? 'The service quota was reached. Please try again later.'
    : 'That action could not be completed. Check your details and try again.';
  message.dataset.kind = 'error';
}
async function run(action, label = 'Request') {
  if (busy) return;
  busy = true;
  root.setAttribute('aria-busy', 'true');
  root.querySelectorAll('button').forEach(node => { node.disabled = true; });
  try { await action(); }
  catch (error) {
    reportError(error, label);
  } finally {
    busy = false;
    root.removeAttribute('aria-busy');
    root.querySelectorAll('button').forEach(node => { node.disabled = false; });
  }
}
function input(label, type, autocomplete, parent) {
  const wrapper = element('label', null, parent);
  element('span', label, wrapper);
  const field = element('input', null, wrapper);
  field.type = type;
  field.autocomplete = autocomplete;
  field.required = true;
  return field;
}

async function start() {
  const response = await fetch(root.dataset.configUrl, { cache: 'no-store' });
  if (!response.ok) { root.textContent = 'On-site comments aren’t available yet.'; return; }
  const config = await response.json();
  const app = initializeApp(config);
  const auth = getAuth(app);
  const db = getFirestore(app);
  if (config.emulators) {
    if (!['localhost', '127.0.0.1'].includes(location.hostname) || !config.projectId.startsWith('demo-')) {
      throw new Error('Emulators are local only');
    }
    connectAuthEmulator(auth, 'http://127.0.0.1:9099', { disableWarnings: true });
    connectFirestoreEmulator(db, '127.0.0.1', 8088);
  }
  await setPersistence(auth, browserLocalPersistence);
  root.replaceChildren();
  message = element('p', '');
  message.className = 'discussion-notice';
  message.setAttribute('role', 'status');
  message.setAttribute('aria-live', 'polite');
  const layout = element('div');
  layout.className = 'discussion-layout';
  const account = element('div', null, layout);
  account.className = 'discussion-account';
  const thread = element('div', null, layout);
  thread.className = 'discussion-thread';
  const composer = element('div', null, thread);
  composer.className = 'discussion-composer';
  const threadHeader = element('div', null, thread);
  threadHeader.className = 'discussion-thread-header';
  const count = element('h3', 'Discussion', threadHeader);
  button('Refresh', load, threadHeader).className = 'discussion-text-button';
  const comments = element('div', null, thread);
  let authMode = 'signin';
  let authEmail = '';
  const taskKey = `${root.dataset.recordId}__${root.dataset.taskId}`;
  const commentsRef = collection(db, `tasks/${taskKey}/comments`);

  async function load() {
    const snapshots = await getDocs(query(commentsRef, orderBy('createdAt', 'desc'), limit(50)));
    comments.replaceChildren();
    count.textContent = `Discussion · ${snapshots.size}${snapshots.size === 50 ? '+' : ''}`;
    if (snapshots.empty) {
      const empty = element('div', null, comments);
      empty.className = 'discussion-empty';
      element('p', 'Start the conversation', empty).className = 'discussion-empty-title';
      element('p', 'Ask about a passage, share what you tried, or help someone find a starting point.', empty);
    }
    for (const snapshot of snapshots.docs.reverse()) {
      const data = snapshot.data();
      const article = element('article', null, comments);
      article.className = 'native-comment';
      const header = element('div', null, article);
      header.className = 'native-comment-header';
      const avatar = element('span', (data.name || '?').slice(0, 1).toUpperCase(), header);
      avatar.className = 'discussion-avatar';
      avatar.setAttribute('aria-hidden', 'true');
      element('strong', data.name, header);
      const date = data.createdAt?.toDate();
      if (date) {
        const time = element('time', date.toLocaleString(), header);
        time.dateTime = date.toISOString();
      }
      element('p', data.body, article).className = 'native-comment-body';
      if (auth.currentUser?.uid === data.uid) {
        button('Delete my comment', async () => { await deleteDoc(snapshot.ref); await load(); showMessage('Your comment was deleted.'); }, article).className = 'discussion-text-button';
      }
    }
  }
  function renderAccount(user) {
    account.hidden = Boolean(user);
    layout.classList.toggle('discussion-layout-signed-in', Boolean(user));
    account.replaceChildren();
    composer.replaceChildren();
    if (!user) {
      const switcher = element('div', null, account);
      switcher.className = 'discussion-auth-switch';
      switcher.setAttribute('aria-label', 'Account options');
      for (const [mode, label] of [['signin', 'Sign in'], ['signup', 'Create account']]) {
        const toggle = button(label, () => {
          authEmail = email.value;
          authMode = mode;
          showMessage('');
          renderAccount(null);
        }, switcher);
        toggle.setAttribute('aria-pressed', String(authMode === mode));
      }
      element('h3', authMode === 'signup' ? 'Join the discussion' : authMode === 'reset' ? 'Reset your password' : 'Welcome back', account);
      element('p', authMode === 'signup' ? 'Choose a public name. Confirm your email before posting.' : authMode === 'reset' ? 'We’ll email you a link to choose a new password.' : 'Sign in to ask a question or share a comment.', account).className = 'discussion-help';
      const form = element('form', null, account);
      const email = input('Email', 'email', 'email', form);
      email.value = authEmail;
      email.placeholder = 'you@example.com';
      const password = authMode === 'reset' ? null : input('Password', 'password', authMode === 'signup' ? 'new-password' : 'current-password', form);
      const name = authMode === 'signup' ? input('Public display name', 'text', 'nickname', form) : null;
      if (name) name.maxLength = 60;
      const login = element('button', authMode === 'signup' ? 'Create account' : authMode === 'reset' ? 'Send reset link' : 'Sign in', form);
      login.className = 'discussion-primary';
      login.type = 'submit';
      form.addEventListener('submit', event => {
        event.preventDefault();
        run(async () => {
          authEmail = email.value.trim();
          if (authMode === 'reset') {
            await sendPasswordResetEmail(auth, authEmail);
            showMessage('If this address has an account, a reset email will arrive. Check your inbox and spam folder.');
          } else if (authMode === 'signup') {
            await register();
          } else {
            await signInWithEmailAndPassword(auth, authEmail, password.value);
            await load();
            showMessage('You’re signed in.');
          }
        }, login.textContent);
      });
      async function register() {
        const displayName = name.value.trim();
        if (!displayName || displayName.length > 60) { showMessage('Choose a display name of 1–60 characters.', 'error'); return; }
        const credential = await createUserWithEmailAndPassword(auth, email.value.trim(), password.value);
        try {
          await updateProfile(credential.user, { displayName });
        } catch (error) {
          reportError(error, 'Save display name');
          message.textContent = `Your account was created, but the display name was not saved. ${message.textContent}`;
          return;
        }
        renderAccount(credential.user);
        try {
          await sendEmailVerification(credential.user);
          showMessage('Account created. Check your email for the verification link.');
        } catch (error) {
          reportError(error, 'Send verification email');
          message.textContent = `Your account was created, but the verification email was not sent. ${message.textContent}`;
        }
      }
      button(authMode === 'reset' ? 'Back to sign in' : 'Forgot password?', () => {
        authEmail = email.value;
        authMode = authMode === 'reset' ? 'signin' : 'reset';
        showMessage('');
        renderAccount(null);
      }, account).className = 'discussion-text-button';
      element('p', 'Your display name is public. Your email is not shown in comments.', account).className = 'discussion-privacy';
      element('h3', 'Have a question?', composer);
      element('p', 'You can read the discussion without an account. Sign in to add your thoughts.', composer).className = 'discussion-help';
    } else {
      const identity = element('div', null, composer);
      identity.className = 'discussion-identity';
      element('span', `Commenting as ${user.displayName || 'Contributor'}`, identity);
      button('Sign out', async () => { await signOut(auth); showMessage('You’re signed out.'); }, identity).className = 'discussion-text-button';
      if (!user.emailVerified) {
        element('h3', 'Check your inbox', composer);
        element('p', 'Open the verification link in your email, then check your status here. Check your spam folder if it hasn’t arrived.', composer).className = 'discussion-help';
        const actions = element('div', null, composer);
        actions.className = 'discussion-actions';
        button('Send verification email', async () => {
          await sendEmailVerification(user);
          showMessage('Verification email sent. Check your inbox and spam folder.');
        }, actions);
        button('Check verification status', async () => {
          await reload(user);
          await user.getIdToken(true);
          renderAccount(user);
          await load();
          showMessage(user.emailVerified ? 'Email confirmed. You can now comment.' : 'Your email is not confirmed yet. Open the link in your verification email first.');
        }, actions).className = 'discussion-primary';
      } else {
        element('h3', 'Add to the discussion', composer);
        const form = element('form', null, composer);
        const label = element('label', null, form);
        element('span', 'Your comment or question', label);
        const body = element('textarea', null, label);
        body.maxLength = 4000;
        body.required = true;
        body.rows = 4;
        body.placeholder = 'Point to a passage, explain what you tried, or ask a specific question…';
        const footer = element('div', null, form);
        footer.className = 'discussion-composer-footer';
        const remaining = element('span', '0 / 4,000', footer);
        remaining.className = 'discussion-help';
        body.addEventListener('input', () => { remaining.textContent = `${body.value.length.toLocaleString()} / 4,000`; });
        const submit = element('button', 'Post comment', footer);
        submit.className = 'discussion-primary';
        submit.type = 'submit';
        form.addEventListener('submit', event => {
          event.preventDefault();
          run(async () => {
            const text = body.value.trim();
            if (!text) return;
            const reference = doc(commentsRef);
            const batch = writeBatch(db);
            batch.set(reference, { uid: user.uid, name: (user.displayName || 'Contributor').slice(0, 60), body: text, createdAt: serverTimestamp() });
            batch.set(doc(db, `postLimits/${user.uid}`), { lastPosted: serverTimestamp(), lastComment: `${taskKey}/${reference.id}` });
            await batch.commit();
            body.value = '';
            remaining.textContent = '0 / 4,000';
            showMessage('Comment posted.');
            await load();
          }, 'Post comment');
        });
      }
    }
    if (!busy) run(load, 'Read comments');
  }
  onAuthStateChanged(auth, renderAccount);
  await load();
}
