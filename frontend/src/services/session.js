/* Session token only (no name/email is kept in browser storage).
   User token: localStorage, so a refresh keeps the signup.
   Storage can be unavailable (private mode, blocked site data), so every access is guarded. */
const USER_KEY = "yw_user_token";

const read = (store, key) => { try { return store.getItem(key); } catch { return null; } };
const write = (store, key, value) => {
  try { value ? store.setItem(key, value) : store.removeItem(key); } catch { /* storage unavailable: session lasts this page only */ }
};

let memoryUser = null; // fallback when storage is blocked

export const getUserToken = () => read(localStorage, USER_KEY) ?? memoryUser;
export const setUserToken = (t) => { memoryUser = t; write(localStorage, USER_KEY, t); };
