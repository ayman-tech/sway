// Reproducible vector export; no changes to the coloured app/launcher icons.
import sharp from "sharp";
const icons = new URL("../public/icons/", import.meta.url);
await sharp(new URL("sway-badge.svg", icons).pathname, { density: 384 })
  .resize(96, 96).png().toFile(new URL("sway-badge-96.png", icons).pathname);
