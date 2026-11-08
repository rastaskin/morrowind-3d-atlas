# Privacy

- Starting with 1.3.0, the desktop launcher has an opt-in update button. Checking sends an HTTPS request to the public GitHub Releases API; downloading uses GitHub release asset servers. These requests contain the app version in the User-Agent and the normal network connection information. Saves, notes, progress, game paths and account credentials are never sent. There are no update checks on startup or in the background without a button click.
- Downloaded installers and local update logs stay under the application's local cache. Updates preserve the generated game resources and browser localStorage. The launcher waits for a user confirmation before downloading and installing a newer release.

- Save files are selected using the browser File API and decoded on the device. There is no upload endpoint, analytics, remote font CDN, cloud account or synchronization service.
- The application retains only location checkboxes and notes in browser localStorage. Marker size is a separate local preference. The source save, filename and character metadata are not persisted.
- The local HTTP server serves files under `public/` and listens on loopback only. It cannot browse the game installation or receive a save upload.
- Browser storage is tied to the origin. The same browser profile is shared storage: this application does not provide separate authenticated users. Export a backup before clearing site data.
- Progress exports can contain notes entered by their owner. Treat these JSON files as private when sharing screenshots, logs or Git changes.
- The public repository starts with no player progress. Documentation screenshots use deterministic fictional demo marks and are labelled as demonstrations.
- Generated game assets, save files, user-provided fonts, environment files and local fixture output are ignored by Git. The unmodified MysticCards font is bundled under SIL OFL 1.1 with its license and source attribution. It loads locally, without an OS font installation or a font CDN. Publication checks inspect the candidate source tree; review staged changes before publishing future updates.

The application is a local static viewer, not an online service. Any deployment by a third party has its own hosting policies. This document describes the code shipped in this repository.
