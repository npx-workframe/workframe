import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const VERSION = JSON.parse(fs.readFileSync(path.join(PACKAGE_ROOT, 'package.json'), 'utf8')).version;
export const DISCOVERY_TIMEOUT_MS = 12_000;
export const VERIFICATION_TIMEOUT_MS = 90_000;
export const HTTP_TIMEOUT_MS = 30_000;
export const QUESTION_TIMEOUT_MS = 120_000;
