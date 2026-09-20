/* Assets versionados para a demo sem internet. Node só é necessário no build. */
import {mkdir, copyFile, readdir, readFile, writeFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
process.chdir(fileURLToPath(new URL('.', import.meta.url)));
const output = '../src/netsentinel/api/static';
await mkdir(`${output}/vendor/licenses`, {recursive: true});
for (const [source, target] of [
  ['vis-network/standalone/umd/vis-network.min.js', 'vis-network.min.js'],
  ['socket.io-client/dist/socket.io.min.js', 'socket.io.min.js'],
]) {
  await copyFile(`node_modules/${source}`, `${output}/vendor/${target}`);
}
// Preservar avisos das dependências e ferramentas usadas para produzir os bundles.
async function licenses(dir, relative = '') {
  for (const item of await readdir(dir, {withFileTypes: true})) {
    const rel = path.join(relative, item.name), full = path.join(dir, item.name);
    if (item.isDirectory()) await licenses(full, rel);
    else if (/^(license|copying|notice)(\.|-|$)/i.test(item.name)) {
      const target = path.join(output, 'vendor/licenses', rel);
      await mkdir(path.dirname(target), {recursive: true}); await copyFile(full, target);
    }
  }
}
await licenses('node_modules');
const manifest = JSON.parse(await readFile('package.json', 'utf8'));
await writeFile(`${output}/vendor/versions.json`, JSON.stringify(manifest.dependencies, null, 2) + '\n');
execFileSync(process.execPath, ['node_modules/@tailwindcss/cli/dist/index.mjs',
  '-i', 'styles.css', '-o', `${output}/dashboard.css`, '--minify'], {stdio: 'inherit'});
// Conferência de sintaxe não exige abrir um navegador.
for (const file of ['core.mjs', 'dashboard.mjs']) execFileSync(process.execPath, ['--check', `${output}/${file}`], {stdio: 'inherit'});
