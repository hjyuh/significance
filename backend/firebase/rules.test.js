import { readFile } from 'node:fs/promises';
import { after, before, beforeEach, test } from 'node:test';
import { initializeTestEnvironment, assertFails, assertSucceeds } from '@firebase/rules-unit-testing';
import { collection, doc, getDocs, setDoc, deleteDoc, serverTimestamp, writeBatch } from 'firebase/firestore';

let env;
before(async () => {
  env = await initializeTestEnvironment({ projectId: 'demo-significance', firestore: {
    host: '127.0.0.1', port: 8088, rules: await readFile('firestore.rules', 'utf8')
  }});
});
beforeEach(async () => {
  await env.clearFirestore();
  await env.withSecurityRulesDisabled(async context => {
    await setDoc(doc(context.firestore(), 'tasks/pilot'), { recordId: 'pilot' });
    await setDoc(doc(context.firestore(), 'moderators/mod'), {});
  });
});
after(async () => { await env?.cleanup(); });
function user(uid = 'alice', verified = true) {
  return env.authenticatedContext(uid, { email_verified: verified }).firestore();
}
function post(db, uid = 'alice', task = 'pilot', extra = {}) {
  const batch = writeBatch(db);
  const reference = doc(collection(db, `tasks/${task}/comments`));
  batch.set(reference, {
    uid, name: 'Alice', body: 'A bounded question.', createdAt: serverTimestamp(), ...extra
  });
  batch.set(doc(db, `postLimits/${uid}`), { lastPosted: serverTimestamp(), lastComment: `${task}/${reference.id}` });
  return batch.commit();
}
test('anonymous readers can read comments but cannot post', async () => {
  const db = env.unauthenticatedContext().firestore();
  await assertSucceeds(getDocs(collection(db, 'tasks/pilot/comments')));
  await assertFails(post(db));
});
test('verified authors can post, and rapid repeat posts are refused', async () => {
  await assertSucceeds(post(user()));
  await assertFails(post(user()));
});
test('unverified accounts and forged authors cannot post', async () => {
  await assertFails(post(user('alice', false)));
  await assertFails(post(user('mallory'), 'alice'));
});
test('invented tasks, oversized bodies and extra fields are refused', async () => {
  await assertFails(post(user(), 'alice', 'invented'));
  await assertFails(post(user(), 'alice', 'pilot', { body: 'x'.repeat(4001) }));
  await assertFails(post(user(), 'alice', 'pilot', { email: 'private@example.test' }));
});
test('posting without the atomic cooldown update is refused', async () => {
  await assertFails(setDoc(doc(user(), 'tasks/pilot/comments/one'), {
    uid: 'alice', name: 'Alice', body: 'question', createdAt: serverTimestamp()
  }));
});
test('only author or moderator can delete; clients cannot appoint moderators', async () => {
  await assertSucceeds(post(user()));
  const snapshot = await getDocs(collection(user(), 'tasks/pilot/comments'));
  const path = snapshot.docs[0].ref.path;
  await assertFails(deleteDoc(doc(user('mallory'), path)));
  await assertFails(setDoc(doc(user('mallory'), 'moderators/mallory'), {}));
  await assertSucceeds(deleteDoc(doc(user('mod'), path)));
});
test('account rate-limit records are private', async () => {
  await assertSucceeds(post(user()));
  await assertFails(getDocs(collection(user('mallory'), 'postLimits')));
});
