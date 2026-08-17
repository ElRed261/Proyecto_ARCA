import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

// WebdriverIO + tauri-driver (protocolo WebDriver) para controlar la ventana Tauri real.
// Requisitos:
//   1. cargo install tauri-driver --locked
//   2. Terminal 1: tauri-driver (puerto 4444)
//   3. Terminal 2: npm run tauri:dev  (app en modo dev)
//   4. Terminal 3: npm run e2e:ui
export const config = {
  runner: 'local',
  specs: ['./e2e/specs/**/*.js'],
  capabilities: [
    {
      maxInstances: 1,
      'tauri:options': {
        application: join(__dirname, '..', 'src-tauri', 'target', 'debug', 'app'),
      },
    },
  ],
  hostname: '127.0.0.1',
  port: 4444,
  path: '/',
  logLevel: 'error',
  framework: 'mocha',
  mochaOpts: { ui: 'bdd', timeout: 60000 },
  reporters: ['spec'],
  waitforTimeout: 10000,
};
