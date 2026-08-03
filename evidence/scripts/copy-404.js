// Lets the Pages function catch real 404s.
import { copyFileSync } from 'node:fs';

copyFileSync('build/404/index.html', 'build/404.html');
console.log('copy-404: build/404/index.html -> build/404.html');
