# Privacy

*Draft. This page will be finalised before the first public deployment.*

BrewNotes is a personal project run by one person. This page says plainly what the app stores and what it does not.

## What is stored

- **Your account:** the ID that GitHub or Google assigns you, your display name, and your avatar URL. BrewNotes does not ask for or store your email address, and it never sees your password.
- **What you enter:** recipes, batches, readings, beers, tastings, custom ingredients, and your settings.

## What is not stored

- **No email addresses.** There is nothing to send you, so none are collected.
- **No IP addresses.** The app does not store IP addresses or write them to its logs. The hosting platform's own access logs may record them for a short time under its retention policy.
- **No precise location.** The "near me" feature on the brewery map converts your location into a map area in your browser. Only that area is sent to the server to fetch breweries, and the server does not store or log it.

## Who can see your data

Only you. Recipes, batches, tastings and commercial beers you log are private to your account. There are no public profiles or shared catalogues.

## Export and deletion

From the account page you can download everything you have entered as a JSON file, and you can delete your account. Deletion removes your data from the live database immediately. Database backups kept by the hosting provider age out on its retention schedule, after which the data is gone from there too.

## Third parties

- **GitHub and Google** handle sign-in. BrewNotes asks for the minimum identity scope each provider allows.
- **Map tiles** on the brewery map are loaded from a tile provider, which receives the requests your browser makes for map images.
- **Error reporting**, if enabled, is configured not to capture IP addresses and to scrub cookies and tokens.

## Changes

If this page changes materially, the change will be noted in the repository history and on this page.
