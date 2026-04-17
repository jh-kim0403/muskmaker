const fs = require('fs');
const path = require('path');

const appJson = require('./app.json');

const APP_ENV = process.env.APP_ENV || 'development';
const VALID_APP_ENVS = new Set(['development', 'test', 'production']);

if (!VALID_APP_ENVS.has(APP_ENV)) {
  throw new Error(
    `Invalid APP_ENV "${APP_ENV}". Expected development, test, or production.`
  );
}

function parseEnvFile(filePath) {
  if (!fs.existsSync(filePath)) return {};

  return fs
    .readFileSync(filePath, 'utf8')
    .split(/\r?\n/)
    .reduce((env, line) => {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) return env;

      const equalsIndex = trimmed.indexOf('=');
      if (equalsIndex === -1) return env;

      const key = trimmed.slice(0, equalsIndex).trim();
      let value = trimmed.slice(equalsIndex + 1).trim();

      if (
        (value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))
      ) {
        value = value.slice(1, -1);
      }

      env[key] = value;
      return env;
    }, {});
}

const env = {
  ...parseEnvFile(path.join(__dirname, '.env')),
  ...process.env,
  ...parseEnvFile(path.join(__dirname, `.env.${APP_ENV}`)),
  ...parseEnvFile(path.join(__dirname, `.env.${APP_ENV}.local`)),
};

const admob = {
  iosAppId: env.ADMOB_IOS_APP_ID || undefined,
  androidAppId: env.ADMOB_ANDROID_APP_ID || undefined,
  iosBannerAdUnitId: env.ADMOB_IOS_BANNER_AD_UNIT_ID || undefined,
  iosInterstitialAdUnitId: env.ADMOB_IOS_INTERSTITIAL_AD_UNIT_ID || undefined,
  androidBannerAdUnitId: env.ADMOB_ANDROID_BANNER_AD_UNIT_ID || undefined,
  androidInterstitialAdUnitId: env.ADMOB_ANDROID_INTERSTITIAL_AD_UNIT_ID || undefined,
};

const requiredAdMobKeys = ['iosAppId', 'androidAppId'];
const missingAdMobKeys = requiredAdMobKeys.filter((key) => !admob[key]);

if (missingAdMobKeys.length > 0) {
  throw new Error(
    `Missing AdMob config for APP_ENV=${APP_ENV}: ${missingAdMobKeys.join(', ')}`
  );
}

const plugins = appJson.expo.plugins.map((plugin) => {
  if (Array.isArray(plugin) && plugin[0] === 'react-native-google-mobile-ads') {
    return [
      'react-native-google-mobile-ads',
      {
        androidAppId: admob.androidAppId,
        iosAppId: admob.iosAppId,
      },
    ];
  }

  return plugin;
});

module.exports = {
  expo: {
    ...appJson.expo,
    plugins,
    extra: {
      ...appJson.expo.extra,
      appEnv: APP_ENV,
      apiUrl: env.API_URL || undefined,
      revenueCatKeyIos: env.REVENUECAT_IOS_KEY || undefined,
      revenueCatKeyAndroid: env.REVENUECAT_ANDROID_KEY || undefined,
      admob: {
        iosBannerAdUnitId: admob.iosBannerAdUnitId,
        iosInterstitialAdUnitId: admob.iosInterstitialAdUnitId,
        androidBannerAdUnitId: admob.androidBannerAdUnitId,
        androidInterstitialAdUnitId: admob.androidInterstitialAdUnitId,
      },
    },
  },
};
