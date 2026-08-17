/* global process */
import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

const SRC = join(process.cwd(), 'src');
const LIB_RS = join(process.cwd(), 'src-tauri', 'src', 'lib.rs');

function walk(dir, acc = []) {
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    if (statSync(p).isDirectory()) walk(p, acc);
    else if (/\.(js|jsx)$/.test(entry) && !entry.endsWith('.test.js')) acc.push(p);
  }
  return acc;
}

/** Comandos registrados en el backend (bloque tauri::generate_handler! en lib.rs) */
function registeredCommands() {
  const src = readFileSync(LIB_RS, 'utf8');
  const start = src.indexOf('generate_handler![');
  const end = src.indexOf('])', start);
  const names = new Set();
  for (const line of src.slice(start, end).split('\n')) {
    const m = line.match(/::\s*([a-z_][a-z0-9_]*)\s*,?\s*$/);
    if (m) names.add(m[1]);
  }
  return names;
}

/** Keys de storage / strings que parecen comandos pero NO lo son */
const NON_COMMAND_STRINGS = new Set([
  'user_email',
  'user_roles',
  'assigned_station',
  'synoptic_draft',
]);

/** Comandos invocados DIRECTAMENTE: primer argumento de invoke(...) (soporta ternarios inline) */
function invokedCommands() {
  const names = new Set();
  for (const file of walk(SRC)) {
    const src = readFileSync(file, 'utf8');
    for (const line of src.split('\n')) {
      for (const m of line.matchAll(/invoke\(\s*(?:[^'"()]*?)?['"]([a-z_][a-z0-9_]*)['"]/g)) {
        names.add(m[1]);
      }
    }
  }
  return names;
}

/** ¿El nombre aparece como string literal en algún archivo del frontend? (cubre ternarios/variables) */
function stringMentioned(name) {
  for (const file of walk(SRC)) {
    const src = readFileSync(file, 'utf8');
    if (src.includes(`'${name}'`) || src.includes(`"${name}"`)) return true;
  }
  return false;
}

describe('Wiring frontend ↔ backend (tu queja: botones que llaman a nada / comandos que nadie llama)', () => {
  const registered = registeredCommands();
  const invoked = invokedCommands();

  it('cada invoke() del frontend existe registrado en lib.rs', () => {
    const missing = [...invoked].filter((c) => !registered.has(c));
    expect(missing, `Comandos invocados pero NO registrados: ${missing.join(', ')}`).toEqual([]);
  });

  it('cada comando registrado tiene al menos un caller en el frontend', () => {
    // Excepciones justificadas: comandos de auth llamados internamente o vía helpers
    const allowedOrphans = new Set(['get_stations', 'validate_token', 'logout']);
    const orphans = [...registered].filter(
      (c) => !invoked.has(c) && !stringMentioned(c) && !allowedOrphans.has(c),
    );
    expect(orphans, `Comandos registrados SIN caller en el frontend: ${orphans.join(', ')}`).toEqual([]);
  });

  it('no quedan comandos muertos conocidos registrados (cli_autofill, summary_logs)', () => {
    expect(registered.has('calculate_cli_autofill')).toBe(false);
    expect(registered.has('get_monthly_summaries')).toBe(false);
    expect(registered.has('create_monthly_summary')).toBe(false);
  });

  it('reporta el inventario para diagnóstico', () => {
    console.log(`\n  Backend registrados: ${registered.size} | Frontend invocados: ${invoked.size}`);
    console.log(`  Sin caller: ${[...registered].filter((c) => !invoked.has(c)).join(', ') || 'ninguno'}`);
  });
});
