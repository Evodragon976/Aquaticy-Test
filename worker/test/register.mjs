// Laesst Node die Oberflaeche wie wrangler als Text importieren (rules in wrangler.toml).
import { register } from "node:module";

register("./html-lader.mjs", import.meta.url);
