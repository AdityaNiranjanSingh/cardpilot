# CardPilot Mobile App

This is the Expo / React Native starter app for CardPilot.

## Local testing

```bash
npm install
npm start
```

For local testing on a phone, set the API URL to your laptop IP address:

```bash
EXPO_PUBLIC_API_URL=http://192.168.1.10:8000 npm start
```

Do not use `127.0.0.1` on a real phone unless the backend is running on the phone itself.

## Online testing with friends

After the backend is deployed online, set the API URL to your Render/Railway backend URL:

```bash
EXPO_PUBLIC_API_URL=https://your-cardpilot-backend.onrender.com
```

The app reads this value through `process.env.EXPO_PUBLIC_API_URL`.

## Build Android APK for sharing

Install EAS CLI and log in:

```bash
npm install -g eas-cli
eas login
eas build:configure
eas build -p android --profile preview
```

The `preview` profile in `eas.json` is configured for Android internal distribution APK builds.

Before building, edit `eas.json` and replace:

```text
https://your-cardpilot-backend.onrender.com
```

with your real online backend URL.
