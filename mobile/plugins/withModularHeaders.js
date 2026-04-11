const { withDangerousMod } = require('@expo/config-plugins');
const fs = require('fs');
const path = require('path');

// React Native Firebase requires modular headers for specific pods only.
// Using use_modular_headers! globally breaks FirebaseAuth Swift headers.
const MODULAR_PODS = [
  'GoogleUtilities',
  'GoogleDataTransport',
  'nanopb',
  'PromisesObjC',
  'abseil',
  'gRPC-Core',
  'gRPC-C++',
  'leveldb-library',
];

module.exports = function withModularHeaders(config) {
  return withDangerousMod(config, [
    'ios',
    (config) => {
      const podfilePath = path.join(config.modRequest.platformProjectRoot, 'Podfile');
      let podfile = fs.readFileSync(podfilePath, 'utf8');

      const podLines = MODULAR_PODS.map(
        (pod) => `  pod '${pod}', :modular_headers => true`
      ).join('\n');

      const marker = '# React Native Firebase modular headers (auto-generated)';
      if (!podfile.includes(marker)) {
        podfile = podfile.replace(
          'end\n',
          `\n  ${marker}\n${podLines}\nend\n`
        );
        fs.writeFileSync(podfilePath, podfile);
      }

      return config;
    },
  ]);
};
