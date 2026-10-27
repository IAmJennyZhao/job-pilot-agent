/** Encode website copies and package actual screenshots without compositing UI content. */
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";

const require = createRequire(import.meta.url);
const sharp = require("sharp"); // Installed with Next.js.
const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const directory = path.resolve(frontend, "../docs/assets/screenshots");
const manifestPath = path.join(directory, "manifest.json");
const manifest = JSON.parse(await fs.readFile(manifestPath, "utf8"));
if (manifest.fictional !== true || manifest.screenshots.length !== 10) throw new Error("Expected the complete fictional screenshot set.");
const escape = value => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll('"', "&quot;");
const kb = bytes => `${Math.round(bytes / 1024)} KB`;
for (const shot of manifest.screenshots) {
  const original = await fs.readFile(path.join(directory, `${shot.file}.png`));
  const metadata = await sharp(original).metadata();
  const web = await sharp(original).resize({ width: Math.min(metadata.width, 1920), withoutEnlargement: true }).webp({ quality: 94, effort: 6 }).toBuffer();
  const encoded = await sharp(web).metadata();
  await fs.writeFile(path.join(directory, `${shot.file}.webp`), web);
  shot.original = { file: `${shot.file}.png`, width: metadata.width, height: metadata.height, bytes: original.length, sha256: createHash("sha256").update(original).digest("hex") };
  shot.web = { file: `${shot.file}.webp`, width: encoded.width, height: encoded.height, bytes: web.length, sha256: createHash("sha256").update(web).digest("hex") };
}
await fs.writeFile(manifestPath, JSON.stringify(manifest, null, 2) + "\n");

const rows = manifest.screenshots.map((shot, index) => `| ${index + 1} | [${shot.title}](${shot.file}.webp) | [PNG](${shot.file}.png), ${shot.original.width}×${shot.original.height} | ${kb(shot.web.bytes)} |`).join("\n");
const descriptions = manifest.screenshots.map(shot => `### ${shot.title}\n\n${shot.recommended}\n\nAlt text: ${shot.alt}\n`).join("\n");
const readme = `# JobPilot website screenshots

Captured October 26, 2026 from the real completed interface. **Use Jobs tracker and Dashboard as the two primary project-page images.** The other images support individual features.

All people, companies, application histories, evidence and AI responses are fictional demo content. The set uses 32 applications (30 non-archived), candidate Alex Rivera and reserved \`.example.test\` domains. It is independent of the owner's database. Suggested website disclosure: **“Screens shown with fictional demo data.”** AI feedback is authored and deterministic, not a live quality benchmark.

[Open the gallery](index.html). WebP files are optimized website copies, capped at 1920px wide. PNGs are original 2× browser captures. No fields, warnings or results were painted over; only Next's development indicator is hidden. Desktop captures are viewport crops of scrollable pages. The mobile Dashboard is a full-page capture; the mobile Jobs image is a viewport capture. Application Assets was not redesigned or featured.

| Order | Website copy | Full-resolution original | Web size |
| --- | --- | --- | --- |
${rows}

## Captions and alt text

${descriptions}
## Recreate and package

Install the project's backend development dependencies and frontend dependencies first. No real provider key is required.

\`\`\`powershell
cd frontend
npx playwright install chromium
node node_modules/@playwright/test/cli.js test -c playwright.portfolio.config.ts
node scripts/package-portfolio.mjs
node scripts/verify-portfolio.mjs
\`\`\`

The dedicated backend creates a new temporary SQLite database and authors its records through existing APIs. It never opens the normal database. AI and research are deterministic local fixtures; unexpected provider requests fail. Demo servers bind only to 127.0.0.1 on ports 3120/8120 and refuse server reuse. The frontend uses a fresh source snapshot under ignored repository logs, with separate build output and no .env copied. Existing app source and assets are not edited for the images.

The capture exercises intake, cohort reporting, ordinary resume generation/content review, saved project progress, and Interview evaluation using demo records. It is an asset-production check, not a replacement for the regression suite. Rendering/export approval is not claimed by the text-preview image.

The packager uses Sharp supplied with Next.js, verifies the ten-image manifest, writes WebP copies/gallery, and creates \`frontend/logs/jobpilot-portfolio-screenshots.zip\`. That convenience ZIP is ignored by Git. Original images, website copies, this guide and \`manifest.json\` are retained in this directory. The manifest records dimensions, file sizes and SHA-256 hashes.
`;
await fs.writeFile(path.join(directory, "README.md"), readme);

