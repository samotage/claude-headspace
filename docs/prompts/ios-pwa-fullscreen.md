# iOS Full-Screen PWA Setup

Make this web application run as a full-screen progressive web app (PWA) on iPad and iPhone. When the user adds the site to their home screen via Safari's "Add to Home Screen", it should launch with zero Safari chrome — no URL bar, no tab bar, no toolbar. Full screen, just the app.

## Requirements

### 1. Viewport Meta Tag

Set the viewport meta tag to include `viewport-fit=cover`. This tells Safari to extend the page into the full display area, behind safe areas, the home indicator, and rounded corners.

```html
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
```

### 2. Apple Web App Meta Tags

Add these meta tags to the `<head>` of every page (or the base/layout template):

```html
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="YOUR APP NAME">
<meta name="theme-color" content="#YOUR_BG_COLOR">
```

- `apple-mobile-web-app-capable: yes` — enables standalone mode (no Safari UI)
- `apple-mobile-web-app-status-bar-style: black-translucent` — the status bar overlays your content with white text, giving you the full screen
- `apple-mobile-web-app-title` — the name shown under the home screen icon
- `theme-color` — should match your app's background colour

### 3. Apple Touch Icons

Provide home screen icons at these sizes:

```html
<link rel="apple-touch-icon" sizes="180x180" href="/path/to/icon-180x180.png">
<link rel="apple-touch-icon" sizes="152x152" href="/path/to/icon-152x152.png">
<link rel="apple-touch-icon" sizes="120x120" href="/path/to/icon-120x120.png">
<link rel="apple-touch-icon" sizes="76x76" href="/path/to/icon-76x76.png">
```

At minimum, provide a 180x180 icon. The others are for older devices.

### 4. Web App Manifest

Create a `site.webmanifest` (or `manifest.json`) file and link it from the `<head>`:

```html
<link rel="manifest" href="/path/to/site.webmanifest">
```

The manifest should contain:

```json
{
  "name": "Your App Name",
  "short_name": "ShortName",
  "display": "standalone",
  "scope": "/",
  "start_url": "/",
  "theme_color": "#YOUR_BG_COLOR",
  "background_color": "#YOUR_BG_COLOR",
  "icons": [
    {
      "src": "/path/to/icon-192x192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/path/to/icon-512x512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

- `display: standalone` — this is what removes all Safari UI
- `scope` — the URL scope the PWA controls (usually `"/"`)
- `background_color` — splash screen background while the app loads

### 5. Safe Area Inset CSS

With `viewport-fit=cover`, your content extends behind the notch, rounded corners, and home indicator. You MUST add safe area padding to prevent content being clipped or hidden behind these hardware features.

Use `env(safe-area-inset-*)` CSS environment variables with fallbacks:

```css
/* Any element fixed to the top of the screen */
.fixed-header {
    padding-top: env(safe-area-inset-top, 0px);
}

/* Any element positioned below a fixed header — offset its top position */
.below-header {
    top: calc(YOUR_HEADER_HEIGHT + env(safe-area-inset-top, 0px));
}

/* Main content area */
.page-content {
    padding-top: calc(YOUR_HEADER_HEIGHT + env(safe-area-inset-top, 0px));
    padding-bottom: env(safe-area-inset-bottom, 0px);
}

/* Full-width fixed elements (for landscape orientation on notched devices) */
.full-width-bar {
    padding-left: env(safe-area-inset-left, 0px);
    padding-right: env(safe-area-inset-right, 0px);
}

/* Bottom-anchored elements (tab bars, drawers, menus) */
.bottom-element {
    padding-bottom: env(safe-area-inset-bottom, 0px);
}
```

**Key rules:**
- Every `position: fixed` element that touches the top edge needs `env(safe-area-inset-top)`
- Every `position: fixed` element that touches the bottom edge needs `env(safe-area-inset-bottom)`
- Elements positioned relative to a fixed header (using pixel `top` values) must add `env(safe-area-inset-top)` to their `top` calculation using `calc()`
- Landscape iPad/iPhone with notch needs left/right insets too
- Always use fallback values: `env(safe-area-inset-top, 0px)` — the `0px` fallback ensures no effect on browsers that don't support it

### 6. What This Achieves

When the user taps Share → "Add to Home Screen" in Safari:
- The app launches full screen with no Safari UI whatsoever
- The status bar text overlays the top of your app (translucent)
- Your content fills the entire screen edge to edge
- Safe area padding keeps interactive elements clear of hardware obstructions
- The app gets its own entry in the iOS app switcher
- It behaves like a native app from the user's perspective
