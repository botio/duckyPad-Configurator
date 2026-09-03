'use strict';

const { execFileSync } = require('node:child_process');
const { join } = require('node:path');

/**
 * electron-builder leaves the upstream Electron signature invalid after adding
 * app resources when mac.identity is null. Re-sign the complete bundle with an
 * ad-hoc identity so Gatekeeper can present the normal "Open Anyway" path
 * instead of treating the bundle as damaged. This is intentionally not a
 * Developer ID signature and does not claim notarization.
 */
exports.default = async (context) => {
  if (context.electronPlatformName !== 'darwin') return;

  const appPath = join(context.appOutDir, `${context.packager.appInfo.productFilename}.app`);
  execFileSync('codesign', ['--force', '--deep', '--sign', '-', appPath], { stdio: 'inherit' });
  execFileSync('codesign', ['--verify', '--deep', '--strict', appPath], { stdio: 'inherit' });
};
