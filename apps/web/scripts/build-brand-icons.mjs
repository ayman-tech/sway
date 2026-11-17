// Reproducible icon exports from the SVG wave mark, with maskable safe padding.
import sharp from "sharp";
const icons = new URL("../public/icons/", import.meta.url);
for (const size of [32, 180, 192, 512]) {
  await sharp(new URL("sway-icon.svg", icons).pathname, { density: 384 }).resize(size, size).png().toFile(new URL(`sway-${size}.png`, icons).pathname);
}
await sharp(new URL("sway-icon.svg", icons).pathname, { density: 384 }).resize(512, 512).png().toFile(new URL("sway-maskable-512.png", icons).pathname);
await sharp(new URL("sway-badge.svg", icons).pathname, { density: 384 }).resize(96, 96).png().toFile(new URL("sway-badge-96.png", icons).pathname);
