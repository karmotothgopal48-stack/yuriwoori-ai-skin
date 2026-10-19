/* Session tokens only (no name/email is kept in browser storage).
   User token: localStorage, so a refresh keeps the signup. Admin token: sessionStorage (ends with the tab).
   Storage can be unavailable (private mode, blocked site data), so every access is guarded. */
const USER_KEY = "yw_user_token";
const ADMIN_KEY = "yw_admin_token";

const read = (store, key) => { try { return store.getItem(key); } catch { return null; } };
const write = (store, key, value) => {
  try { value ? store.setItem(key, value) : store.removeItem(key); } catch { /* storage unavailable: session lasts this page only */ }
};

let memoryUser = null; // fallback when storage is blocked
let memoryAdmin = null;

export const getUserToken = () => read(localStorage, USER_KEY) ?? memoryUser;
export const setUserToken = (t) => { memoryUser = t; write(localStorage, USER_KEY, t); };
export const getAdminToken = () => read(sessionStorage, ADMIN_KEY) ?? memoryAdmin;
export const setAdminToken = (t) => { memoryAdmin = t; write(sessionStorage, ADMIN_KEY, t); };
