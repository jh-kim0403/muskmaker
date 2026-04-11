const { withDangerousMod } = require('@expo/config-plugins');
const fs = require('fs');
const path = require('path');

// React Native Firebase requires both use_frameworks! :linkage => :static
// AND use_modular_headers! to compile correctly on iOS.
module.exports = function withModularHeaders(config) {
  return withDangerousMod(config, [
    'ios',
    (config) => {
      const podfilePath = path.join(config.modRequest.platformProjectRoot, 'Podfile');
      let podfile = fs.readFileSync(podfilePath, 'utf8');

      // Remove previous injections to avoid duplication on re-runs
      podfile = podfile.replace(/\n?\s*use_modular_headers!\n/g, '\n');
      podfile = podfile.replace(/\n?\s*use_frameworks! :linkage => :static\n/g, '\n');

      // Inject both after platform declaration
      podfile = podfile.replace(
        /^(platform :ios.*)/m,
        '$1\nuse_frameworks! :linkage => :static\nuse_modular_headers!'
      );

      fs.writeFileSync(podfilePath, podfile);
      return config;
    },
  ]);
};
