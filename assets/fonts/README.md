# Caption font library

The catalog in `packages/shared/caption-fonts.json` describes 16 families and
223 static faces. Each visible weight and italic style has a real bundled font.
Families only expose their available weights: for example, Bebas Neue has a
single Regular face, while Urbanist provides Thin through Black plus italics.

`caption/` contains the TTFs used by libass. Browser WOFF2s in
`apps/web/public/fonts/caption/` are compressed from these exact faces and load
only when used. Every family includes its original license and source notice.
The unique native family names avoid substituted or artificially bolded export
faces and respect upstream reserved names. The UI retains familiar family names.

Font width is a separate 75–150% horizontal scaling control. It composes with
caption animations and does not claim to be a designed variable-width master.

To regenerate with Python and `fonttools` + `brotli` installed:

```powershell
python scripts/build_caption_fonts.py
```

The pinned source lock includes immutable download URLs and SHA-256 checksums.
Use `--refresh-sources` deliberately to refresh the upstream family versions.
Commit the catalog, its API package copy, fonts, licenses, source lock and generated
CSS together. `caption-fonts.test.ts` checks catalog parity, asset presence,
native weights and distinct glyph outlines; renderer tests cover font selection.
