# Bill Scanner — mobile app (Expo)

React Native app (Expo SDK 54) for scanning bills, viewing parsed line items, and analytics. Talks to **BillScannerServer** over HTTP.

## Prerequisites

| Requirement | Version / notes |
|-------------|------------------|
| **Node.js** | **20 LTS** or **22** (Expo 54 works best with current Node). |
| **npm** | Comes with Node. |
| **BillScannerServer** | Running locally or on your LAN (see server `README.md`). |
| **Phone or emulator** | [Expo Go](https://expo.dev/go), Android emulator, or iOS simulator. |

Optional: [Expo CLI](https://docs.expo.dev/get-started/installation/) via `npx` (no global install required).

## 1. Install dependencies

```bash
cd BillScannerApp
npm install
```

If native modules get out of sync with the Expo SDK, use:

```bash
npx expo install --fix
```

## 2. Point the app at your API

The app builds the API URL in this order (see `constants/api.ts`):

1. **`EXPO_PUBLIC_API_BASE_URL`** — recommended for another PC or a physical device.
2. Otherwise it infers the host from the Expo dev server (works for many emulator setups).
3. Fallback: `localhost` or Android emulator `10.0.2.2` on port **8000**.

### Same computer (web or simulator often OK)

If the API runs on the same machine:

```bash
# Windows PowerShell — use your machine’s LAN IP for a real phone on Wi‑Fi
$env:EXPO_PUBLIC_API_BASE_URL = "http://192.168.1.XX:8000"
npx expo start
```

```bash
# macOS / Linux
export EXPO_PUBLIC_API_BASE_URL="http://192.168.1.XX:8000"
npx expo start
```

Replace `192.168.1.XX` with your PC’s IP. The server must listen on `0.0.0.0` (e.g. `uvicorn main:app --host 0.0.0.0 --port 8000`).

### Create a `.env` file (optional)

In `BillScannerApp` (same folder as `package.json`):

```env
EXPO_PUBLIC_API_BASE_URL=http://YOUR_PC_IP:8000
```

Restart Expo after changing env vars (`npx expo start -c` clears cache).

**Note:** Do not commit real secrets; `.env` is usually gitignored.

## 3. Start the app

```bash
npx expo start
```

Then:

- Press **`w`** for web, **`a`** for Android emulator, **`i`** for iOS simulator, or scan the QR code with **Expo Go** on your phone.

Other scripts:

```bash
npm run android
npm run ios
npm run web
```

## 4. Device ID (backend)

The app sends a demo `device_id` in `constants/api.ts`. For production you would register the device via the server’s auth endpoints; for class demos the default often works if the backend accepts it.

## 5. Lint

```bash
npm run lint
```

## Features (high level)

- Upload bills: camera, gallery, or files (images, PDF, Word, Excel, CSV) — depends on server support.
- View parsed summary, categories, and line items.
- Analytics tab: spending summaries from the API.

## Troubleshooting

| Issue | What to try |
|-------|-------------|
| **Network request failed** / timeout | Set `EXPO_PUBLIC_API_BASE_URL` to `http://<server-ip>:8000`. Phone cannot use `localhost` for your PC’s server. |
| **Android emulator** | Server on host machine: often `http://10.0.2.2:8000` (app may infer this). |
| **CORS** | Server allows `*` in dev; if you change CORS, allow your Expo origin. |
| **Clear Metro cache** | `npx expo start -c` |

## Repo structure (short)

- `app/` — Expo Router screens (tabs: Bills, Analytics)
- `components/` — UI and bill/analytics components
- `constants/api.ts` — API base URL and routes
- `hooks/` — Data fetching hooks

## Running the full stack (checklist)

1. Start **PostgreSQL** and set **`DATABASE_URL`** on the server.
2. Start **BillScannerServer** on port **8000**.
3. Open **`http://localhost:8000/docs`** and confirm it loads.
4. Start **BillScannerApp** with **`EXPO_PUBLIC_API_BASE_URL`** pointing at that server if not on the same loopback setup.

For coursework, keep API keys and database passwords out of git.
