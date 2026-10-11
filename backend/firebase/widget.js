import { initializeApp } from 'firebase/app';
import { getAuth, connectAuthEmulator, onAuthStateChanged, createUserWithEmailAndPassword,
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
}
async function run(action, label = 'Request') {
  if (busy) return;
  busy = true;
  try { await action(); }
  catch (error) {
    reportError(error, label);
  } finally { busy = false; }
}
function input(label, type, autocomplete, parent) {
  const wrapper = element('label', `${label} `, parent);
  const field = element('input', null, wrapper);
  field.type = type;
  field.autocomplete = autocomplete;
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
  root.replaceChildren();
  element('p', 'Read or comment here without GitHub. Display names are chosen by users; discussion is separate from record evidence.');
  message = element('p', '');
  message.setAttribute('role', 'status');
  const account = element('div');
  const composer = element('div');
  const comments = element('div');
  const taskKey = `${root.dataset.recordId}__${root.dataset.taskId}`;
  const commentsRef = collection(db, `tasks/${taskKey}/comments`);

  async function load() {
    const snapshots = await getDocs(query(commentsRef, orderBy('createdAt', 'desc'), limit(50)));
    comments.replaceChildren();
    if (snapshots.empty) element('p', 'No comments yet.', comments);
    for (const snapshot of snapshots.docs.reverse()) {
      const data = snapshot.data();
      const article = element('article', null, comments);
      article.className = 'native-comment';
      const timestamp = data.createdAt?.toDate().toLocaleString() || '';
      element('p', `${data.name} · ${timestamp}`, article).className = 'meta';
      element('p', data.body, article).className = 'native-comment-body';
      if (auth.currentUser?.uid === data.uid) {
        button('Delete my comment', async () => { await deleteDoc(snapshot.ref); await load(); }, article);
      }
    }
  }
  button('Refresh comments', load);
  function renderAccount(user) {
    account.replaceChildren();
    composer.replaceChildren();
    if (!user) {
      const form = element('form', null, account);
      const email = input('Email', 'email', 'email', form);
      const password = input('Password', 'password', 'current-password', form);
      const name = input('Display name (for registration)', 'text', 'nickname', form);
      name.maxLength = 60;
      const login = element('button', 'Sign in', form);
      login.type = 'submit';
      form.addEventListener('submit', event => {
        event.preventDefault();
        run(() => signInWithEmailAndPassword(auth, email.value.trim(), password.value));
      });
      button('Create account', async () => {
        const displayName = name.value.trim();
        if (!displayName || displayName.length > 60) { message.textContent = 'Choose a display name of 1–60 characters.'; return; }
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
          message.textContent = 'Account created. Check your email for the verification link.';
        } catch (error) {
          reportError(error, 'Send verification email');
          message.textContent = `Your account was created, but the verification email was not sent. ${message.textContent}`;
        }
      }, form);
      button('Reset password', async () => {
        await sendPasswordResetEmail(auth, email.value.trim());
        message.textContent = 'If this address has an account, a reset email will arrive.';
      }, form);
    } else {
      element('p', `Signed in as ${user.displayName || 'your account'}.`, account);
      button('Sign out', () => signOut(auth), account);
      if (!user.emailVerified) {
        element('p', 'Confirm your email before posting.', composer);
        button('Send verification email', async () => {
          await sendEmailVerification(user);
          message.textContent = 'Check your email for the verification link.';
        }, composer);
        button('I verified my email', async () => {
          await reload(user);
          await user.getIdToken(true);
          // Re-render using the refreshed user without changing persistence.
          location.reload();
        }, composer);
      } else {
        const form = element('form', null, composer);
        const label = element('label', 'Your comment ', form);
        const body = element('textarea', null, label);
        body.maxLength = 4000;
        body.required = true;
        body.rows = 5;
        const submit = element('button', 'Post comment', form);
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
            message.textContent = 'Comment posted.';
            await load();
          });
        });
      }
    }
    run(load);
  }
  onAuthStateChanged(auth, renderAccount);
  await load();
}
