import { readFile } from "node:fs/promises";

// Wie die rules in wrangler.toml: .html als Text, .png als ArrayBuffer.
export async function load(url, context, nextLoad) {
  if (url.endsWith(".html")) {
    const text = await readFile(new URL(url), "utf8");
    return { format: "module", source: `export default ${JSON.stringify(text)};`,
      shortCircuit: true };
  }
  if (url.endsWith(".png")) {
    const b64 = (await readFile(new URL(url))).toString("base64");
    return { format: "module", shortCircuit: true,
      source: `export default Uint8Array.from(atob(${JSON.stringify(b64)}), `
        + "(z) => z.charCodeAt(0)).buffer;" };
  }
  return nextLoad(url, context);
}
