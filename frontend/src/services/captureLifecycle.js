/* NO SELFIE STORAGE: the customer's captured photo lives in browser memory only, and only while a screen needs it.
   Review shows it and Processing analyses it (and keeps it for "Try again" after a failure). Every other screen
   (home, details, camera/retake, tips, results, routine, Ask Yuri) means the scan was exited, restarted or completed:
   the capture is released there (App.jsx). The report's copy is separate (services/reportPhoto.js). */

export const CAPTURE_SCREENS = Object.freeze(["review", "processing"]);

/** May the captured photo stay in memory while `screen` is shown? */
export const keepsCapture = (screen) => CAPTURE_SCREENS.includes(screen);
