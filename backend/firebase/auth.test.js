import assert from 'node:assert/strict';
import { test } from 'node:test';
import { initializeApp, deleteApp } from 'firebase/app';
import { getAuth, connectAuthEmulator, createUserWithEmailAndPassword, updateProfile,
  sendEmailVerification, applyActionCode, reload, signOut, signInWithEmailAndPassword,
  sendPasswordResetEmail, confirmPasswordReset, EmailAuthProvider,
  reauthenticateWithCredential, updatePassword } from 'firebase/auth';

test('email registration, verification, login, logout and password reset work locally', async () => {
  const app = initializeApp({ apiKey: 'demo-key', projectId: 'demo-significance' }, 'auth-test');
  const auth = getAuth(app);
  connectAuthEmulator(auth, 'http://127.0.0.1:9099', { disableWarnings: true });
  const email = `test-${Date.now()}@example.test`;
  async function code(type) {
    const response = await fetch('http://127.0.0.1:9099/emulator/v1/projects/demo-significance/oobCodes');
    assert.equal(response.status, 200);
    const data = await response.json();
    const result = data.oobCodes.findLast(entry => entry.email === email && entry.requestType === type);
    assert.ok(result);
    return result.oobCode;
  }
  try {
    const created = await createUserWithEmailAndPassword(auth, email, 'ExamplePassword-123!');
    await updateProfile(created.user, { displayName: 'Local test contributor' });
    assert.equal(created.user.emailVerified, false);
    await sendEmailVerification(created.user);
    await applyActionCode(auth, await code('VERIFY_EMAIL'));
    await reload(created.user);
    assert.equal(created.user.emailVerified, true);
    const uid = created.user.uid;
    await signOut(auth);
    assert.equal(auth.currentUser, null);
    const login = await signInWithEmailAndPassword(auth, email, 'ExamplePassword-123!');
    assert.equal(login.user.uid, uid);
    await sendPasswordResetEmail(auth, email);
    await confirmPasswordReset(auth, await code('PASSWORD_RESET'), 'ChangedPassword-456!');
    await signOut(auth);
    await assert.rejects(signInWithEmailAndPassword(auth, email, 'ExamplePassword-123!'));
    assert.equal((await signInWithEmailAndPassword(auth, email, 'ChangedPassword-456!')).user.uid, uid);
    await assert.rejects(reauthenticateWithCredential(auth.currentUser,
      EmailAuthProvider.credential(email, 'WrongPassword-000!')));
    await reauthenticateWithCredential(auth.currentUser,
      EmailAuthProvider.credential(email, 'ChangedPassword-456!'));
    await updatePassword(auth.currentUser, 'ProfilePassword-789!');
    await signOut(auth);
    await assert.rejects(signInWithEmailAndPassword(auth, email, 'ChangedPassword-456!'));
    assert.equal((await signInWithEmailAndPassword(auth, email, 'ProfilePassword-789!')).user.uid, uid);
  } finally { await deleteApp(app); }
});
