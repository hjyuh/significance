import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import { test } from 'node:test';

// A minimal DOM lets us exercise form handlers without production credentials.
class Element {
  constructor(tag) {
    this.tag = tag; this.children = []; this.dataset = {}; this.attrs = {};
    this.events = {}; this.textContent = ''; this.className = '';
    this.classList = { toggle() {}, add() {} };
  }
  append(child) { this.children.push(child); }
  insertBefore(child, before) { this.children.splice(this.children.indexOf(before), 0, child); }
  get isConnected() { return true; }
  replaceChildren() { this.children = []; }
  setAttribute(key, value) { this.attrs[key] = value; }
  hasAttribute(key) { return key in this.attrs; }
  removeAttribute(key) { delete this.attrs[key]; }
  addEventListener(name, fn) { this.events[name] = fn; }
  querySelectorAll(tag) { return this.children.flatMap(c => [...(c.tag === tag ? [c] : []), ...c.querySelectorAll(tag)]); }
  reset() { this.querySelectorAll('input').forEach(field => { field.value = ''; }); }
}

test('profile keeps guests out and requires matching passwords and successful reauthentication', async () => {
  const root = new Element('div');
  root.attrs['data-native-profile'] = '';
  root.dataset.configUrl = '/config.json';
  const auth = { currentUser: null };
  let listener, failReauth = false, reauthCalls = 0, passwordCalls = 0, commentReads = 0;
  let savedDetails;
  const context = vm.createContext({
    document: { querySelector: () => root, createElement: tag => new Element(tag) },
    fetch: async () => ({ ok: true, json: async () => ({ projectId: 'demo' }) }),
    console: { warn() {} }, initializeApp: c => c, getAuth: () => auth,
    setPersistence: async () => {}, browserLocalPersistence: {}, getFirestore: () => ({}),
    doc: () => ({}), getDoc: async () => ({ exists: () => false }),
    setDoc: async (reference, data) => { savedDetails = { ...data }; },
    getDocs: async () => { commentReads++; },
    onAuthStateChanged: (a, fn) => { listener = fn; fn(null); },
    EmailAuthProvider: { credential: (email, password) => ({ email, password }) },
    reauthenticateWithCredential: async () => {
      reauthCalls++;
      if (failReauth) throw { code: 'auth/invalid-credential' };
    },
    updatePassword: async () => { passwordCalls++; },
  });
  const source = (await readFile(new URL('./widget.js', import.meta.url), 'utf8'))
    .replace(/import\s+\{[\s\S]*?\}\s+from\s+'[^']+';/g, '');
  vm.runInContext(source, context);
  const settle = () => new Promise(resolve => setImmediate(resolve));
  const buttons = () => root.querySelectorAll('button');
  await settle();
  assert.ok(buttons().some(n => n.textContent === 'Sign in'));
  assert.ok(!buttons().some(n => n.textContent === 'Change password'));
  const user = { displayName: 'Test', email: 'test@example.test', emailVerified: true,
    metadata: { creationTime: '2026-10-01T00:00:00Z' } };
  auth.currentUser = user; listener(user); await settle();
  assert.ok(!buttons().some(n => n.textContent === 'Sign in'));
  const passwordForm = root.querySelectorAll('form').find(form => form.querySelectorAll('input').length === 3);
  const fields = passwordForm.querySelectorAll('input');
  const submit = () => passwordForm.events.submit({ preventDefault() {} });
  fields[0].value = 'current'; fields[1].value = 'new-password'; fields[2].value = 'different';
  submit(); await settle();
  assert.equal(reauthCalls, 0);
  assert.equal(passwordCalls, 0);
  fields[2].value = fields[1].value; failReauth = true;
  submit(); await settle();
  assert.equal(reauthCalls, 1);
  assert.equal(passwordCalls, 0);
  assert.ok(fields.every(field => field.value === ''));
  failReauth = false;
  fields[0].value = 'current'; fields[1].value = fields[2].value = 'new-password';
  submit(); await settle();
  assert.equal(passwordCalls, 1);
  assert.ok(fields.every(field => field.value === ''));
  assert.equal(commentReads, 0);
  const aboutForm = root.querySelectorAll('form').find(form => form.querySelectorAll('textarea').length === 1);
  const aboutInputs = aboutForm.querySelectorAll('input');
  aboutInputs[0].value = '  A mathematics project  ';
  aboutForm.querySelectorAll('textarea')[0].value = '  Interested in exposition.  ';
  aboutInputs[1].value = 'https://linkedin.com.evil.test/in/test';
  aboutForm.events.submit({ preventDefault() {} }); await settle();
  assert.equal(savedDetails, undefined);
  aboutInputs[1].value = 'https://www.linkedin.com/in/test';
  aboutForm.events.submit({ preventDefault() {} }); await settle();
  assert.deepEqual(savedDetails, { workingOn: 'A mathematics project', bio: 'Interested in exposition.', linkedin: 'https://www.linkedin.com/in/test' });
  auth.currentUser = null; listener(null); await settle();
  assert.ok(!buttons().some(n => n.textContent === 'Change password'));
});
