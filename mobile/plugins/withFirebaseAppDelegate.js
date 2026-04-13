const { withAppDelegate } = require('@expo/config-plugins');

// Expo SDK 53 / RN 0.79 uses a Swift AppDelegate.
// @react-native-firebase/app's plugin targets ObjC, so FirebaseApp.configure()
// never gets called. This plugin patches the Swift AppDelegate directly.
module.exports = function withFirebaseAppDelegate(config) {
  return withAppDelegate(config, (config) => {
    const { modResults } = config;

    if (modResults.language === 'swift') {
      if (!modResults.contents.includes('import FirebaseCore') && !modResults.contents.includes('import Firebase')) {
        // Try common import anchors — Expo SDK 53 uses 'import Expo', older SDKs use 'import UIKit'
        const anchor = modResults.contents.includes('import Expo') ? 'import Expo' : 'import UIKit';
        modResults.contents = modResults.contents.replace(
          anchor,
          `${anchor}\nimport FirebaseCore`
        );
      }
      if (!modResults.contents.includes('FirebaseApp.configure()')) {
        modResults.contents = modResults.contents.replace(
          /override func application\(_ application: UIApplication, didFinishLaunchingWithOptions[^\{]+\{/,
          (match) => `${match}\n    FirebaseApp.configure()`
        );
      }
    } else {
      // Fallback for ObjC AppDelegate
      if (!modResults.contents.includes('@import Firebase')) {
        modResults.contents = modResults.contents.replace(
          '#import "AppDelegate.h"',
          '#import "AppDelegate.h"\n@import Firebase;'
        );
      }
      if (!modResults.contents.includes('[FIRApp configure]')) {
        modResults.contents = modResults.contents.replace(
          /- \(BOOL\)application:\(UIApplication \*\)application didFinishLaunchingWithOptions:[^\{]+\{/,
          (match) => `${match}\n  [FIRApp configure];`
        );
      }
    }

    return config;
  });
};
