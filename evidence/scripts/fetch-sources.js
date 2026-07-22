// Pulls the gold marts nb_export_gold wrote to OneLake down to data/warehouse/,
// so the DuckDB source reads local parquet and the build never touches the
// Warehouse. Needs the capacity running - paused capacities reject OneLake reads.
//
// Needs AZURE_TENANT_ID / AZURE_CLIENT_ID / AZURE_CLIENT_SECRET
import { mkdir, readdir, writeFile } from 'node:fs/promises';

const WORKSPACE = 'gutenberg-fingerprint';
const DIRECTORY = 'lh_silver.Lakehouse/Files/exports';
// Outside sources/ on purpose: Evidence runs ${} substitution over every file
// in a source directory, and parquet is binary.
const DEST = 'data/warehouse';
const ONELAKE = 'https://onelake.dfs.fabric.microsoft.com';

const { AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET } = process.env;

async function getToken() {
  const res = await fetch(`https://login.microsoftonline.com/${AZURE_TENANT_ID}/oauth2/v2.0/token`, {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'client_credentials',
      client_id: AZURE_CLIENT_ID,
      client_secret: AZURE_CLIENT_SECRET,
      scope: 'https://storage.azure.com/.default'
    })
  });
  if (!res.ok) throw new Error(`token request failed: ${res.status} ${await res.text()}`);
  return (await res.json()).access_token;
}

async function listParquet(token) {
  const url = `${ONELAKE}/${WORKSPACE}?resource=filesystem&recursive=false&directory=${encodeURIComponent(DIRECTORY)}`;
  const res = await fetch(url, { headers: { authorization: `Bearer ${token}` } });
  if (!res.ok) throw new Error(`list failed: ${res.status} ${await res.text()}`);
  return (await res.json()).paths
    .filter((p) => p.isDirectory !== 'true' && p.name.endsWith('.parquet'))
    .map((p) => p.name);
}

async function download(token, path) {
  const res = await fetch(`${ONELAKE}/${WORKSPACE}/${path}`, {
    headers: { authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error(`download failed for ${path}: ${res.status}`);
  const name = path.split('/').pop();
  const body = Buffer.from(await res.arrayBuffer());
  await writeFile(`${DEST}/${name}`, body);
  console.log(`  ${name} (${(body.length / 1024).toFixed(0)} KB)`);
}

if (!AZURE_TENANT_ID || !AZURE_CLIENT_ID || !AZURE_CLIENT_SECRET) {
  const local = await readdir(DEST).catch(() => []);
  const cached = local.filter((f) => f.endsWith('.parquet'));
  if (!cached.length) {
    throw new Error(
      'fetch-sources: no Azure credentials and no local parquet in ' +
      DEST +
      '. Set AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET.'
    );
  }
  console.log(`fetch-sources: no credentials, reusing ${cached.length} cached parquet files`);
} else {
  await mkdir(DEST, { recursive: true });
  const token = await getToken();
  const paths = await listParquet(token);
  if (!paths.length) throw new Error(`fetch-sources: no parquet under ${DIRECTORY}`);
  console.log(`fetch-sources: ${paths.length} files from ${WORKSPACE}/${DIRECTORY}`);
  await Promise.all(paths.map((p) => download(token, p)));
}
