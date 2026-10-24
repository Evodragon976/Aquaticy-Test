// Aquaticy als Cloudflare-Worker: dieselbe Oberflaeche, ohne Datenbank, ohne Konten.
//
// Workers erlaubt im Hauptmodul nur den Handler als Export; alles andere steht in
// server.js (und ist dort fuer die Tests erreichbar).

import { bearbeite } from "./server.js";

export default {
  fetch(request, env, ctx) {
    return bearbeite(request, env, ctx);
  },
};