const cards = manifest.screenshots.map((shot, index) => `<article data-kind="${index < 2 ? "primary" : index > 7 ? "mobile" : "support"}"><h2>${escape(shot.title)}${index < 2 ? '<span class="tag">Recommended</span>' : ""}</h2><a href="${shot.original.file}" aria-label="Open full-resolution ${escape(shot.title)}"><img src="${shot.web.file}" width="${shot.web.width}" height="${shot.web.height}" loading="${index < 2 ? "eager" : "lazy"}" decoding="async" alt="${escape(shot.alt)}"></a><p>${escape(shot.recommended)}</p><p class="downloads"><a href="${shot.web.file}" download>WebP · ${kb(shot.web.bytes)}</a><a href="${shot.original.file}" download>PNG · ${shot.original.width}×${shot.original.height}</a></p></article>`).join("\n");
await fs.writeFile(path.join(directory, "index.html"), `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>JobPilot project screenshots</title><style>:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f5faf4;color:#193b29;font:16px/1.6 system-ui}main{max-width:1520px;padding:40px 24px;margin:auto}h1{font-size:36px;letter-spacing:-1px;margin:0}h2{font-size:19px;margin:0 0 16px}header p{max-width:820px;color:#526b58}.filters{display:flex;gap:10px;margin:24px 0}button{font:inherit;cursor:pointer;border:1px solid #c8dcc4;padding:8px 18px;border-radius:6px;background:white;color:#193b29}button[aria-pressed=true]{background:#3a503f;color:white}.grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}article{background:white;border:1px solid #c8dcc4;border-radius:12px;padding:20px;min-width:0}article[hidden]{display:none}img{display:block;max-width:100%;width:100%;height:auto;border:1px solid #e0e8de;border-radius:5px}article[data-kind=mobile] img{max-height:850px;width:auto;max-width:100%;object-fit:contain;object-position:top;display:block;margin:auto}a{color:#2c573c;text-underline-offset:3px}.tag{font-size:12px;font-weight:500;background:#d8edd5;border-radius:4px;margin-left:12px;padding:4px 8px}.downloads{display:flex;flex-wrap:wrap;gap:20px;font-size:14px}footer{margin-top:24px;color:#526b58}@media(max-width:850px){.grid{grid-template-columns:1fr}main{padding:24px 16px}h1{font-size:30px}}</style><main><header><h1>JobPilot</h1><p>Website-ready screenshots of the completed UI, with fictional demo data. Jobs and Dashboard are featured first. Open an image for the full-resolution PNG, or download its optimized WebP for the project page.</p><p><a href="README.md">Captions, alt text and capture notes</a></p></header><nav class="filters" aria-label="Filter screenshots"><button data-filter="all" aria-pressed="true">All</button><button data-filter="primary" aria-pressed="false">Primary</button><button data-filter="mobile" aria-pressed="false">Mobile</button></nav><div class="grid">${cards}</div><footer>Actual browser captures · October 26, 2026 · Fictional candidate and employers · Authored demo AI output</footer></main><script>document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('[data-filter]').forEach(other=>other.setAttribute('aria-pressed',String(other===button)));document.querySelectorAll('[data-kind]').forEach(card=>card.hidden=button.dataset.filter!=='all'&&card.dataset.kind!==button.dataset.filter)}))</script></html>`);

const zip = path.join(frontend, "logs/jobpilot-portfolio-screenshots.zip");
const python = process.platform === "win32" ? "py" : "python3";
execFileSync(python, [...(process.platform === "win32" ? ["-3.13"] : []), "-c", "import pathlib,sys,zipfile; folder=pathlib.Path(sys.argv[1]); z=zipfile.ZipFile(sys.argv[2],'w',zipfile.ZIP_DEFLATED); [z.write(p,p.name) for p in sorted(folder.iterdir()) if p.is_file()]; z.close()", directory, zip]);
console.log(`Packaged ${manifest.screenshots.length} PNG originals, 10 WebP copies, gallery and captions.\nZIP: ${zip}`);
